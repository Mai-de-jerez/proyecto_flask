# talegoTK_flask/blueprints/books/routes.py
import sqlite3
import unicodedata
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from database import get_db
import math
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

books_bp = Blueprint('books', __name__, template_folder='templates')

PER_PAGE = 20

def remove_accents(input_str):
    if not isinstance(input_str, str):
        return input_str
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


@books_bp.app_template_filter('url_set_param')
def url_set_param_filter(url, param_name, param_value):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query, keep_blank_values=True)

    query_params[param_name] = [param_value]

    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed_url._replace(query=new_query))


def _get_filtered_paginated_books(conn, search_query, page, per_page, mode='list'):
    params_for_sql_select = []
    where_clauses_for_filtering = []
    params_for_where_clause = []

    clean_search_query_lower = unicodedata.normalize('NFKD', search_query.strip()).encode('ascii', 'ignore').decode(
        'utf-8').lower()

    relevance_score_select_clause = "0 AS relevance_score"
    final_order_by_clause = "ORDER BY l.id ASC"

    if clean_search_query_lower:
        try:
            libro_id_search = int(clean_search_query_lower)
            where_clauses_for_filtering.append("l.id = ?")
            params_for_where_clause.append(libro_id_search)

            relevance_score_select_clause = "100 AS relevance_score"
            final_order_by_clause = "ORDER BY relevance_score DESC, l.id ASC"
        except ValueError:
            starts_with_pattern = f'{clean_search_query_lower}%'
            contains_pattern = f'%{clean_search_query_lower}%'

            search_fields = [
                "l.titulo",
                "a.nombre_autor"
            ]
            if mode == 'select':
                search_fields.append("c.codigo_cdu")
                search_fields.append("c.materia")

            or_conditions = []
            for field in search_fields:
                or_conditions.append(f"remove_accents({field}) LIKE remove_accents(?)")
                params_for_where_clause.append(contains_pattern)

            if or_conditions:
                where_clauses_for_filtering.append("(" + " OR ".join(or_conditions) + ")")

            relevance_case_parts = []
            for field in search_fields:
                relevance_case_parts.append(f"WHEN remove_accents({field}) LIKE remove_accents(?) THEN 2")
                params_for_sql_select.append(starts_with_pattern)

            for field in search_fields:
                relevance_case_parts.append(f"WHEN remove_accents({field}) LIKE remove_accents(?) THEN 1")
                params_for_sql_select.append(contains_pattern)

            if relevance_case_parts:
                relevance_score_select_clause = f'''
                    CASE
                        {' '.join(relevance_case_parts)}
                        ELSE 0
                    END AS relevance_score
                '''

            final_order_by_clause = "ORDER BY relevance_score DESC, l.id ASC"

    base_sql_from_join = '''
        FROM libros l
        JOIN autores a ON l.id_autor_principal = a.id
        JOIN cdu c ON l.id_cdu = c.id
    '''

    sql_where_clause_string = ""
    if where_clauses_for_filtering:
        sql_where_clause_string = " WHERE " + " AND ".join(where_clauses_for_filtering)

    count_query = f"SELECT COUNT(*) {base_sql_from_join} {sql_where_clause_string}"
    total_results = conn.execute(count_query, params_for_where_clause).fetchone()[0]

    total_pages = math.ceil(total_results / per_page) if total_results > 0 else 1

    page = max(1, min(page, max(1, total_pages)))
    main_sql_select_fields = f'''
        l.id,
        l.titulo,
        a.nombre_autor AS autor_principal,
        c.codigo_cdu,
        c.materia,
        l.let_titulo,
        l.let_autor,
        l.disponible,
        l.observaciones,
        {relevance_score_select_clause}
    '''

    sql_query = f"SELECT {main_sql_select_fields} {base_sql_from_join} {sql_where_clause_string} {final_order_by_clause} LIMIT ? OFFSET ?"
    final_params = params_for_sql_select + params_for_where_clause + [per_page, (page - 1) * per_page]
    libros = conn.execute(sql_query, final_params).fetchall()
    return libros, total_results, total_pages


@books_bp.route('/autocomplete/autores')
def autocomplete_autores():
    conn = get_db()
    term = request.args.get('term', '').strip()
    if not term:
        return jsonify([])

    # Limpiamos y convertimos el término a mayúsculas para la búsqueda
    clean_term_upper = remove_accents(term).upper()
    term_parts = clean_term_upper.split()  # Dividimos el término en palabras

    query_params = []
    where_conditions = []
    order_conditions = []

    # Lógica de relevancia:
    # Prioridad 4: Coincidencia exacta de la frase completa
    # Se usa 4 para que sea la más alta entre las condiciones específicas
    if clean_term_upper:
        order_conditions.append(f"WHEN remove_accents(nombre_autor) = ? THEN 4")
        query_params.append(clean_term_upper)
        where_conditions.append(f"remove_accents(nombre_autor) LIKE ?")
        query_params.append(f"%{clean_term_upper}%")  # para incluirlo en el WHERE general

    # Prioridad 3: Coincidencia de todas las palabras en cualquier orden (si hay múltiples palabras)
    if len(term_parts) > 1:
        all_words_like = []
        all_words_case = []
        for part in term_parts:
            all_words_like.append(f"remove_accents(nombre_autor) LIKE ?")
            query_params.append(f"%{part}%")
            all_words_case.append(f"remove_accents(nombre_autor) LIKE ?")
            query_params.append(f"%{part}%")  # Parámetros para la cláusula CASE

        where_conditions.append("(" + " AND ".join(all_words_like) + ")")
        order_conditions.append(f"WHEN (" + " AND ".join(all_words_case) + ") THEN 3")

    # Prioridad 2: Empieza con el término completo
    if clean_term_upper:
        order_conditions.append(f"WHEN remove_accents(nombre_autor) LIKE ? || '%' THEN 2")
        query_params.append(clean_term_upper)
        # Añadir al WHERE si aún no está cubierto por una condición más específica
        where_conditions.append(f"remove_accents(nombre_autor) LIKE ? || '%'")
        query_params.append(clean_term_upper)

    # Prioridad 1: Contiene alguna de las palabras (general, para asegurar resultados amplios)
    any_word_like = []
    any_word_case = []
    for part in term_parts:
        any_word_like.append(f"remove_accents(nombre_autor) LIKE ?")
        query_params.append(f"%{part}%")
        any_word_case.append(f"remove_accents(nombre_autor) LIKE ?")
        query_params.append(f"%{part}%")  # Parámetros para la cláusula CASE
    if any_word_like:
        where_conditions.append("(" + " OR ".join(any_word_like) + ")")
        order_conditions.append(f"WHEN (" + " OR ".join(any_word_case) + ") THEN 1")

    # Asegurarse de que el WHERE clause no esté vacío
    final_where_clause = " OR ".join(set(where_conditions)) if where_conditions else '1=1'

    sql_query = f"""
        SELECT nombre_autor,
               CASE
                   {' '.join(order_conditions)}
                   ELSE 0
               END AS relevance_score
        FROM autores
        WHERE {final_where_clause}
        ORDER BY relevance_score DESC, nombre_autor ASC
        LIMIT 10
    """

    autores = conn.execute(sql_query, query_params).fetchall()

    return jsonify([row['nombre_autor'] for row in autores])


@books_bp.route('/autocomplete/titulos')
def autocomplete_titulos():
    conn = get_db()
    term = request.args.get('term', '').strip()
    if not term:
        return jsonify([])

    clean_term_upper = remove_accents(term).upper()
    term_parts = clean_term_upper.split()

    query_params = []
    order_conditions = []
    where_clauses_for_search = []

    # Función auxiliar para generar condiciones para un campo específico
    def _generate_field_conditions(field_name, base_score):
        # Corrección para PyCharm: Inicializar 'conditions' como un literal de lista
        nonlocal query_params
        conditions = [
            f"WHEN remove_accents({field_name}) = ? THEN {base_score + 4}",
            f"WHEN remove_accents({field_name}) LIKE ? || '%' THEN {base_score + 3}",
            f"WHEN remove_accents({field_name}) LIKE ? THEN {base_score + 2}"
        ]
        # Los parámetros para estas condiciones iniciales
        query_params.append(clean_term_upper)
        query_params.append(clean_term_upper)
        query_params.append(f"%{clean_term_upper}%")

        # Contiene todas las palabras en cualquier orden (si hay múltiples palabras)
        if len(term_parts) > 1:
            all_words_check = []
            for item_part in term_parts: # 'item_part' evita el "shadows name"
                all_words_check.append(f"remove_accents({field_name}) LIKE ?")
                query_params.append(f"%{item_part}%")
            conditions.append(f"WHEN (" + " AND ".join(all_words_check) + f") THEN {base_score + 1}")

        # Contiene alguna palabra (general)
        any_word_check = []
        for item_part in term_parts: # 'item_part' evita el "shadows name"
            any_word_check.append(f"remove_accents({field_name}) LIKE ?")
            query_params.append(f"%{item_part}%")
        conditions.append(f"WHEN (" + " OR ".join(any_word_check) + f") THEN {base_score + 0}")

        return conditions

    # Generar condiciones para TITULO (mayor prioridad)
    order_conditions.extend(_generate_field_conditions('titulo', 10))  # Base 10 para título
    # Generar condiciones para SUBTITULO (menor prioridad)
    order_conditions.extend(_generate_field_conditions('subtitulo', 0))  # Base 0 para subtítulo
    fields_to_check = ['titulo', 'subtitulo']

    # Busca si el término completo aparece en título o subtítulo
    or_full_term_conditions = []
    for field in fields_to_check:
        or_full_term_conditions.append(f"remove_accents({field}) LIKE ?")
        query_params.append(f"%{clean_term_upper}%")
    if or_full_term_conditions:
        where_clauses_for_search.append("(" + " OR ".join(or_full_term_conditions) + ")")

    # Busca si todas las palabras aparecen en cualquier campo (si hay múltiples palabras)
    if len(term_parts) > 1:
        all_words_field_conditions = []
        for current_part in term_parts: # 'current_part' es correcto aquí
            all_words_field_conditions.append(
                f"(remove_accents(titulo) LIKE ? OR remove_accents(subtitulo) LIKE ?)"
            )
            query_params.extend([f"%{current_part}%", f"%{current_part}%"])
        where_clauses_for_search.append("(" + " AND ".join(all_words_field_conditions) + ")")

    # Si no hay condiciones más específicas, al menos buscar por alguna palabra
    if not where_clauses_for_search and clean_term_upper:
        any_word_field_conditions = []
        for current_part in term_parts: # 'current_part' es correcto aquí
            any_word_field_conditions.append(f"(remove_accents(titulo) LIKE ? OR remove_accents(subtitulo) LIKE ?)")
            query_params.extend([f"%{current_part}%", f"%{current_part}%"])
        if any_word_field_conditions:
            where_clauses_for_search.append("(" + " OR ".join(any_word_field_conditions) + ")")

    final_where_clause = " OR ".join(set(where_clauses_for_search)) if where_clauses_for_search else "1=1"

    sql_query = f"""
        SELECT titulo,
               CASE
                   {' '.join(order_conditions)}
                   ELSE 0
               END AS relevance_score
        FROM libros
        WHERE {final_where_clause}
        ORDER BY relevance_score DESC, titulo ASC
        LIMIT 10
    """

    titulos = conn.execute(sql_query, query_params).fetchall()

    # Devolvemos solo títulos únicos para evitar duplicados si un mismo título aparece por subtítulo, etc.
    unique_titulos = sorted(list(set([row['titulo'] for row in titulos])))
    return jsonify(unique_titulos)


@books_bp.route('/autocomplete/editoriales')
def autocomplete_editoriales():
    conn = get_db()
    term = request.args.get('term', '').strip()
    if not term:
        return jsonify([])

    search_term = '%' + remove_accents(term).upper() + '%'
    editoriales = conn.execute(
        "SELECT nombre_editorial FROM editoriales WHERE remove_accents(nombre_editorial) LIKE ? ORDER BY nombre_editorial LIMIT 10",
        (search_term,)
    ).fetchall()
    return jsonify([row['nombre_editorial'] for row in editoriales])


@books_bp.route('/autocomplete/idiomas')
def autocomplete_idiomas():
    conn = get_db()
    term = request.args.get('term', '').strip()
    if not term:
        return jsonify([])

    search_term = '%' + remove_accents(term).upper() + '%'
    idiomas = conn.execute(
        "SELECT nombre_idioma FROM idiomas WHERE remove_accents(nombre_idioma) LIKE ? ORDER BY nombre_idioma LIMIT 10",
        (search_term,)
    ).fetchall()
    return jsonify([row['nombre_idioma'] for row in idiomas])


@books_bp.route('/autocomplete/cdu_codigos')
def autocomplete_cdu_codigos():
    conn = get_db()
    term = request.args.get('term', '').strip()
    if not term:
        return jsonify([])

    search_term = '%' + remove_accents(term).upper() + '%'
    codigos = conn.execute(
        "SELECT codigo_cdu FROM cdu WHERE remove_accents(codigo_cdu) LIKE ? ORDER BY codigo_cdu LIMIT 10",
        (search_term,)
    ).fetchall()
    return jsonify([row['codigo_cdu'] for row in codigos])


@books_bp.route('/autocomplete/cdu_materias')
def autocomplete_cdu_materias():
    conn = get_db()
    term = request.args.get('term', '').strip()
    if not term:
        return jsonify([])

    search_term = '%' + remove_accents(term).upper() + '%'
    materias = conn.execute(
        "SELECT materia FROM cdu WHERE remove_accents(materia) LIKE ? ORDER BY materia LIMIT 10",
        (search_term,)
    ).fetchall()
    return jsonify([row['materia'] for row in materias])

@books_bp.route('/')
def listar_libros():
    conn = get_db()
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    # Utilizar la función auxiliar para obtener los datos
    libros, total_results, total_pages = _get_filtered_paginated_books(
        conn, search_query, page, PER_PAGE, mode='list'
    )

    return render_template(
        'libros_list.html',
        libros=libros,
        q=search_query,
        page=page,
        per_page=PER_PAGE,
        total_pages=total_pages,
        total_results=total_results
    )

@books_bp.route('/list_ajax')
def listar_libros_ajax():
    conn = get_db()
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    # Utilizar la función auxiliar para obtener los datos
    libros, total_results, total_pages = _get_filtered_paginated_books(
        conn, search_query, page, PER_PAGE, mode='list'
    )

    # Renderizar solo el fragmento HTML de las filas de la tabla
    table_rows_html = render_template(
        '_libros_table_rows.html',
        libros=libros
    )

    # Renderizar solo el fragmento HTML de los controles de paginación
    pagination_html = render_template(
        '_pagination_controls_books.html',
        page=page,
        total_pages=total_pages,
        q=search_query,
        base_ajax_url='books.listar_libros_ajax'
    )

    # Devolver una respuesta JSON con los fragmentos HTML y otros datos
    return jsonify({
        'table_rows': table_rows_html,
        'pagination_html': pagination_html,
        'total_results': total_results
    })

@books_bp.route('/listar_libros_select', methods=['GET'])
def listar_libros_select():
    conn = get_db()
    all_args = request.args.to_dict()
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    all_args['q'] = search_query
    all_args['page'] = str(page)
    select_mode = True
    libros, total_results, total_pages = _get_filtered_paginated_books(
        conn, search_query, page, PER_PAGE, mode='select'
    )

    all_url_params_for_js = urlencode(all_args)
    return render_template(
        'libros_list_select.html',
        libros=libros,
        q=search_query,
        select_mode=select_mode,
        page=page,
        per_page=PER_PAGE,
        total_pages=total_pages,
        total_results=total_results,
        current_page_url=request.full_path,
        all_url_params_for_js=all_url_params_for_js
    )

@books_bp.route('/select_ajax', methods=['GET'])
def listar_libros_select_ajax():
    conn = get_db()
    all_args = request.args.to_dict()
    search_query = all_args.get('q', '').strip()
    page = int(all_args.get('page', 1))

    all_args['q'] = search_query
    all_args['page'] = str(page)

    # Utilizar la función auxiliar para obtener los datos en modo selección
    libros, total_results, total_pages = _get_filtered_paginated_books(
        conn, search_query, page, PER_PAGE, mode='select'
    )

    current_page_url = url_for('books.listar_libros_select', **all_args)


    # Renderizar solo el fragmento HTML de las filas para el modo selección
    table_rows_html = render_template(
        '_libros_select_table_rows.html',
        libros=libros,
        current_page_url=current_page_url
    )

    # Renderizar solo el fragmento HTML de los controles de paginación para el modo selección
    pagination_html = render_template(
        '_pagination_controls_books.html',
        page=page,
        total_pages=total_pages,
        q=search_query,
        base_ajax_url='books.listar_libros_select_ajax',
        all_url_params=all_args
    )

    current_state_url = url_for('books.listar_libros_select', **all_args)
    return jsonify({
        'table_rows': table_rows_html,
        'pagination_html': pagination_html,
        'total_results': total_results,
        'current_state_url': current_state_url
    })

@books_bp.route('/nuevo', methods=('GET', 'POST'))
def anadir_libro():
    conn = get_db()
    errors = []

    # Recopilar datos del formulario
    num_reg_input = request.form.get('num_reg', '').strip()
    titulo = request.form.get('titulo', '').strip().upper()
    subtitulo = request.form.get('subtitulo', '').strip().upper()
    autor_principal_nombre = request.form.get('autor_principal', '').strip().upper()
    segundo_autor = request.form.get('segundo_autor', '').strip().upper()
    tercer_autor = request.form.get('tercer_autor', '').strip().upper()
    codigo_cdu_input = request.form.get('codigo_cdu', '').strip().upper()
    materia_input = request.form.get('materia', '').strip().upper()
    nombre_editorial_input = request.form.get('nombre_editorial', '').strip().upper()
    nombre_idioma_input = request.form.get('nombre_idioma', '').strip().upper()
    anio_str = request.form.get('anio', '').strip()
    paginas_str = request.form.get('paginas', '').strip()
    anio = None
    if anio_str:
        try:
            anio = int(anio_str)
        except ValueError:
            errors.append('El año debe ser un número entero válido.')

    paginas = None
    if paginas_str:
        try:
            paginas = int(paginas_str)
        except ValueError:
            errors.append('El número de páginas debe ser un entero válido.')

    isbn = request.form.get('isbn', '').strip().upper()
    observaciones = request.form.get('observaciones', '').strip()
    disponible = 'Si'

    if request.method == 'POST':
        # Validaciones de campos obligatorios
        if not titulo:
            errors.append('El título es un campo obligatorio.')
        if not autor_principal_nombre:
            errors.append('El autor principal es un campo obligatorio.')
        if not codigo_cdu_input:
            errors.append('El código CDU es un campo obligatorio.')
        if not materia_input:
            errors.append('La materia es un campo obligatorio.')
        if not nombre_editorial_input:
            errors.append('La editorial es un campo obligatorio.')
        if not nombre_idioma_input:
            errors.append('El idioma es un campo obligatorio.')

        libro_id = None
        if num_reg_input:
            try:
                libro_id = int(num_reg_input)
                if libro_id <= 0:
                    errors.append('El número de registro debe ser un entero positivo.')
            except ValueError:
                errors.append('El número de registro debe ser un número entero válido.')

            if not errors:
                existing_libro = conn.execute("SELECT id FROM libros WHERE id = ?", (libro_id,)).fetchone()
                if existing_libro:
                    errors.append(f'El número de registro {libro_id} ya existe. Por favor, elija otro.')

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('anadir_libro.html',
                                   num_reg=num_reg_input,
                                   titulo=titulo, subtitulo=subtitulo,
                                   autor_principal=autor_principal_nombre,
                                   segundo_autor=segundo_autor,
                                   tercer_autor=tercer_autor,
                                   codigo_cdu=codigo_cdu_input, materia=materia_input,
                                   nombre_editorial=nombre_editorial_input,
                                   nombre_idioma=nombre_idioma_input,
                                   anio=str(anio) if anio is not None else '',
                                   paginas=str(paginas) if paginas is not None else '',
                                   isbn=isbn,
                                   observaciones=observaciones)

        try:
            # --- Gestión del Autor Principal ---
            cursor = conn.execute("SELECT id FROM autores WHERE nombre_autor = ?", (autor_principal_nombre,))
            autor_principal_id_row = cursor.fetchone()
            if not autor_principal_id_row:
                conn.execute("INSERT INTO autores (nombre_autor) VALUES (?)", (autor_principal_nombre,))
                conn.commit()
                autor_principal_id_row = conn.execute("SELECT id FROM autores WHERE nombre_autor = ?",
                                                      (autor_principal_nombre,)).fetchone()
            id_autor_principal = autor_principal_id_row['id']

            # --- Gestión de CDU ---
            cursor = conn.execute("SELECT id, materia FROM cdu WHERE codigo_cdu = ?", (codigo_cdu_input,))
            cdu_entry = cursor.fetchone()

            if cdu_entry:
                id_cdu = cdu_entry['id']
                if cdu_entry['materia'] != materia_input:
                    conn.execute("UPDATE cdu SET materia = ? WHERE id = ?", (materia_input, id_cdu))
                    conn.commit()
            else:
                conn.execute("INSERT INTO cdu (codigo_cdu, materia) VALUES (?, ?)", (codigo_cdu_input, materia_input))
                conn.commit()
                id_cdu = conn.execute("SELECT id FROM cdu WHERE codigo_cdu = ?", (codigo_cdu_input,)).fetchone()['id']

            # --- Gestión de Editorial ---
            cursor = conn.execute("SELECT id FROM editoriales WHERE nombre_editorial = ?", (nombre_editorial_input,))
            editorial_id_row = cursor.fetchone()
            if not editorial_id_row:
                conn.execute("INSERT INTO editoriales (nombre_editorial) VALUES (?)", (nombre_editorial_input,))
                conn.commit()
                editorial_id_row = conn.execute("SELECT id FROM editoriales WHERE nombre_editorial = ?",
                                                (nombre_editorial_input,)).fetchone()
            id_editorial = editorial_id_row['id']

            # --- Gestión de Idioma ---
            cursor = conn.execute("SELECT id FROM idiomas WHERE nombre_idioma = ?", (nombre_idioma_input,))
            idioma_id_row = cursor.fetchone()
            if not idioma_id_row:
                conn.execute("INSERT INTO idiomas (nombre_idioma) VALUES (?)", (nombre_idioma_input,))
                conn.commit()
                idioma_id_row = conn.execute("SELECT id FROM idiomas WHERE nombre_idioma = ?",
                                             (nombre_idioma_input,)).fetchone()
            id_idioma = idioma_id_row['id']

            # --- Generar Letras de Autor y Título ---
            autor_principal_nombre_sin_tildes = remove_accents(autor_principal_nombre)
            let_autor = autor_principal_nombre_sin_tildes[:3].upper() if autor_principal_nombre_sin_tildes else ''

            let_titulo = titulo[:3].lower() if titulo else ''

            # --- Inserción en la tabla de libros ---
            if libro_id is not None:
                conn.execute('''
                    INSERT INTO libros (
                        id, id_cdu, let_autor, let_titulo, titulo, subtitulo,
                        id_autor_principal, segundo_autor, tercer_autor,
                        anio, id_editorial, paginas, id_idioma,
                        observaciones, isbn, disponible
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                             (
                                 libro_id, id_cdu, let_autor, let_titulo, titulo, subtitulo,
                                 id_autor_principal, segundo_autor, tercer_autor,
                                 anio, id_editorial, paginas, id_idioma,
                                 observaciones, isbn, disponible
                             ))
            else:
                conn.execute('''
                    INSERT INTO libros (
                        id_cdu, let_autor, let_titulo, titulo, subtitulo,
                        id_autor_principal, segundo_autor, tercer_autor,
                        anio, id_editorial, paginas, id_idioma,
                        observaciones, isbn, disponible
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                             (
                                 id_cdu, let_autor, let_titulo, titulo, subtitulo,
                                 id_autor_principal, segundo_autor, tercer_autor,
                                 anio, id_editorial, paginas, id_idioma,
                                 observaciones, isbn, disponible
                             ))
            conn.commit()
            flash('Libro añadido correctamente.', 'success')
            return redirect(url_for('books.listar_libros'))

        except sqlite3.IntegrityError as e:
            conn.rollback()
            if "UNIQUE constraint failed: cdu.materia" in str(e) or "UNIQUE constraint failed: cdu.codigo_cdu, cdu.materia" in str(e):
                existing_cdu = conn.execute("SELECT codigo_cdu, materia FROM cdu WHERE materia = ?", (materia_input,)).fetchone()
                if existing_cdu:
                    flash_message = (f'Esa materia ya existe y su CDU asociado no es ese. El CDU para la materia "{existing_cdu["materia"]}" es "{existing_cdu["codigo_cdu"]}".', 'danger')
                else:
                    flash_message = (f'Error de integridad: Un valor que intentaste introducir ya existe o no es válido. {e}', 'danger')
            elif "UNIQUE constraint failed: libros.id" in str(e) and request.form.get('num_reg'):
                flash_message = ('El Número de Registro (ID) que has introducido ya existe. Por favor, elige otro o déjalo vacío para asignación automática.', 'danger')
            else:
                flash_message = (f'Ocurrió un error de integridad en la base de datos: {e}. Asegúrate de que todas las referencias existen y el ID es único.', 'danger')

            flash(*flash_message)

            return render_template('anadir_libro.html',
                                   num_reg=num_reg_input,
                                   titulo=titulo, subtitulo=subtitulo,
                                   autor_principal=autor_principal_nombre,
                                   segundo_autor=segundo_autor,
                                   tercer_autor=tercer_autor,
                                   codigo_cdu=codigo_cdu_input, materia=materia_input,
                                   nombre_editorial=nombre_editorial_input,
                                   nombre_idioma=nombre_idioma_input,
                                   anio=str(anio) if anio is not None else '',
                                   paginas=str(paginas) if paginas is not None else '',
                                   isbn=isbn,
                                   observaciones=observaciones)

        except Exception as e:
            flash(f'Ocurrió un error inesperado al añadir el libro: {e}', 'danger')
            conn.rollback()
            return render_template('anadir_libro.html',
                                   num_reg=num_reg_input,
                                   titulo=titulo, subtitulo=subtitulo,
                                   autor_principal=autor_principal_nombre,
                                   segundo_autor=segundo_autor,
                                   tercer_autor=tercer_autor,
                                   codigo_cdu=codigo_cdu_input, materia=materia_input,
                                   nombre_editorial=nombre_editorial_input,
                                   nombre_idioma=nombre_idioma_input,
                                   anio=str(anio) if anio is not None else '',
                                   paginas=str(paginas) if paginas is not None else '',
                                   isbn=isbn,
                                   observaciones=observaciones)

    # Para la solicitud GET (primera carga del formulario)
    return render_template('anadir_libro.html',
                           num_reg=num_reg_input,
                           titulo=titulo,
                           subtitulo=subtitulo,
                           autor_principal=autor_principal_nombre,
                           segundo_autor=segundo_autor,
                           tercer_autor=tercer_autor,
                           codigo_cdu=codigo_cdu_input,
                           materia=materia_input,
                           nombre_editorial=nombre_editorial_input,
                           nombre_idioma=nombre_idioma_input,
                           anio=str(anio) if anio is not None else '',
                           paginas=str(paginas) if paginas is not None else '',
                           isbn=isbn,
                           observaciones=observaciones)


@books_bp.route('/editar/<int:book_id>', methods=('GET', 'POST'))
def editar_libro(book_id):
    conn = get_db()
    cursor = conn.cursor()
    errors = []
    next_url = request.args.get('next')

    libro_data_db = cursor.execute('''
        SELECT
            l.id, l.titulo, l.subtitulo, l.anio, l.paginas, l.isbn, l.observaciones, l.disponible,
            a1.nombre_autor AS autor_principal_nombre,
            l.segundo_autor,
            l.tercer_autor,
            c.codigo_cdu, c.materia,
            e.nombre_editorial,
            i.nombre_idioma
        FROM libros l
        LEFT JOIN autores a1 ON l.id_autor_principal = a1.id
        LEFT JOIN cdu c ON l.id_cdu = c.id
        LEFT JOIN editoriales e ON l.id_editorial = e.id
        LEFT JOIN idiomas i ON l.id_idioma = i.id
        WHERE l.id = ?
    ''', (book_id,)).fetchone()

    if libro_data_db is None:
        flash('Libro no encontrado para editar.', 'danger')
        return redirect(url_for('books.listar_libros'))

    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip().upper()
        subtitulo = request.form.get('subtitulo', '').strip()

        autor_principal_nombre = request.form.get('autor_principal', '').strip().upper()
        segundo_autor = request.form.get('segundo_autor', '').strip()
        tercer_autor = request.form.get('tercer_autor', '').strip()

        codigo_cdu_input = request.form.get('codigo_cdu', '').strip().upper()
        materia_input = request.form.get('materia', '').strip().upper()
        nombre_editorial_input = request.form.get('nombre_editorial', '').strip().upper()
        nombre_idioma_input = request.form.get('nombre_idioma', '').strip().upper()

        anio = request.form.get('anio')
        paginas = request.form.get('paginas')
        isbn = request.form.get('isbn', '').strip()
        observaciones = request.form.get('observaciones', '').strip()

        try:
            anio = int(anio) if anio else None
        except ValueError:
            errors.append('El año debe ser un número entero válido.')
            anio = None

        try:
            paginas = int(paginas) if paginas else None
        except ValueError:
            errors.append('El número de páginas debe ser un entero válido.')
            paginas = None

        if not titulo:
            errors.append('El título es un campo obligatorio.')
        if not autor_principal_nombre:
            errors.append('El autor principal es un campo obligatorio.')
        if not codigo_cdu_input:
            errors.append('El código CDU es un campo obligatorio.')
        if not materia_input:
            errors.append('La materia es un campo obligatorio.')
        if not nombre_editorial_input:
            errors.append('La editorial es un campo obligatorio.')
        if not nombre_idioma_input:
            errors.append('El idioma es un campo obligatorio.')

        if errors:
            for error in errors:
                flash(error, 'danger')

            reconstructed_libro_data = {
                'id': book_id,
                'titulo': titulo, 'subtitulo': subtitulo,
                'autor_principal_nombre': autor_principal_nombre,
                'segundo_autor': segundo_autor,
                'tercer_autor': tercer_autor,
                'codigo_cdu': codigo_cdu_input, 'materia': materia_input,
                'nombre_editorial': nombre_editorial_input,
                'nombre_idioma': nombre_idioma_input,
                'anio': str(anio) if anio is not None else '',
                'paginas': str(paginas) if paginas is not None else '',
                'isbn': isbn,
                'observaciones': observaciones,
                'disponible': libro_data_db['disponible']
            }

            return render_template('actualizar_libro.html',
                                   libro_id=book_id,
                                   libro_data=reconstructed_libro_data,
                                   next_url=next_url)

        try:
            autor_principal_id_row = cursor.execute("SELECT id FROM autores WHERE nombre_autor = ?", (autor_principal_nombre,)).fetchone()
            if not autor_principal_id_row:
                cursor.execute("INSERT INTO autores (nombre_autor) VALUES (?)", (autor_principal_nombre,))
                conn.commit()
                autor_principal_id_row = cursor.execute("SELECT id FROM autores WHERE nombre_autor = ?",
                                                      (autor_principal_nombre,)).fetchone()
            id_autor_principal = autor_principal_id_row['id']

            cdu_entry = cursor.execute("SELECT id, materia FROM cdu WHERE codigo_cdu = ?", (codigo_cdu_input,)).fetchone()
            if cdu_entry:
                id_cdu = cdu_entry['id']
                if cdu_entry['materia'] != materia_input:
                    cursor.execute("UPDATE cdu SET materia = ? WHERE id = ?", (materia_input, id_cdu))
                    conn.commit()
            else:
                cursor.execute("INSERT INTO cdu (codigo_cdu, materia) VALUES (?, ?)", (codigo_cdu_input, materia_input))
                conn.commit()
                id_cdu = cursor.execute("SELECT id FROM cdu WHERE codigo_cdu = ?", (codigo_cdu_input,)).fetchone()['id']

            editorial_id_row = cursor.execute("SELECT id FROM editoriales WHERE nombre_editorial = ?", (nombre_editorial_input,)).fetchone()
            if not editorial_id_row:
                cursor.execute("INSERT INTO editoriales (nombre_editorial) VALUES (?)", (nombre_editorial_input,))
                conn.commit()
                editorial_id_row = cursor.execute("SELECT id FROM editoriales WHERE nombre_editorial = ?",
                                                (nombre_editorial_input,)).fetchone()
            id_editorial = editorial_id_row['id']

            idioma_id_row = cursor.execute("SELECT id FROM idiomas WHERE nombre_idioma = ?", (nombre_idioma_input,)).fetchone()
            if not idioma_id_row:
                cursor.execute("INSERT INTO idiomas (nombre_idioma) VALUES (?)", (nombre_idioma_input,))
                conn.commit()
                idioma_id_row = cursor.execute("SELECT id FROM idiomas WHERE nombre_idioma = ?",
                                             (nombre_idioma_input,)).fetchone()
            id_idioma = idioma_id_row['id']

            autor_principal_nombre_sin_tildes = remove_accents(autor_principal_nombre)
            let_autor = autor_principal_nombre_sin_tildes[:3].upper() if autor_principal_nombre_sin_tildes else ''

            let_titulo = titulo[:3].lower() if titulo else ''

            cursor.execute('''
                UPDATE libros SET
                    id_cdu = ?,
                    let_autor = ?,
                    let_titulo = ?,
                    titulo = ?,
                    subtitulo = ?,
                    id_autor_principal = ?,
                    segundo_autor = ?,
                    tercer_autor = ?,
                    anio = ?,
                    id_editorial = ?,
                    paginas = ?,
                    id_idioma = ?,
                    observaciones = ?,
                    isbn = ?
                WHERE id = ?
            ''',
                         (
                             id_cdu, let_autor, let_titulo, titulo, subtitulo,
                             id_autor_principal,
                             segundo_autor,
                             tercer_autor,
                             anio, id_editorial, paginas, id_idioma,
                             observaciones,
                             isbn,
                             book_id
                         ))
            conn.commit()
            flash('Libro actualizado correctamente.', 'success')
            if next_url:
                return redirect(next_url)
            return redirect(url_for('books.ver_ficha', book_id=book_id))

        except sqlite3.IntegrityError as e:
            conn.rollback()

            if "UNIQUE constraint failed: cdu.materia" in str(
                    e) or "UNIQUE constraint failed: cdu.codigo_cdu, cdu.materia" in str(e):
                existing_cdu = cursor.execute("SELECT codigo_cdu, materia FROM cdu WHERE materia = ?",
                                            (materia_input,)).fetchone()
                if existing_cdu:
                    flash_message = (
                    f'Esa materia ya existe y su CDU asociado no es ese. El CDU para la materia "{existing_cdu["materia"]}" es "{existing_cdu["codigo_cdu"]}".',
                    'danger')
                else:
                    flash_message = (
                    f'Error de integridad: Un valor que intentaste introducir ya existe o no es válido. {e}', 'danger')
            else:
                flash_message = (
                f'Ocurrió un error de integridad en la base de datos: {e}. Asegúrate de que todas las referencias existen y el ID es único.',
                'danger')

            flash(*flash_message)

            reconstructed_libro_data = {
                'id': book_id,
                'titulo': titulo, 'subtitulo': subtitulo,
                'autor_principal_nombre': autor_principal_nombre,
                'segundo_autor': segundo_autor,
                'tercer_autor': tercer_autor,
                'codigo_cdu': codigo_cdu_input, 'materia': materia_input,
                'nombre_editorial': nombre_editorial_input,
                'nombre_idioma': nombre_idioma_input,
                'anio': str(anio) if anio is not None else '',
                'paginas': str(paginas) if paginas is not None else '',
                'isbn': isbn,
                'observaciones': observaciones,
                'disponible': libro_data_db['disponible']
            }

            return render_template('actualizar_libro.html',
                                   libro_id=book_id,
                                   libro_data=reconstructed_libro_data,
                                   next_url=next_url)

        except Exception as e:
            flash(f'Ocurrió un error inesperado al actualizar el libro: {e}', 'danger')
            conn.rollback()
            reconstructed_libro_data = {
                'id': book_id,
                'titulo': titulo, 'subtitulo': subtitulo,
                'autor_principal_nombre': autor_principal_nombre,
                'segundo_autor': segundo_autor,
                'tercer_autor': tercer_autor,
                'codigo_cdu': codigo_cdu_input, 'materia': materia_input,
                'nombre_editorial': nombre_editorial_input,
                'nombre_idioma': nombre_idioma_input,
                'anio': str(anio) if anio is not None else '',
                'paginas': str(paginas) if paginas is not None else '',
                'isbn': isbn,
                'observaciones': observaciones,
                'disponible': libro_data_db['disponible']
            }

            return render_template('actualizar_libro.html',
                                   libro_id=book_id,
                                   libro_data=reconstructed_libro_data,
                                   next_url=next_url)

    libro_data = {
        'id': libro_data_db['id'],
        'titulo': libro_data_db['titulo'],
        'subtitulo': libro_data_db['subtitulo'] if libro_data_db['subtitulo'] is not None else '',
        'anio': str(libro_data_db['anio']) if libro_data_db['anio'] is not None else '',
        'paginas': str(libro_data_db['paginas']) if libro_data_db['paginas'] is not None else '',
        'isbn': libro_data_db['isbn'] if libro_data_db['isbn'] is not None else '',
        'observaciones': libro_data_db['observaciones'] if libro_data_db['observaciones'] is not None else '',
        'disponible': libro_data_db['disponible'],
        'autor_principal_nombre': libro_data_db['autor_principal_nombre'],
        'segundo_autor': libro_data_db['segundo_autor'] if libro_data_db['segundo_autor'] is not None else '',
        'tercer_autor': libro_data_db['tercer_autor'] if libro_data_db['tercer_autor'] is not None else '',
        'codigo_cdu': libro_data_db['codigo_cdu'],
        'materia': libro_data_db['materia'],
        'nombre_editorial': libro_data_db['nombre_editorial'],
        'nombre_idioma': libro_data_db['nombre_idioma']
    }
    return render_template('actualizar_libro.html', libro_id=book_id, libro_data=libro_data, next_url=next_url)

@books_bp.route('/ver/<int:book_id>')
def ver_ficha(book_id):
    conn = get_db()
    cursor = conn.cursor()
    libro = cursor.execute('''
        SELECT
            l.id,
            l.titulo,
            l.subtitulo,
            a1.nombre_autor AS autor_principal_nombre,
            l.segundo_autor AS segundo_autor_nombre,  
            l.tercer_autor AS tercer_autor_nombre,   
            l.let_titulo,      
            l.let_autor,       
            c.codigo_cdu || ' - ' || c.materia AS cdu_completa,
            l.anio,
            e.nombre_editorial,
            l.paginas,
            i.nombre_idioma,
            l.isbn,
            l.observaciones,
            l.disponible  
        FROM libros l
        JOIN autores a1 ON l.id_autor_principal = a1.id
        LEFT JOIN editoriales e ON l.id_editorial = e.id
        LEFT JOIN idiomas i ON l.id_idioma = i.id
        LEFT JOIN cdu c ON l.id_cdu = c.id
        WHERE l.id = ?
    ''', (book_id,)).fetchone()

    if libro is None:
        flash('Libro no encontrado.', 'danger')
        return redirect(url_for('books.listar_libros'))

    prestamos = cursor.execute('''
        SELECT
            p.id,
            u.nombre || ' ' || u.apellidos AS usuario_nombre,
            p.fecha_prestamo,
            p.fecha_devolucion_estimada,
            p.fecha_devolucion_real,
            p.estado_prestamo
        FROM prestamos p
        JOIN usuarios u ON p.id_usuario = u.id
        WHERE p.id_libro = ?
        ORDER BY p.fecha_prestamo DESC
    ''', (book_id,)).fetchall()

    next_url = request.args.get('next', url_for('books.listar_libros'))
    return render_template('ver_ficha.html', libro=libro, prestamos=prestamos, next_url=next_url)


@books_bp.route('/eliminar/<int:book_id>', methods=('POST',))
def eliminar_libro(book_id):
    conn = get_db()
    cursor = conn.cursor()
    libro_info = cursor.execute("SELECT titulo, disponible FROM libros WHERE id = ?", (book_id,)).fetchone()

    if libro_info is None:
        flash('Libro no encontrado para eliminar.', 'danger')
        return redirect(url_for('books.listar_libros'))

    # 2. Comprobación de la disponibilidad ANTES de intentar el borrado
    if libro_info['disponible'] == 'No':
        flash(f'No se puede eliminar el libro "{libro_info["titulo"]}" porque está actualmente prestado (estado "No disponible"). Primero debe ser devuelto.', 'danger')
        return redirect(url_for('books.ver_ficha', book_id=book_id))

    try:
        conn.execute("DELETE FROM libros WHERE id = ?", (book_id,))
        conn.commit()
        flash(f'Libro "{libro_info["titulo"]}" eliminado correctamente.', 'success')
        return redirect(url_for('books.listar_libros'))

    except sqlite3.IntegrityError as e:
        conn.rollback()
        if "FOREIGN KEY constraint failed" in str(e):
            flash(f'No se puede eliminar el libro "{libro_info["titulo"]}" porque tiene un historial de préstamos asociado. Solo se pueden eliminar libros que nunca han sido prestados.', 'danger')
        else:
            flash(f'Ocurrió un error de integridad en la base de datos al intentar eliminar el libro: {e}', 'danger')
        return redirect(url_for('books.ver_ficha', book_id=book_id))

    except Exception as e:
        flash(f'Ocurrió un error inesperado al eliminar el libro: {e}', 'danger')
        conn.rollback()
        return redirect(url_for('books.listar_libros'))



