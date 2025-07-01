# Importar la función get_db desde el módulo database
from database import get_db
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify

# Importar el nuevo UserService
from .user_service import UserService

users_bp = Blueprint('users', __name__, template_folder='templates')

# Instanciar el UserService
user_service = UserService(get_db)


@users_bp.route('/')
def listar_usuarios():
    data = user_service.get_paginated_users(request.args.to_dict())
    data['base_listing_endpoint'] = 'users.listar_usuarios'

    # Se renderiza la plantilla principal, pasando todos los datos necesarios
    return render_template(
        'users_list.html',
        **data
    )

@users_bp.route('/list_ajax')
def listar_usuarios_ajax():
    # Se pasan todos los request.args directamente al servicio
    data = user_service.get_paginated_users(request.args.to_dict())

    # Renderiza solo las filas de la tabla usando la plantilla parcial para el listado general
    table_rows_html = render_template(
        '_users_table_rows_general.html',
        users=data['usuarios'],
        q=data['q'],
        page=data['page'],
        sort_by=data.get('sort_by', 'id'),
        sort_direction=data.get('sort_direction', 'ASC'),
        base_listing_endpoint='users.listar_usuarios'
    )

    # Renderiza los controles de paginación usando su plantilla parcial
    pagination_html = render_template(
        '_pagination_controls_users.html',
        page=data['page'],
        total_pages=data['total_pages'],
        q=data['q'],
        sort_by=data.get('sort_by', 'id'), # Pasar el parámetro de ordenación
        sort_direction=data.get('sort_direction', 'ASC'), # Pasar la dirección de ordenación
        base_ajax_url='users.listar_usuarios_ajax'
    )

    # Devolver una respuesta JSON con los fragmentos HTML y otros datos
    return jsonify({
        'table_rows': table_rows_html,
        'pagination_html': pagination_html,
        'total_results': data['total_results']
    })

@users_bp.route('/select')
def listar_users_select():
    # Se pasan todos los request.args directamente al servicio
    data = user_service.get_paginated_users(request.args.to_dict())
    data['base_listing_endpoint'] = 'users.listar_users_select'

    return render_template(
        'listar_users_select.html',
        **data
    )

@users_bp.route('/select_ajax')
def listar_users_ajax_select():
    data = user_service.get_paginated_users(request.args.to_dict())

    # Renderiza solo las filas de la tabla usando la plantilla parcial para filas seleccionables
    table_rows_html = render_template(
        '_users_table_rows.html',
        users=data['usuarios'],
        q=data['q'],
        page=data['page'],
        sort_by=data.get('sort_by', 'id'),
        sort_direction=data.get('sort_direction', 'ASC'),
        # Endpoint correcto al que regresar desde 'Ver Ficha' en esta vista
        base_listing_endpoint='users.listar_users_select'
    )

    pagination_html = render_template(
        '_pagination_controls_users.html',
        page=data['page'],
        total_pages=data['total_pages'],
        q=data['q'],
        sort_by=data.get('sort_by', 'id'),
        sort_direction=data.get('sort_direction', 'ASC'),
        base_ajax_url='users.listar_users_ajax_select'
    )

    return jsonify({
        'table_rows': table_rows_html,
        'pagination_html': pagination_html,
        'total_results': data['total_results'],
        'current_state_url': url_for('users.listar_users_select', **data)
    })


@users_bp.route('/anadir', methods=('GET', 'POST'))
def anadir_usuario():
    modulos = user_service.get_modulos()
    generos_existentes = user_service.get_existing_generos()

    # Recuperar datos del formulario para rellenar si hay errores (lógica original)
    user_id_input = request.form.get('user_id', '').strip()
    apellidos = request.form.get('apellidos', '').strip().upper()
    nombre = request.form.get('nombre', '').strip().upper()
    id_modulo_input = request.form.get('id_modulo', '').strip()
    genero_input = request.form.get('genero', '').strip().upper()
    observaciones = request.form.get('observaciones', '').strip()


    if request.method == 'POST':
        error_message = user_service.add_user(request.form.to_dict())
        if error_message:
            flash(error_message, 'danger')
            # Recargar módulos y géneros para el renderizado del formulario con errores (lógica original)
            modulos = user_service.get_modulos()
            generos_existentes = user_service.get_existing_generos()
            return render_template('add_user.html',
                                   modulos=modulos,
                                   generos_existentes=generos_existentes,
                                   user_id_input=user_id_input,
                                   apellidos=apellidos,
                                   nombre=nombre,
                                   id_modulo_input=id_modulo_input,
                                   genero_input=genero_input,
                                   observaciones=observaciones)
        else:
            flash('Usuario añadido correctamente.', 'success')
            return redirect(url_for('users.listar_usuarios'))

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
    next_url = request.values.get('next')
    modulos = user_service.get_modulos()

    if request.method == 'POST':
        error_message = user_service.update_user(user_id, request.form.to_dict())
        if error_message:
            flash(error_message, 'danger')
            # Reconstruir datos del formulario si hay error (lógica original)
            usuario_para_plantilla = {
                'id': user_id,
                'nombre': request.form.get('nombre', ''),
                'apellidos': request.form.get('apellidos', ''),
                'nombre_modulo': request.form.get('modulo', ''),
                'genero': request.form.get('genero', ''),
                'observaciones': request.form.get('observaciones', '')
            }
            return render_template('edit_user.html', usuario=usuario_para_plantilla, modulos=modulos, next_url=next_url)
        else:
            flash('Usuario actualizado correctamente.', 'success')
            if next_url:
                return redirect(next_url)
            return redirect(url_for('users.ver_ficha_usuario', user_id=user_id, next=next_url or url_for('users.listar_usuarios')))
    else:
        usuario_actual = user_service.get_user_for_edit(user_id)
        if usuario_actual is None:
            flash('Usuario no encontrado para editar.', 'danger')
            return redirect(url_for('users.listar_usuarios'))
        return render_template('edit_user.html', usuario=usuario_actual, modulos=modulos, next_url=next_url)


@users_bp.route('/eliminar/<int:user_id>', methods=('POST',))
def eliminar_usuario(user_id):
    next_url = request.values.get('next')

    error_message = user_service.delete_user(user_id)
    if error_message:
        flash(error_message, 'danger')
        # Si hay error, volvemos a la ficha del usuario, preservando next_url si existe
        return redirect(url_for('users.ver_ficha_usuario', user_id=user_id, next=next_url))
    else:
        flash(f'Usuario eliminado correctamente.', 'success')
        if next_url:
            return redirect(next_url)
        return redirect(url_for('users.listar_usuarios'))


@users_bp.route('/ver/<int:user_id>')
def ver_ficha_usuario(user_id):
    usuario = user_service.get_user_details(user_id)
    if usuario is None:
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('users.listar_usuarios'))
    next_url = request.args.get('next', url_for('users.listar_usuarios'))
    return render_template('ver_ficha_usuario.html', usuario=usuario, next_url=next_url)


# Rutas de autocompletado
@users_bp.route('/autocomplete/users_name')
def autocomplete_users_name():
    term = request.args.get('term', '').strip()
    suggestions = user_service.autocomplete_users_name(term)
    return jsonify(suggestions)

@users_bp.route('/autocomplete/modulos')
def autocomplete_modulos():
    term = request.args.get('term', '').strip()
    suggestions = user_service.autocomplete_modulos(term)
    return jsonify(suggestions)
