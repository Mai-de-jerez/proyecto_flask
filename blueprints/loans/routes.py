# blueprints/loans/routes.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from datetime import date
from database import get_db
from .loan_service import LoanService
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

loans_bp = Blueprint('loans', __name__, template_folder='templates')

# Instanciar el LoanService
loan_service = LoanService(get_db)

# Filtro personalizado para URL (como en books y users)
@loans_bp.app_template_filter('url_set_param')
def url_set_param_filter(url, param_name, param_value):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query, keep_blank_values=True)

    query_params[param_name] = [param_value]

    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed_url._replace(query=new_query))

@loans_bp.route('/')
def listar_prestamos():
    data = loan_service.get_paginated_loans(request.args.to_dict())
    today_date = date.today().isoformat()
    data['base_listing_endpoint'] = 'loans.listar_prestamos'
    return render_template(
        'listar_prestamos.html',
        today_date=today_date,
        **data
    )


@loans_bp.route('/ajax')
def listar_prestamos_ajax():
    # Pasar todos los request.args directamente al servicio
    data = loan_service.get_paginated_loans(request.args.to_dict())
    today_date = date.today().isoformat()

    # Renderizar solo el fragmento HTML de las filas de la tabla
    table_rows_html = render_template(
        '_prestamos_table_rows.html',
        prestamos=data['prestamos'],
        today_date=today_date,
        q=data['q'],
        page=data['page'],
        filter_status=data['filter_status'],
        sort_by=data['sort_by'],
        sort_direction=data['sort_direction'],
        base_listing_endpoint='loans.listar_prestamos'
    )

    # Renderizar solo el fragmento HTML de los controles de paginación
    # Asegurarse de pasar todos los parámetros de filtro y ordenación para que la paginación los mantenga
    pagination_html = render_template(
        '_pagination_controls.html',
        page=data['page'],
        total_pages=data['total_pages'],
        q=data['q'],
        filter_status=data['filter_status'],
        sort_by=data['sort_by'],
        sort_direction=data['sort_direction'],
        base_ajax_url='loans.listar_prestamos_ajax'
    )

    # Devolver una respuesta JSON con los fragmentos HTML y otros datos
    return jsonify({
        'table_rows': table_rows_html,
        'pagination_html': pagination_html,
        'total_results': data['total_results']
    })


@loans_bp.route('/realizar_prestamo', methods=['GET', 'POST'])
def realizar_prestamo():
    errors = []
    form_initial_data = loan_service.get_loan_form_initial_data(request.args.to_dict())

    if request.method == 'POST':
        error_message = loan_service.add_loan(request.form.to_dict())
        if error_message:
            flash(error_message, 'danger')
            errors.append(error_message)
            reconstructed_form_data = {
                'id_prestamo': request.form.get('id_prestamo', ''),
                'id_usuario': request.form.get('id_usuario', ''),
                'usuario_display': request.form.get('usuario_display', ''),
                'id_libro': request.form.get('id_libro', ''),
                'libro_display': request.form.get('libro_display', ''),
                'fecha_prestamo': request.form.get('fecha_prestamo', form_initial_data['today_date']),
                'fecha_devolucion_estimada': request.form.get('fecha_devolucion_estimada', form_initial_data['estimated_return_date']),
            }
            # Si el usuario y/o libro vienen en el form (y no eran válidos), intentar preseleccionarlos de nuevo
            if reconstructed_form_data['id_usuario']:
                temp_user_details = loan_service.get_loan_form_initial_data({'id_usuario_seleccionado': reconstructed_form_data['id_usuario']})['usuario_preseleccionado']
                if temp_user_details:
                    form_initial_data['usuario_preseleccionado'] = temp_user_details
            if reconstructed_form_data['id_libro']:
                temp_libro_details = loan_service.get_loan_form_initial_data({'id_libro_seleccionado': reconstructed_form_data['id_libro']})['libro_preseleccionado']
                if temp_libro_details:
                    form_initial_data['libro_preseleccionado'] = temp_libro_details

            return render_template('realizar_prestamo.html',
                                   errors=errors, # Pasamos los errores explícitamente si queremos manejarlos en la plantilla
                                   **form_initial_data, # Datos preseleccionados
                                   **reconstructed_form_data # Datos del formulario si hay error
                                   )
        else:
            flash('Préstamo realizado correctamente y estadística registrada.', 'success')
            return redirect(url_for('loans.listar_prestamos'))

    # Si es GET, simplemente renderiza el formulario con los datos iniciales (incluidos preseleccionados)
    return render_template('realizar_prestamo.html',
                           errors=errors,
                           **form_initial_data # Esto incluye today_date, estimated_return_date, usuario_preseleccionado, libro_preseleccionado
                           )


@loans_bp.route('/devolver_prestamo/<int:id_prestamo>', methods=['POST'])
def devolver_prestamo(id_prestamo):
    next_url = request.args.get('next')
    error_message = loan_service.return_loan(id_prestamo)
    if error_message:
        flash(error_message, 'danger')
    else:
        flash('Préstamo devuelto con éxito. El libro ha sido marcado como disponible y los préstamos activos del usuario actualizados.', 'success')
    if next_url:
        return redirect(next_url)
    return redirect(url_for('loans.listar_prestamos'))


@loans_bp.route('/ver_ficha_prestamo/<int:id_prestamo>')
def ver_ficha_prestamo(id_prestamo):
    next_url = request.args.get('next', url_for('loans.listar_prestamos'))
    prestamo = loan_service.get_loan_details(id_prestamo)
    if prestamo is None:
        flash('Ficha de préstamo no encontrada.', 'danger')
        return redirect(url_for('loans.listar_prestamos'))
    return render_template('ver_ficha_prestamo.html', prestamo=prestamo, next_url=next_url)


@loans_bp.route('/eliminar_prestamo/<int:id_prestamo>', methods=['POST'])
def eliminar_prestamo(id_prestamo):
    next_url = request.args.get('next')
    error_message = loan_service.delete_loan(id_prestamo)
    if error_message:
        flash(error_message, 'danger')
        # Determinar el mensaje flash y la categoría según el resultado del servicio
        if "No se puede eliminar" in error_message: # Si el error es por tener préstamos activos
            flash_message = error_message
            flash_category = 'warning'
        else:
            flash_message = f'Error al eliminar el préstamo {id_prestamo}: {error_message}'
            flash_category = 'danger'
        flash(flash_message, flash_category)

    else:
        flash(f'Préstamo {id_prestamo} eliminado correctamente.', 'success')

    if next_url:
        return redirect(next_url)
    return redirect(url_for('loans.listar_prestamos'))

