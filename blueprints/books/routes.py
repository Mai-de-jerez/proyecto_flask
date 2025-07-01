# talegoTK_Flask/blueprints/books/routes.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from database import get_db
from .book_service import BookService
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

books_bp = Blueprint('books', __name__, template_folder='templates')
book_service = BookService(get_db)


@books_bp.app_template_filter('url_set_param')
def url_set_param_filter(url, param_name, param_value):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query, keep_blank_values=True)

    query_params[param_name] = [param_value]

    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed_url._replace(query=new_query))


@books_bp.route('/')
def listar_libros():
    data = book_service.get_paginated_books(request.args.to_dict(), mode='list')
    data['base_listing_endpoint'] = 'books.listar_libros'
    return render_template('libros_list.html', **data)

@books_bp.route('/list_ajax')
def listar_libros_ajax():
    data = book_service.get_paginated_books(request.args.to_dict(), mode='list')

    table_rows_html = render_template(
        '_libros_table_rows.html',
        libros=data['libros'],
        # Pasar explícitamente los parámetros para que el enlace 'Ver Ficha' pueda reconstruir la URL de retorno
        q=data['q'],
        page=data['page'],
        sort_by=data['sort_by'],
        sort_direction=data['sort_direction'],
        filter_material_type=data['filter_material_type'],
        base_listing_endpoint='books.listar_libros'
    )

    pagination_html = render_template(
        '_pagination_controls_books.html',
        page=data['page'],
        total_pages=data['total_pages'],
        q=data['q'],
        base_ajax_url=data['base_ajax_url'],
        sort_by=data['sort_by'],
        sort_direction=data['sort_direction'],
        filter_material_type=data['filter_material_type']
    )
    return jsonify({
        'table_rows': table_rows_html,
        'pagination_html': pagination_html,
        'total_results': data['total_results']
    })

@books_bp.route('/listar_libros_select', methods=['GET'])
def listar_libros_select():
    all_args = request.args.to_dict()
    data = book_service.get_paginated_books(all_args, mode='select')
    all_url_params_for_js = urlencode(all_args, doseq=True)
    data['base_listing_endpoint'] = 'books.listar_libros_select'
    data.pop('select_mode', None)

    return render_template(
        'libros_list_select.html',
        select_mode=True,
        current_page_url=request.full_path,
        all_url_params_for_js=all_url_params_for_js,
        **data
    )

@books_bp.route('/select_ajax', methods=['GET'])
def listar_libros_select_ajax():
    all_args = request.args.to_dict()
    data = book_service.get_paginated_books(all_args, mode='select')

    current_page_url = url_for('books.listar_libros_select', **all_args)

    table_rows_html = render_template(
        '_libros_select_table_rows.html',
        libros=data['libros'],
        current_page_url=current_page_url,  # Esta URL ya contendrá todos los parámetros de `all_args`
        q=data['q'],
        page=data['page'],
        sort_by=data['sort_by'],
        sort_direction=data['sort_direction'],
        filter_material_type=data['filter_material_type'],
        base_listing_endpoint='books.listar_libros_select'
    )

    pagination_html = render_template(
        '_pagination_controls_books.html',
        page=data['page'],
        total_pages=data['total_pages'],
        q=data['q'],
        base_ajax_url=data['base_ajax_url'],
        all_url_params=all_args,
        sort_by=data['sort_by'],
        sort_direction=data['sort_direction'],
        filter_material_type=data['filter_material_type']
    )
    return jsonify({
        'table_rows': table_rows_html,
        'pagination_html': pagination_html,
        'total_results': data['total_results'],
        'current_state_url': current_page_url
    })


@books_bp.route('/nuevo', methods=('GET', 'POST'))
def anadir_libro():
    if request.method == 'POST':
        error_message = book_service.add_book(request.form.to_dict())
        if error_message:
            flash(error_message, 'danger')
            return render_template('anadir_libro.html', **request.form.to_dict())
        else:
            flash('Libro añadido correctamente.', 'success')
            return redirect(url_for('books.listar_libros'))
    return render_template('anadir_libro.html')


@books_bp.route('/editar/<int:book_id>', methods=('GET', 'POST'))
def editar_libro(book_id):
    next_url = request.args.get('next')

    if request.method == 'POST':
        error_message = book_service.update_book(book_id, request.form.to_dict())
        if error_message:
            flash(error_message, 'danger')
            reconstructed_libro_data = {
                'id': book_id,
                'titulo': request.form.get('titulo', ''),
                'subtitulo': request.form.get('subtitulo', ''),
                'autor_principal_nombre': request.form.get('autor_principal', ''),
                'segundo_autor': request.form.get('segundo_autor', ''),
                'tercer_autor': request.form.get('tercer_autor', ''),
                'codigo_cdu': request.form.get('codigo_cdu', ''),
                'materia': request.form.get('materia', ''),
                'nombre_editorial': request.form.get('nombre_editorial', ''),
                'nombre_idioma': request.form.get('nombre_idioma', ''),
                'anio': request.form.get('anio', ''),
                'paginas': request.form.get('paginas', ''),
                'isbn': request.form.get('isbn', ''),
                'observaciones': request.form.get('observaciones', ''),
                'disponible': request.form.get('disponible', 'Si')
            }
            return render_template('actualizar_libro.html',
                                   libro_id=book_id,
                                   libro_data=reconstructed_libro_data,
                                   next_url=next_url)
        else:
            flash('Libro actualizado correctamente.', 'success')
            if next_url:
                return redirect(next_url)
            return redirect(url_for('books.ver_ficha', book_id=book_id))
    else: # GET request
        libro_data = book_service.get_book_for_edit(book_id)
        if libro_data is None:
            flash('Libro no encontrado para editar.', 'danger')
            return redirect(url_for('books.listar_libros'))
        return render_template('actualizar_libro.html', libro_id=book_id, libro_data=libro_data, next_url=next_url)


@books_bp.route('/ver/<int:book_id>')
def ver_ficha(book_id):
    libro = book_service.get_book_details(book_id)
    if libro is None:
        flash('Libro no encontrado.', 'danger')
        return redirect(url_for('books.listar_libros'))
    prestamos = book_service.get_book_loans(book_id)
    next_url = request.args.get('next', url_for('books.listar_libros'))
    return render_template('ver_ficha.html', libro=libro, prestamos=prestamos, next_url=next_url)


@books_bp.route('/eliminar/<int:book_id>', methods=('POST',))
def eliminar_libro(book_id):
    next_url = request.args.get('next')

    error_message = book_service.delete_book(book_id)
    if error_message:
        flash(error_message, 'danger')
        # Si hay error, volvemos a la ficha del libro, preservando next_url si existe
        return redirect(url_for('books.ver_ficha', book_id=book_id, next=next_url))
    else:
        flash(f'Libro eliminado correctamente.', 'success')
        if next_url:
            return redirect(next_url)
        return redirect(url_for('books.listar_libros'))


@books_bp.route('/autocomplete/autores')
def autocomplete_autores():
    term = request.args.get('term', '').strip()
    suggestions = book_service.autocomplete_authors(term)
    return jsonify(suggestions)

@books_bp.route('/autocomplete/titulos')
def autocomplete_titulos():
    term = request.args.get('term', '').strip()
    suggestions = book_service.autocomplete_titles(term)
    return jsonify(suggestions)

@books_bp.route('/autocomplete/editoriales')
def autocomplete_editoriales():
    term = request.args.get('term', '').strip()
    suggestions = book_service.autocomplete_publishers(term)
    return jsonify(suggestions)

@books_bp.route('/autocomplete/idiomas')
def autocomplete_idiomas():
    term = request.args.get('term', '').strip()
    suggestions = book_service.autocomplete_languages(term)
    return jsonify(suggestions)

@books_bp.route('/autocomplete/cdu_codigos')
def autocomplete_cdu_codigos():
    term = request.args.get('term', '').strip()
    suggestions = book_service.autocomplete_cdu_codes(term)
    return jsonify(suggestions)

@books_bp.route('/autocomplete/cdu_materias')
def autocomplete_cdu_materias():
    term = request.args.get('term', '').strip()
    suggestions = book_service.autocomplete_cdu_subjects(term)
    return jsonify(suggestions)






