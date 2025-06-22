import sqlite3
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from database import get_db
import unicodedata
import math

users_bp = Blueprint('users', __name__, template_folder='templates')

PER_PAGE_USERS = 20


def _get_filtered_paginated_users(conn, search_query, page, per_page):
    params_for_sql_select = []
    where_clauses_for_filtering = []
    params_for_where_clause = []

    clean_search_query_lower = unicodedata.normalize('NFKD', search_query.strip()).encode('ascii', 'ignore').decode(
        'utf-8').lower()

    relevance_score_select_clause = "0 AS relevance_score"
    final_order_by_clause = "ORDER BY u.id ASC"

    if clean_search_query_lower:
        try:
            user_id_search = int(clean_search_query_lower)
            where_clauses_for_filtering.append("u.id = ?")
            params_for_where_clause.append(user_id_search)

            relevance_score_select_clause = "100 AS relevance_score"
            final_order_by_clause = "ORDER BY relevance_score DESC, u.id ASC"
        except ValueError:
            starts_with_pattern = f'{clean_search_query_lower}%'
            contains_pattern = f'%{clean_search_query_lower}%'

            where_clauses_for_filtering.append(
                "(remove_accents(u.nombre) LIKE ? OR remove_accents(u.apellidos) LIKE ?)"
            )
            params_for_where_clause.extend([contains_pattern, contains_pattern])

            relevance_score_select_clause = '''
                CASE
                    WHEN (remove_accents(u.nombre) LIKE ? OR remove_accents(u.apellidos) LIKE ?) THEN 2
                    WHEN (remove_accents(u.nombre) LIKE ? OR remove_accents(u.apellidos) LIKE ?) THEN 1
                    ELSE 0
                END AS relevance_score
            '''
            params_for_sql_select.extend([starts_with_pattern, starts_with_pattern, contains_pattern, contains_pattern])

            final_order_by_clause = "ORDER BY relevance_score DESC, u.id ASC"

    base_sql_from_join = '''
        FROM usuarios AS u
        LEFT JOIN modulos AS m ON u.id_modulo = m.id
    '''

    sql_where_clause_string = ""
    if where_clauses_for_filtering:
        sql_where_clause_string = " WHERE " + " AND ".join(where_clauses_for_filtering)

    count_query = f"SELECT COUNT(*) {base_sql_from_join} {sql_where_clause_string}"
    total_results = conn.execute(count_query, params_for_where_clause).fetchone()[0]
    total_pages = math.ceil(total_results / per_page) if total_results > 0 else 1
    page = max(1, min(page, max(1, total_pages)))
    offset = (page - 1) * per_page

    main_sql_select_fields = f'''
        u.id, u.apellidos, u.nombre, u.genero, u.observaciones,
        m.nombre_modulo,
        (SELECT COUNT(*) FROM prestamos WHERE id_usuario = u.id AND fecha_devolucion_real IS NULL) AS prestamos_activos,
        {relevance_score_select_clause}
    '''

    sql_query = f"SELECT {main_sql_select_fields} {base_sql_from_join} {sql_where_clause_string} {final_order_by_clause} LIMIT ? OFFSET ?"

    final_params = params_for_sql_select + params_for_where_clause + [per_page, offset]

    users = conn.execute(sql_query, final_params).fetchall()

    return users, total_results, total_pages


def remove_accents(input_str):
    if not isinstance(input_str, str):
        return input_str
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


@users_bp.route('/anadir', methods=('GET', 'POST'))
def anadir_usuario():
    conn = get_db()
    modulos = conn.execute('SELECT id, nombre_modulo FROM modulos ORDER BY nombre_modulo').fetchall()
    generos_existentes = conn.execute(
        'SELECT DISTINCT genero FROM usuarios WHERE genero IS NOT NULL ORDER BY genero').fetchall()

    errors = []

    user_id_input = request.form.get('user_id', '').strip()
    apellidos = request.form.get('apellidos', '').strip().upper()
    nombre = request.form.get('nombre', '').strip().upper()
    id_modulo_input = request.form.get('id_modulo', '').strip()
    genero_input = request.form.get('genero', '').strip().upper()
    observaciones = request.form.get('observaciones', '').strip()

    if request.method == 'POST':
        # --- Validaciones iniciales de campos obligatorios ---
        if not apellidos:
            errors.append('Los apellidos son obligatorios.')
        if not nombre:
            errors.append('El nombre es obligatorio.')
        if not genero_input:
            errors.append('El género es obligatorio.')

        # Validación para el módulo (obligatorio)
        if not id_modulo_input:  # Si el campo del formulario de módulo está completamente vacío
            errors.append('El módulo es obligatorio.')

        # --- Validación y manejo del ID de usuario (opcional pero si se da, debe ser único) ---
        user_id = None
        if user_id_input:
            try:
                user_id = int(user_id_input)
                if user_id <= 0:
                    errors.append('El ID de usuario debe ser un número entero positivo.')
            except ValueError:
                errors.append('El ID de usuario debe ser un número entero válido.')

            if not errors and user_id is not None:  # Solo comprobar si existe si no hay errores previos y el ID es válido
                existing_user = conn.execute("SELECT id FROM usuarios WHERE id = ?", (user_id,)).fetchone()
                if existing_user:
                    errors.append(f'El ID de usuario {user_id} ya existe. Por favor, elija otro.')

        # --- Validación y manejo del ID de módulo (Creación si no existe) ---
        final_id_modulo_for_db = None
        if id_modulo_input:  # Solo procesar la entrada del módulo si el campo no está vacío
            modulo_nombre_limpio = id_modulo_input.upper()  # Convertir el nombre a mayúsculas para la búsqueda/inserción

            parsed_id_modulo = None
            if ' - ' in id_modulo_input:  # Si viene en formato "ID - Nombre"
                try:
                    parsed_id_modulo = int(id_modulo_input.split(' - ')[0])
                except ValueError:
                    parsed_id_modulo = None  # Dejar parsed_id_modulo como None, se buscará/creará por nombre
            elif id_modulo_input.isdigit():  # Si es solo un número, intentar buscarlo como ID
                parsed_id_modulo = int(id_modulo_input)

            existing_modulo = None
            if parsed_id_modulo is not None:
                existing_modulo = conn.execute("SELECT id, nombre_modulo FROM modulos WHERE id = ?",
                                               (parsed_id_modulo,)).fetchone()

            if existing_modulo is None:  # Si no se encontró por ID, buscar por nombre
                existing_modulo = conn.execute("SELECT id, nombre_modulo FROM modulos WHERE nombre_modulo = ?",
                                               (modulo_nombre_limpio,)).fetchone()

            if existing_modulo:
                final_id_modulo_for_db = existing_modulo['id']
            else:
                # El módulo no existe, lo insertamos
                try:
                    conn.execute("INSERT INTO modulos (nombre_modulo) VALUES (?)", (modulo_nombre_limpio,))
                    conn.commit()
                    final_id_modulo_for_db = \
                    conn.execute("SELECT id FROM modulos WHERE nombre_modulo = ?", (modulo_nombre_limpio,)).fetchone()[
                        'id']
                    flash(f'Módulo "{modulo_nombre_limpio}" creado automáticamente.', 'info')
                    # Recargar la lista de módulos para la plantilla en caso de que se renderice de nuevo (por errores)
                    modulos = conn.execute('SELECT id, nombre_modulo FROM modulos ORDER BY nombre_modulo').fetchall()
                except sqlite3.IntegrityError as e:
                    # Esto podría pasar si hay una restricción UNIQUE en nombre_modulo y se intenta insertar duplicado
                    errors.append(
                        f'Error al crear el módulo "{modulo_nombre_limpio}": ya existe un módulo con ese nombre o similar. {e}')
                    conn.rollback()
                    # Si el error es por duplicado, intenta recuperar el ID del módulo existente para que el usuario pueda ser asociado.
                    existing_modulo_after_error = conn.execute("SELECT id FROM modulos WHERE nombre_modulo = ?",
                                                               (modulo_nombre_limpio,)).fetchone()
                    if existing_modulo_after_error:
                        final_id_modulo_for_db = existing_modulo_after_error['id']
                    else:
                        errors.append(
                            f'No se pudo determinar un módulo válido para el usuario tras el error de creación: {modulo_nombre_limpio}.')
                except Exception as e:
                    errors.append(f'Ocurrió un error inesperado al crear el módulo: {e}')
                    conn.rollback()

        if id_modulo_input and final_id_modulo_for_db is None and 'El módulo es obligatorio.' not in errors:
            errors.append(
                'No se pudo determinar un módulo válido para el usuario. Por favor, revise el campo "Módulo".')

        # El género final para la DB ya está en mayúsculas
        final_genero_for_db = genero_input

        if errors:
            for error in errors:
                flash(error, 'danger')
            # Volver a cargar los géneros existentes (por si se añadió uno nuevo en otro formulario mientras)
            generos_existentes = conn.execute(
                'SELECT DISTINCT genero FROM usuarios WHERE genero IS NOT NULL ORDER BY genero').fetchall()
            return render_template('add_user.html',
                                   modulos=modulos,
                                   generos_existentes=generos_existentes,
                                   user_id_input=user_id_input,
                                   apellidos=apellidos,
                                   nombre=nombre,
                                   id_modulo_input=id_modulo_input,
                                   genero_input=genero_input,
                                   observaciones=observaciones)


        prestamos_activos = 0

        try:
            if user_id is not None:
                # Insertar con ID especificado
                conn.execute(
                    'INSERT INTO usuarios (id, apellidos, nombre, id_modulo, genero, observaciones, prestamos_activos) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (user_id, apellidos, nombre, final_id_modulo_for_db, final_genero_for_db, observaciones,
                     prestamos_activos)
                )
            else:
                # Insertar sin ID, la base de datos lo generará automáticamente
                conn.execute(
                    'INSERT INTO usuarios (apellidos, nombre, id_modulo, genero, observaciones, prestamos_activos) VALUES (?, ?, ?, ?, ?, ?)',
                    (apellidos, nombre, final_id_modulo_for_db, final_genero_for_db, observaciones, prestamos_activos)
                )
            conn.commit()
            flash('Usuario añadido correctamente.', 'success')
            return redirect(url_for('users.listar_usuarios'))
        except sqlite3.IntegrityError as e:
            conn.rollback()
            if "UNIQUE constraint failed: usuarios.id" in str(e):
                flash(
                    'El ID de usuario que has introducido ya existe. Por favor, elige otro o déjalo vacío para asignación automática.',
                    'danger')
            # Este 'elif' solo se activaría si tuvieras UNIQUE en usuarios.genero (cosa que no recomiendo para géneros)
            elif "UNIQUE constraint failed: usuarios.genero" in str(e):
                flash(f'El género "{genero_input}" ya está asignado a otro usuario (si la columna género es UNIQUE).',
                      'danger')
            elif "NOT NULL constraint failed: usuarios.id_modulo" in str(e):
                flash('Error: El módulo es un campo obligatorio y no pudo ser asignado. Revise su selección.', 'danger')
            else:
                flash(f'Ocurrió un error de integridad en la base de datos: {e}', 'danger')

            # Si hay un error de base de datos, volvemos a cargar los datos necesarios para renderizar el formulario.
            modulos = conn.execute('SELECT id, nombre_modulo FROM modulos ORDER BY nombre_modulo').fetchall()
            generos_existentes = conn.execute(
                'SELECT DISTINCT genero FROM usuarios WHERE genero IS NOT NULL ORDER BY genero').fetchall()
            return render_template('add_user.html',
                                   modulos=modulos,
                                   generos_existentes=generos_existentes,
                                   user_id_input=user_id_input,
                                   apellidos=apellidos,
                                   nombre=nombre,
                                   id_modulo_input=id_modulo_input,
                                   genero_input=genero_input,
                                   observaciones=observaciones)
        except Exception as e:
            flash(f'Ocurrió un error inesperado al añadir el usuario: {e}', 'danger')
            conn.rollback()
            # Si hay un error general, volvemos a cargar los datos necesarios para renderizar el formulario.
            modulos = conn.execute('SELECT id, nombre_modulo FROM modulos ORDER BY nombre_modulo').fetchall()
            generos_existentes = conn.execute(
                'SELECT DISTINCT genero FROM usuarios WHERE genero IS NOT NULL ORDER BY genero').fetchall()
            return render_template('add_user.html',
                                   modulos=modulos,
                                   generos_existentes=generos_existentes,
                                   user_id_input=user_id_input,
                                   apellidos=apellidos,
                                   nombre=nombre,
                                   id_modulo_input=id_modulo_input,
                                   genero_input=genero_input,
                                   observaciones=observaciones)

    return render_template('add_user.html',
                           modulos=modulos,
                           generos_existentes=generos_existentes,
                           user_id_input='',
                           apellidos='',
                           nombre='',
                           id_modulo_input='',
                           genero_input='',
                           observaciones='')


@users_bp.route('/editar/<int:user_id>', methods=['GET', 'POST'])
def editar_usuario(user_id):
    conn = get_db()
    errors = []
    usuario_actual = conn.execute('''
        SELECT
            u.id,
            u.nombre,
            u.apellidos,
            u.id_modulo,
            m.nombre_modulo, -- Para mostrar el nombre del módulo en el input datalist
            u.genero,
            u.observaciones
        FROM usuarios AS u
        LEFT JOIN modulos AS m ON u.id_modulo = m.id
        WHERE u.id = ?
    ''', (user_id,)).fetchone()

    if usuario_actual is None:
        flash('Usuario no encontrado para editar.', 'danger')
        return redirect(url_for('users.listar_usuarios'))

    if request.method == 'POST':
        # 1. Recoger datos del formulario (sin convertir a mayúsculas AQUI)
        apellidos_input = request.form['apellidos'].strip()
        nombre_input = request.form['nombre'].strip()
        modulo_input = request.form['modulo'].strip()  # Ahora viene el NOMBRE del módulo
        genero_input = request.form['genero'].strip()
        observaciones = request.form.get('observaciones', '').strip()  # Observaciones no se tocan

        # 2. Convertir a mayúsculas PARA ALMACENAR Y VALIDAR
        apellidos_upper = apellidos_input.upper()
        nombre_upper = nombre_input.upper()
        genero_upper = genero_input.upper()
        modulo_upper = modulo_input.upper()

        # 3. Validaciones básicas
        if not apellidos_upper:
            errors.append('Los apellidos son obligatorios.')
        if not nombre_upper:
            errors.append('El nombre es obligatorio.')
        if not modulo_upper:
            errors.append('El módulo es obligatorio.')
        if not genero_upper:
            errors.append('El género es obligatorio.')
        elif genero_upper not in ['HOMBRE', 'MUJER', 'OTRO']:  # Validación de género específico
            errors.append('El género debe ser "Hombre", "Mujer" u "Otro".')

        # 4. Validar y manejar el Módulo (Creación si no existe)
        final_id_modulo_for_db = None
        if modulo_upper:  # Si el módulo no está vacío
            # Intentar buscar el módulo por nombre
            existing_modulo = conn.execute("SELECT id FROM modulos WHERE nombre_modulo = ?",
                                           (modulo_upper,)).fetchone()

            if existing_modulo:
                final_id_modulo_for_db = existing_modulo['id']
            else:
                # El módulo no existe, lo insertamos
                try:
                    conn.execute("INSERT INTO modulos (nombre_modulo) VALUES (?)", (modulo_upper,))
                    conn.commit()
                    # Obtener el ID del módulo recién insertado
                    final_id_modulo_for_db = \
                    conn.execute("SELECT id FROM modulos WHERE nombre_modulo = ?", (modulo_upper,)).fetchone()['id']
                    flash(f'Módulo "{modulo_upper}" creado automáticamente.', 'info')
                except sqlite3.IntegrityError as _e:

                    flash(f'Error al crear el módulo "{modulo_upper}": ya existe un módulo con ese nombre.', 'warning')
                    conn.rollback()  # Deshacer si hubo un intento de inserción fallido
                    existing_modulo_after_error = conn.execute("SELECT id FROM modulos WHERE nombre_modulo = ?",
                                                               (modulo_upper,)).fetchone()
                    if existing_modulo_after_error:
                        final_id_modulo_for_db = existing_modulo_after_error['id']
                    else:
                        errors.append(
                            f'No se pudo determinar el ID del módulo "{modulo_upper}" incluso después de un error de inserción. Por favor, intente de nuevo.')
                except Exception as e:
                    errors.append(f'Ocurrió un error inesperado al crear el módulo: {e}')
                    conn.rollback()

        # Asegurarse de que tenemos un ID de módulo válido si el campo de módulo no estaba vacío
        if modulo_upper and final_id_modulo_for_db is None and 'El módulo es obligatorio.' not in errors:
            errors.append(
                'No se pudo determinar un módulo válido para el usuario. Por favor, revise el campo "Módulo".')

        # 5. Si no hay errores, procede con la actualización
        if not errors:
            try:
                conn.execute('''
                    UPDATE usuarios SET
                        apellidos = ?,
                        nombre = ?,
                        id_modulo = ?,
                        genero = ?,
                        observaciones = ?
                    WHERE id = ?
                ''', (apellidos_upper, nombre_upper, final_id_modulo_for_db, genero_upper, observaciones, user_id))
                conn.commit()
                flash('Usuario actualizado correctamente.', 'success')
                return redirect(url_for('users.ver_ficha_usuario', user_id=user_id, next=url_for('users.listar_usuarios')))
            except sqlite3.Error as e:
                flash(f'Error de base de datos al actualizar el usuario: {e}', 'danger')
                conn.rollback()
            except Exception as e:
                flash(f'Ocurrió un error inesperado al actualizar el usuario: {e}', 'danger')
                conn.rollback()
        else:

            for error in errors:
                flash(error, 'danger')

            modulos = conn.execute('SELECT id, nombre_modulo FROM modulos ORDER BY nombre_modulo').fetchall()
            usuario_para_plantilla = {
                'id': user_id,
                'nombre': nombre_input,
                'apellidos': apellidos_input,
                'nombre_modulo': modulo_input,
                'genero': genero_input,
                'observaciones': observaciones
            }
            return render_template('edit_user.html', usuario=usuario_para_plantilla, modulos=modulos)

    modulos = conn.execute('SELECT id, nombre_modulo FROM modulos ORDER BY nombre_modulo').fetchall()

    return render_template('edit_user.html', usuario=usuario_actual, modulos=modulos)


@users_bp.route('/eliminar/<int:user_id>', methods=('POST',))
def eliminar_usuario(user_id):
    conn = get_db()

    user = conn.execute('SELECT nombre, apellidos FROM usuarios WHERE id = ?', (user_id,)).fetchone()

    if user is None:
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('users.listar_usuarios'))

    try:
        active_loans_count = conn.execute(
            'SELECT COUNT(*) FROM prestamos WHERE id_usuario = ? AND fecha_devolucion_real IS NULL',
            (user_id,)
        ).fetchone()[0]

        if active_loans_count > 0:
            flash(
                f'No se puede eliminar a {user["nombre"]} {user["apellidos"]} porque tiene {active_loans_count} préstamos activos.',
                'warning')
            return redirect(url_for('users.listar_usuarios'))

        deleted_inactive_loans = conn.execute(
            'DELETE FROM prestamos WHERE id_usuario = ? AND fecha_devolucion_real IS NOT NULL',
            (user_id,)
        ).rowcount

        current_app.logger.debug(
            f"DEBUG: Se eliminaron {deleted_inactive_loans} préstamos inactivos para el usuario {user_id}.")

        conn.execute('DELETE FROM usuarios WHERE id = ?', (user_id,))
        conn.commit()

        flash(f'Usuario "{user["nombre"]} {user["apellidos"]}" eliminado correctamente.', 'success')
    except sqlite3.Error as e:
        flash(f'Error de base de datos al eliminar usuario: {e}', 'danger')
        conn.rollback()
        current_app.logger.error(f"ERROR: Fallo al eliminar usuario {user_id} o sus préstamos inactivos.",
                                 exc_info=True)
    except Exception as e:
        flash(f'Ocurrió un error inesperado al eliminar usuario: {e}', 'danger')
        conn.rollback()
        current_app.logger.error(f"ERROR: Fallo inesperado al eliminar usuario {user_id}.", exc_info=True)

    return redirect(url_for('users.listar_usuarios'))

@users_bp.route('/ver/<int:user_id>')
def ver_ficha_usuario(user_id):
    conn = get_db()
    cursor = conn.cursor()
    usuario = cursor.execute('''
        SELECT
            u.id,
            u.nombre,
            u.apellidos,
            m.nombre_modulo,
            u.genero,
            u.observaciones, 
            (SELECT COUNT(*) FROM prestamos WHERE id_usuario = u.id AND fecha_devolucion_real IS NULL) AS prestamos_activos
        FROM usuarios AS u
        LEFT JOIN modulos AS m ON u.id_modulo = m.id
        WHERE u.id = ?
    ''', (user_id,)).fetchone()

    if usuario is None:
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('users.listar_usuarios'))

    usuario_dict = dict(usuario)
    if 'observaciones' in usuario_dict:
        obs_value = usuario_dict['observaciones']
        if obs_value == 'None' or obs_value is None or (isinstance(obs_value, str) and obs_value.strip() == ''):
            usuario_dict['observaciones'] = None
    usuario = usuario_dict
    next_url = request.args.get('next')
    return render_template('ver_ficha_usuario.html', usuario=usuario, next_url=next_url)


@users_bp.route('/')
def listar_usuarios():
    """Muestra una lista de todos los usuarios y maneja la búsqueda por ID, nombre o apellido con paginación."""
    conn = get_db()

    query_param = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)  # Obtiene el número de página de la URL

    # Se utiliza la función auxiliar para obtener los datos paginados y filtrados eficientemente
    users_final, total_results, total_pages = _get_filtered_paginated_users(
        conn, query_param, page, PER_PAGE_USERS
    )

    # Se renderiza la plantilla principal, pasando todos los datos necesarios para la paginación
    return render_template(
        'users_list.html',
        users=users_final,
        q=query_param,
        page=page,
        per_page=PER_PAGE_USERS,
        total_pages=total_pages,
        total_results=total_results,
        base_ajax_url='users.listar_usuarios_ajax'
    )


@users_bp.route('/list_ajax')
def listar_usuarios_ajax():
    conn = get_db()
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    # Se utiliza la función auxiliar para obtener los datos paginados
    users, total_results, total_pages = _get_filtered_paginated_users(
        conn, search_query, page, PER_PAGE_USERS
    )

    # Renderiza solo las filas de la tabla usando la plantilla parcial para el listado general
    table_rows_html = render_template(
        '_users_table_rows_general.html',  # Esta plantilla debe tener los botones de acción (Ver, Editar, Eliminar)
        users=users
    )

    # Renderiza los controles de paginación usando su plantilla parcial
    pagination_html = render_template(
        '_pagination_controls_users.html',
        page=page,
        total_pages=total_pages,
        q=search_query,
        base_ajax_url='users.listar_usuarios_ajax'
        # La URL base para los enlaces de paginación apunta a esta misma ruta AJAX
    )

    # Devolver una respuesta JSON con los fragmentos HTML y otros datos
    return jsonify({
        'table_rows': table_rows_html,
        'pagination_html': pagination_html,
        'total_results': total_results
    })

@users_bp.route('/select')
def listar_users_select():
    conn = get_db()
    query_param = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    # Se utiliza la función auxiliar para obtener los datos paginados y filtrados
    users_final, total_results, total_pages = _get_filtered_paginated_users(
        conn, query_param, page, PER_PAGE_USERS
    )

    return render_template(
        'listar_users_select.html',
        users=users_final,
        q=query_param,
        page=page,
        per_page=PER_PAGE_USERS,
        total_pages=total_pages,
        total_results=total_results,
        base_ajax_url='users.listar_users_ajax_select'
    )


@users_bp.route('/select_ajax')
def listar_users_ajax_select():
    conn = get_db()
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    users, total_results, total_pages = _get_filtered_paginated_users(
        conn, search_query, page, PER_PAGE_USERS
    )

    # Renderiza solo las filas de la tabla usando la plantilla parcial para filas seleccionables
    table_rows_html = render_template(
        '_users_table_rows.html',
        users=users
    )

    pagination_html = render_template(
        '_pagination_controls_users.html',
        page=page,
        total_pages=total_pages,
        q=search_query,
        base_ajax_url='users.listar_users_ajax_select'
    )

    return jsonify({
        'table_rows': table_rows_html,
        'pagination_html': pagination_html,
        'total_results': total_results
    })
