# blueprints/loans/routes.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
import sqlite3
from datetime import date, timedelta
from datetime import datetime
from database import get_db
import math

loans_bp = Blueprint('loans', __name__, template_folder='templates')

PER_PAGE = 10

def _get_filtered_paginated_prestamos(conn, search_query, page, per_page):
    base_query = '''
        SELECT
            p.id,
            l.titulo AS libro_titulo,
            u.nombre || ' ' || u.apellidos AS usuario_nombre_completo,
            p.fecha_prestamo,
            p.fecha_devolucion_estimada,
            p.fecha_devolucion_real,
            p.estado_prestamo
        FROM prestamos AS p
        JOIN usuarios AS u ON p.id_usuario = u.id
        JOIN libros AS l ON p.id_libro = l.id
        JOIN autores AS a ON l.id_autor_principal = a.id
    '''

    # Listas para almacenar los parámetros de la consulta y las condiciones WHERE
    params = []
    where_clauses = []
    if search_query:
        search_pattern = f'%{search_query}%'

        where_clauses.append("remove_accents(u.nombre) LIKE remove_accents(?)")
        params.append(search_pattern)

        where_clauses.append("remove_accents(u.apellidos) LIKE remove_accents(?)")
        params.append(search_pattern)

        where_clauses.append("remove_accents(l.titulo) LIKE remove_accents(?)")
        params.append(search_pattern)

        where_clauses.append("remove_accents(a.nombre_autor) LIKE remove_accents(?)")
        params.append(search_pattern)

    # Si hay condiciones WHERE, las unimos con OR
    if where_clauses:
        base_query += " WHERE " + " OR ".join(where_clauses)

    count_query = "SELECT COUNT(*) FROM prestamos AS p JOIN usuarios AS u ON p.id_usuario = u.id JOIN libros AS l ON p.id_libro = l.id JOIN autores AS a ON l.id_autor_principal = a.id"
    if where_clauses:
        count_query += " WHERE " + " OR ".join(where_clauses)

    total_results = conn.execute(count_query, params).fetchone()[0]

    # Calcular el número total de páginas. Usamos math.ceil para redondear hacia arriba.
    total_pages = math.ceil(total_results / per_page) if total_results > 0 else 1

    # Asegurarse de que el número de página sea válido (no menor de 1, no mayor que total_pages)
    page = max(1, min(page, max(1, total_pages)))

    # Ordenación de los resultados (los más recientes primero)
    base_query += " ORDER BY p.fecha_prestamo DESC"
    base_query += " LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])

    # Ejecutar la consulta principal y obtener los préstamos de la página actual
    prestamos = conn.execute(base_query, params).fetchall()

    return prestamos, total_results, total_pages


@loans_bp.route('/')
def listar_prestamos():
    conn = get_db()
    today_date = date.today().isoformat()

    # Primero, actualiza el estado de los préstamos vencidos
    conn.execute('''
        UPDATE prestamos
        SET estado_prestamo = 'Vencido'
        WHERE fecha_devolucion_real IS NULL
        AND fecha_devolucion_estimada IS NOT NULL
        AND fecha_devolucion_estimada < ?
        AND estado_prestamo != 'Vencido';
    ''', (today_date,))
    conn.commit()

    # Obtener el término de búsqueda y el número de página de la solicitud
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    # Utilizar la función auxiliar para obtener los datos
    prestamos, total_results, total_pages = _get_filtered_paginated_prestamos(
        conn, search_query, page, PER_PAGE
    )

    # Renderizar la plantilla principal (para la carga inicial de la página)
    return render_template(
        'listar_prestamos.html',
        prestamos=prestamos,
        q=search_query,
        today_date=today_date,
        page=page,
        per_page=PER_PAGE,
        total_pages=total_pages,
        total_results=total_results
    )


@loans_bp.route('/ajax')
def listar_prestamos_ajax():
    conn = get_db()
    today_date = date.today().isoformat()

    # Obtener el término de búsqueda y el número de página de la solicitud AJAX
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    # Utilizar la función auxiliar para obtener los datos
    prestamos, total_results, total_pages = _get_filtered_paginated_prestamos(
        conn, search_query, page, PER_PAGE
    )

    # Renderizar solo el fragmento HTML de las filas de la tabla
    table_rows_html = render_template(
        '_prestamos_table_rows.html',
        prestamos=prestamos,
        today_date=today_date
    )

    # Renderizar solo el fragmento HTML de los controles de paginación
    # Este se cargará en el <ul> de paginación existente en el cliente.
    pagination_html = render_template(
        '_pagination_controls.html',
        page=page,
        total_pages=total_pages,
        q=search_query
    )

    # Devolver una respuesta JSON con los fragmentos HTML y otros datos
    return jsonify({
        'table_rows': table_rows_html,
        'pagination_html': pagination_html,
        'total_results': total_results
    })


@loans_bp.route('/realizar_prestamo', methods=['GET', 'POST'])
def realizar_prestamo():
    conn = get_db()
    errors = []
    cursor = conn.cursor()

    # today_date se usa y se pasa a la plantilla
    today_date = date.today().isoformat()
    estimated_return_date = (date.today() + timedelta(days=15)).isoformat()

    usuario_preseleccionado = None
    id_usuario_param = request.args.get('id_usuario_seleccionado')

    if id_usuario_param:
        user_details = cursor.execute("SELECT id, nombre, apellidos FROM usuarios WHERE id = ?",
                                      (id_usuario_param,)).fetchone()
        if user_details:
            usuario_preseleccionado = {
                'id': user_details['id'],
                'nombre': user_details['nombre'],
                'apellidos': user_details['apellidos']
            }

    libro_preseleccionado = None
    id_libro_param = request.args.get('id_libro_seleccionado')

    if id_libro_param:
        libro_details = cursor.execute("SELECT id, titulo FROM libros WHERE id = ?", (id_libro_param,)).fetchone()
        if libro_details:
            libro_preseleccionado = {
                'id': libro_details['id'],
                'titulo': libro_details['titulo']
            }

    if request.method == 'POST':
        id_prestamo_input = request.form.get('id_prestamo')
        id_prestamo_to_insert = None

        if id_prestamo_input:
            try:
                id_prestamo_to_insert = int(id_prestamo_input)
                if id_prestamo_to_insert <= 0:
                    errors.append('El número de préstamo debe ser un entero positivo.')
                    id_prestamo_to_insert = None
                else:
                    existing_loan = cursor.execute("SELECT id FROM prestamos WHERE id = ?",
                                                   (id_prestamo_to_insert,)).fetchone()
                    if existing_loan:
                        errors.append(
                            f'El número de préstamo "{id_prestamo_to_insert}" ya existe. Por favor, elige otro o déjalo en blanco para asignación automática.')
                        id_prestamo_to_insert = None
            except ValueError:
                errors.append('El número de préstamo debe ser un número entero válido.')
                id_prestamo_to_insert = None

        id_usuario = request.form.get('id_usuario')
        id_libro = request.form.get('id_libro')
        fecha_prestamo_form = request.form.get('fecha_prestamo')
        fecha_devolucion_estimada_form = request.form.get('fecha_devolucion_estimada')

        if not id_usuario:
            errors.append('Debes seleccionar un usuario.')
        if not id_libro:
            errors.append('Debes seleccionar un libro.')
        if not fecha_prestamo_form:
            errors.append('La fecha de préstamo es obligatoria.')
        if not fecha_devolucion_estimada_form:
            errors.append('La fecha de devolución estimada es obligatoria.')

        try:
            prestamo_date = date.fromisoformat(fecha_prestamo_form)
            devolucion_estimada_date = date.fromisoformat(fecha_devolucion_estimada_form)
        except ValueError:
            errors.append('Formato de fecha inválido. Usa Jamboree-MM-DD.')
            prestamo_date = None
            devolucion_estimada_date = None

        if prestamo_date and devolucion_estimada_date and prestamo_date > devolucion_estimada_date:
            errors.append('La fecha de devolución estimada no puede ser anterior a la fecha de préstamo.')

        if not errors:
            try:
                libro_disponible = cursor.execute("SELECT disponible FROM libros WHERE id = ?", (id_libro,)).fetchone()
                if not libro_disponible or libro_disponible['disponible'] != 'Si':
                    errors.append('El libro seleccionado no está disponible para préstamo.')

                if not errors:
                    libro_info_stats = cursor.execute("""
                        SELECT l.titulo, a.nombre_autor
                        FROM libros l
                        LEFT JOIN autores a ON l.id_autor_principal = a.id
                        WHERE l.id = ?
                    """, (id_libro,)).fetchone()

                    usuario_info_stats = cursor.execute("""
                        SELECT u.genero, m.nombre_modulo
                        FROM usuarios u
                        LEFT JOIN modulos m ON u.id_modulo = m.id
                        WHERE u.id = ?
                    """, (id_usuario,)).fetchone()

                    if id_prestamo_to_insert is not None:
                        prestamo_id_generado = id_prestamo_to_insert
                        cursor.execute('''
                            INSERT INTO prestamos (id, id_usuario, id_libro, fecha_prestamo, fecha_devolucion_estimada, fecha_devolucion_real, estado_prestamo)
                            VALUES (?, ?, ?, ?, ?, NULL, ?)
                        ''', (
                            id_prestamo_to_insert, id_usuario, id_libro, fecha_prestamo_form,
                            fecha_devolucion_estimada_form,
                            'Prestado'))
                    else:
                        cursor.execute('''
                            INSERT INTO prestamos (id_usuario, id_libro, fecha_prestamo, fecha_devolucion_estimada, fecha_devolucion_real, estado_prestamo)
                            VALUES (?, ?, ?, ?, NULL, ?)
                        ''', (id_usuario, id_libro, fecha_prestamo_form, fecha_devolucion_estimada_form,
                              'Prestado'))
                        prestamo_id_generado = cursor.lastrowid

                    cursor.execute("UPDATE libros SET disponible = 'No' WHERE id = ?", (id_libro,))
                    cursor.execute("UPDATE usuarios SET prestamos_activos = prestamos_activos + 1 WHERE id = ?",
                                   (id_usuario,))

                    cursor.execute("""
                        INSERT INTO estadisticas (
                            id_prestamo,
                            titulo_libro,
                            nombre_autor,
                            genero_usuario_historial,
                            modulo_usuario_historial,
                            fecha_prestamo
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        prestamo_id_generado,
                        libro_info_stats['titulo'] if libro_info_stats else 'Desconocido',
                        libro_info_stats['nombre_autor'] if libro_info_stats and libro_info_stats[
                            'nombre_autor'] else 'Desconocido',
                        usuario_info_stats['genero'] if usuario_info_stats else 'Desconocido',
                        usuario_info_stats['nombre_modulo'] if usuario_info_stats and usuario_info_stats[
                            'nombre_modulo'] else 'Desconocido',
                        fecha_prestamo_form
                    ))

                    conn.commit()
                    flash('Préstamo realizado correctamente y estadística registrada.', 'success')
                    return redirect(url_for('loans.listar_prestamos'))
            except sqlite3.Error as e:
                flash(f'Error de base de datos al realizar el préstamo: {e}', 'danger')
                conn.rollback()

            except Exception as e:
                flash(f'Ocurrió un error inesperado al realizar el préstamo: {e}', 'danger')
                conn.rollback()

        else:
            if request.form.get('id_usuario'):
                if not usuario_preseleccionado or (
                        usuario_preseleccionado and str(usuario_preseleccionado['id']) != request.form.get(
                    'id_usuario')):
                    temp_user_details = cursor.execute("SELECT id, nombre, apellidos FROM usuarios WHERE id = ?",
                                                       (request.form.get('id_usuario'),)).fetchone()
                    if temp_user_details:
                        usuario_preseleccionado = {
                            'id': temp_user_details['id'],
                            'nombre': temp_user_details['nombre'],
                            'apellidos': temp_user_details['apellidos']
                        }
            if request.form.get('id_libro'):
                if not libro_preseleccionado or (
                        libro_preseleccionado and str(libro_preseleccionado['id']) != request.form.get('id_libro')):
                    temp_libro_details = cursor.execute("SELECT id, titulo FROM libros WHERE id = ?",
                                                        (request.form.get('id_libro'),)).fetchone()
                    if temp_libro_details:
                        libro_preseleccionado = {
                            'id': temp_libro_details['id'],
                            'titulo': temp_libro_details['titulo']
                        }

            for error in errors:
                flash(error, 'danger')

    libros = cursor.execute("SELECT id, titulo FROM libros WHERE disponible = 'Si' ORDER BY titulo;").fetchall()
    usuarios = cursor.execute("SELECT id, nombre, apellidos FROM usuarios ORDER BY nombre, apellidos;").fetchall()

    return render_template('realizar_prestamo.html',
                           libros=libros,
                           usuarios=usuarios,
                           today_date=today_date,
                           estimated_return_date=estimated_return_date,
                           usuario_preseleccionado=usuario_preseleccionado,
                           libro_preseleccionado=libro_preseleccionado,
                           errors=errors
                           )


@loans_bp.route('/devolver_prestamo/<int:id_prestamo>', methods=['POST'])
def devolver_prestamo(id_prestamo):
    conn = get_db()
    cursor = conn.cursor()

    try:
        prestamo_info = cursor.execute('SELECT id_libro, id_usuario, fecha_devolucion_real FROM prestamos WHERE id = ?',
                                       (id_prestamo,)).fetchone()

        if prestamo_info is None:
            flash('Préstamo no encontrado.', 'danger')
            return redirect(url_for('loans.listar_prestamos'))

        if prestamo_info['fecha_devolucion_real'] is not None:
            flash('Este préstamo ya ha sido devuelto.', 'warning')
            return redirect(url_for('loans.listar_prestamos'))

        id_libro = prestamo_info['id_libro']
        id_usuario = prestamo_info['id_usuario']
        fecha_devolucion_actual = datetime.now().strftime('%Y-%m-%d')

        # 2. Actualizar el registro del préstamo: fecha_devolucion_real y estado_prestamo = 'Devuelto'
        cursor.execute('''
            UPDATE prestamos
            SET fecha_devolucion_real = ?, estado_prestamo = 'Devuelto'
            WHERE id = ?
        ''', (fecha_devolucion_actual, id_prestamo))

        # 3. Actualizar el estado del libro (disponible = 'Si')
        cursor.execute('''
            UPDATE libros
            SET disponible = 'Si'
            WHERE id = ?
        ''', (id_libro,))


        cursor.execute('''
            UPDATE usuarios
            SET prestamos_activos = prestamos_activos - 1
            WHERE id = ?
        ''', (id_usuario,))

        conn.commit()
        flash(
            'Préstamo devuelto con éxito. El libro ha sido marcado como disponible y los préstamos activos del usuario actualizados.',
            'success')

    except Exception as e:
        conn.rollback()
        flash(f'Error al devolver el préstamo: {e}', 'danger')

    return redirect(url_for('loans.listar_prestamos'))


@loans_bp.route('/ver_ficha_prestamo/<int:id_prestamo>')
def ver_ficha_prestamo(id_prestamo):
    conn = get_db()

    prestamo = conn.execute('''
        SELECT
            p.id,
            p.id_libro,
            l.titulo AS libro_titulo,
            a.nombre_autor AS libro_autor,
            l.isbn AS libro_isbn,
            p.id_usuario,
            u.nombre AS usuario_nombre,
            u.apellidos AS usuario_apellidos,
            m.nombre_modulo AS usuario_modulo_nombre,
            p.fecha_prestamo,
            p.fecha_devolucion_estimada,
            p.fecha_devolucion_real,
            p.estado_prestamo
        FROM prestamos AS p
        JOIN usuarios AS u ON p.id_usuario = u.id
        JOIN libros AS l ON p.id_libro = l.id        
        JOIN autores AS a ON l.id_autor_principal = a.id
        JOIN modulos AS m ON u.id_modulo = m.id
        WHERE p.id = ?
    ''', (id_prestamo,)).fetchone()

    if prestamo is None:
        flash('Ficha de préstamo no encontrada.', 'danger')
        return redirect(url_for('loans.listar_prestamos'))

    return render_template('ver_ficha_prestamo.html', prestamo=prestamo)


@loans_bp.route('/eliminar_prestamo/<int:id_prestamo>', methods=['POST'])
def eliminar_prestamo(id_prestamo):
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 1. Obtener la información del préstamo para verificar su estado actual
        prestamo_info = cursor.execute('SELECT id_libro, id_usuario, fecha_devolucion_real FROM prestamos WHERE id = ?',
                                       (id_prestamo,)).fetchone()

        if prestamo_info is None:
            flash('Préstamo no encontrado.', 'danger')
            return redirect(url_for('loans.listar_prestamos'))

        id_libro = prestamo_info['id_libro']
        id_usuario = prestamo_info['id_usuario']
        fecha_devolucion_real = prestamo_info['fecha_devolucion_real']

        # 2. Si el préstamo NO ha sido devuelto (fecha_devolucion_real es NULL)
        if fecha_devolucion_real is None:
            cursor.execute('''
                UPDATE libros
                SET disponible = 'Si'
                WHERE id = ?
            ''', (id_libro,))


            cursor.execute('''
                UPDATE usuarios
                SET prestamos_activos = prestamos_activos - 1
                WHERE id = ?
            ''', (id_usuario,))

            flash_message = f'Préstamo {id_prestamo} eliminado y libro marcado como disponible. El contador de préstamos activos del usuario ha disminuido.'
            flash_category = 'success'
        else:
            flash_message = f'Préstamo {id_prestamo} eliminado. Ya había sido devuelto, por lo que no se actualizó el libro ni el contador del usuario.'
            flash_category = 'info'

        # 3. Eliminar el registro del préstamo de la tabla 'prestamos'
        cursor.execute('DELETE FROM prestamos WHERE id = ?', (id_prestamo,))

        conn.commit()
        flash(flash_message, flash_category)

    except Exception as e:
        conn.rollback()
        flash(f'Error al eliminar el préstamo {id_prestamo}: {e}', 'danger')

    return redirect(url_for('loans.listar_prestamos'))

