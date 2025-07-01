# tu_proyecto_biblioteca/blueprints/books/book_service.py
import sqlite3
import unicodedata
import math
from typing import List, Any, Dict, Optional

# Constante de paginación (puede estar aquí o en routes, pero aquí es más coherente con el servicio)
PER_PAGE = 20

# Función auxiliar para eliminar tildes (uso interno del servicio)
def remove_accents(input_str: str) -> str:
    if not isinstance(input_str, str):
        return input_str
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

# Función auxiliar para mapear el tipo de material a condiciones SQL de CDU
def map_material_type_to_cdu_conditions(material_type: str) -> List[str]:
    if material_type == 'dvd':
        return ["c.codigo_cdu LIKE 'DVD%'"]
    elif material_type == 'revista':
        return ["c.codigo_cdu = '82-42'"]
    elif material_type == 'curso':
        return ["c.codigo_cdu = 'CURIDI'"]
    elif material_type == 'diccionario_enciclopedia':
        return ["c.codigo_cdu LIKE '%DIC%'"]
    elif material_type == 'atlas':
        return ["c.codigo_cdu = '91-1'"]
    return []


class BookService:
    def __init__(self, db_connection_factory):
        self.get_db = db_connection_factory

    def eliminar_autor_si_huerfano(self, autor_id: int) -> bool:
        conn = self.get_db()
        cursor = conn.cursor()

        try:
            # Primero, verifica si el autor realmente existe
            autor = cursor.execute('SELECT nombre_autor FROM autores WHERE id = ?', (autor_id,)).fetchone()
            if not autor:
                print(f"ADVERTENCIA: Intento de verificar autor huérfano para ID {autor_id}, pero el autor no existe.")
                return False

            # Cuenta cuántos libros tienen este autor como 'id_autor_principal'
            cursor.execute("SELECT COUNT(*) FROM libros WHERE id_autor_principal = ?", (autor_id,))
            count = cursor.fetchone()[0]

            if count == 0:
                # Si el contador es 0, significa que el autor NO es autor principal de ningún libro
                cursor.execute("DELETE FROM autores WHERE id = ?", (autor_id,))
                conn.commit()
                return True
            else:
                return False

        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR: Fallo al verificar/eliminar autor huérfano ID {autor_id}: {e}")
            return False
        except Exception as e:
            print(f"ERROR INESPERADO al verificar/eliminar autor huérfano ID {autor_id}: {e}")
            return False

    def eliminar_idioma_si_huerfano(self, idioma_id: int) -> bool:
        conn = self.get_db()
        cursor = conn.cursor()
        print(
            f"DEBUG: [eliminar_idioma_si_huerfano] Entrando para idioma_id: {idioma_id}")
        try:
            idioma = cursor.execute('SELECT nombre_idioma FROM idiomas WHERE id = ?', (idioma_id,)).fetchone()
            if not idioma:
                print(
                    f"ADVERTENCIA: [elimeliminar_idioma_si_huerfano] Intento de verificar idioma huérfano para ID {idioma_id}, pero el idioma no existe.")
                return False

            cursor.execute("SELECT COUNT(*) FROM libros WHERE id_idioma = ?", (idioma_id,))
            count = cursor.fetchone()[0]
            print(f"DEBUG: [eliminar_idioma_si_huerfano] Idioma '{idioma['nombre_idioma']}' (ID: {idioma_id}) es referenciado por {count} libro(s).")  # <-- NUEVO/REAFIRMADO DEBUG

            if count == 0:
                cursor.execute("DELETE FROM idiomas WHERE id = ?", (idioma_id,))
                conn.commit()
                print(
                    f"DEBUG: [eliminar_idioma_si_huerfano] Idioma ID {idioma_id} ('{idioma['nombre_idioma']}') ELIMINADO porque ya no está asociado a ningún libro.")
                return True
            else:
                print(
                    f"DEBUG: [eliminar_idioma_si_huerfano] Idioma ID {idioma_id} ('{idioma['nombre_idioma']}') NO ELIMINADO. Aún está asociado a {count} libro(s).")
                return False
        except sqlite3.Error as e:
            conn.rollback()
            print(
                f"ERROR: [eliminar_idioma_si_huerfano] Fallo al verificar/eliminar idioma huérfano ID {idioma_id}: {e}")
            return False
        except Exception as e:
            conn.rollback()
            print(
                f"ERROR INESPERADO: [eliminar_idioma_si_huerfano] al verificar/eliminar idioma huérfano ID {idioma_id}: {e}")
            return False

    def eliminar_editorial_si_huerfana(self, editorial_id: int) -> bool:
        conn = self.get_db()
        cursor = conn.cursor()
        print(f"DEBUG: [eliminar_editorial_si_huerfana] -> Entrando. ID de Editorial a revisar: {editorial_id}")
        try:
            editorial = cursor.execute('SELECT nombre_editorial FROM editoriales WHERE id = ?',
                                       (editorial_id,)).fetchone()
            if not editorial:
                print(
                    f"DEBUG: [eliminar_editorial_si_huerfana] ADVERTENCIA: Editorial ID {editorial_id} NO ENCONTRADA.")
                return False

            cursor.execute("SELECT COUNT(*) FROM libros WHERE id_editorial = ?", (editorial_id,))
            count = cursor.fetchone()[0]
            print(
                f"DEBUG: [eliminar_editorial_si_huerfana] Editorial '{editorial['nombre_editorial']}' (ID: {editorial_id}) es usado por {count} libro(s).")

            if count == 0:
                cursor.execute("DELETE FROM editoriales WHERE id = ?", (editorial_id,))
                conn.commit()
                print(
                    f"DEBUG: [eliminar_editorial_si_huerfana] EXITO: Editorial ID {editorial_id} ('{editorial['nombre_editorial']}') BORRADA porque ya no la usa ningún libro.")
                return True
            else:
                print(
                    f"DEBUG: [eliminar_editorial_si_huerfana] NO BORRADA: Editorial ID {editorial_id} ('{editorial['nombre_editorial']}') AÚN USADA por {count} libro(s).")
                return False
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR: [eliminar_editorial_si_huerfana] Error de SQLite para ID {editorial_id}: {e}")
            return False
        except Exception as e:
            conn.rollback()
            print(f"ERROR: [eliminar_editorial_si_huerfana] Error INESPERADO para ID {editorial_id}: {e}")
            return False

    def get_paginated_books(self, params: Dict[str, Any], mode: str = 'list') -> Dict[str, Any]:
        conn = self.get_db()

        # Recopilar parámetros del diccionario `params`
        search_query = params.get('q', '').strip()
        page_str = params.get('page', '1')  # Obtener como string, con '1' como valor por defecto
        try:
            page = int(page_str)
        except ValueError:
            page = 1

        sort_by = params.get('sort_by', '').strip()
        sort_direction = params.get('sort_direction', '').upper()
        filter_material_type = params.get('filter_material_type', '').strip()
        additional_params = {k: v for k, v in params.items() if k not in [
            'q', 'page', 'sort_by', 'sort_direction', 'filter_material_type'
        ]}

        params_for_sql_select: List[Any] = []
        where_clauses_for_filtering: List[str] = []
        params_for_where_clause: List[Any] = []

        clean_search_query_lower = remove_accents(search_query).lower()

        relevance_score_select_clause = "0 AS relevance_score"

        allowed_sort_columns = {
            'titulo': 'remove_accents(l.titulo)',
            'autor_principal': 'remove_accents(a.nombre_autor)',
            'anio': 'l.anio',
            'codigo_cdu': 'c.codigo_cdu',
            'materia': 'c.materia',
            'disponible': 'l.disponible',
            'id': 'l.id'
        }

        order_by_parts: List[str] = []
        actual_sort_column_sql = allowed_sort_columns.get(sort_by)
        if actual_sort_column_sql:
            direction = 'ASC' if sort_direction == 'ASC' else 'DESC'
            order_by_parts.append(f"{actual_sort_column_sql} {direction}")

        if filter_material_type:
            cdu_conditions = map_material_type_to_cdu_conditions(filter_material_type)
            if cdu_conditions:
                where_clauses_for_filtering.append("(" + " OR ".join(cdu_conditions) + ")")

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

                if order_by_parts:
                    final_order_by_clause = f"ORDER BY relevance_score DESC, {', '.join(order_by_parts)}, l.id ASC"
                else:
                    final_order_by_clause = "ORDER BY relevance_score DESC, l.id ASC"
        else:
            if order_by_parts:
                final_order_by_clause = f"ORDER BY {', '.join(order_by_parts)}, l.id ASC"
            else:
                final_order_by_clause = "ORDER BY l.id ASC"

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

        total_pages = math.ceil(total_results / PER_PAGE) if total_results > 0 else 1

        page = max(1, min(page, max(1, total_pages)))
        offset = (page - 1) * PER_PAGE

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
        final_params = params_for_sql_select + params_for_where_clause + [PER_PAGE, offset]

        libros = conn.execute(sql_query, final_params).fetchall()

        return_data = {
            'libros': libros,
            'q': search_query,
            'page': page,
            'per_page': PER_PAGE,
            'total_pages': total_pages,
            'total_results': total_results,
            'sort_by': sort_by,
            'sort_direction': sort_direction,
            'filter_material_type': filter_material_type,
            'base_ajax_url': 'books.listar_libros_ajax' if mode == 'list' else 'books.listar_libros_select_ajax'
        }
        # Añadir todos los parámetros adicionales que se recibieron a la data de retorno
        return_data.update(additional_params)
        return return_data

    def get_book_details(self, book_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene los detalles de un libro por su ID."""
        conn = self.get_db()
        libro = conn.execute('''
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
        if libro:
            return dict(libro)
        return None

    def get_book_loans(self, book_id: int) -> List[Dict[str, Any]]:
        """Obtiene el historial de préstamos de un libro."""
        conn = self.get_db()
        prestamos = conn.execute('''
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
        return [dict(row) for row in prestamos]

    def get_book_for_edit(self, book_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene los datos de un libro para el formulario de edición."""
        conn = self.get_db()
        libro_data_db = conn.execute('''
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

        if libro_data_db:
            return {
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
        return None

    def add_book(self, form_data: Dict[str, Any]) -> Optional[str]:
        conn = self.get_db()
        materia_input = form_data.get('materia', '').strip().upper()
        try:
            num_reg_input = form_data.get('num_reg', '').strip()
            titulo = form_data.get('titulo', '').strip().upper()
            subtitulo = form_data.get('subtitulo', '').strip().upper()
            autor_principal_nombre = form_data.get('autor_principal', '').strip().upper()
            segundo_autor = form_data.get('segundo_autor', '').strip().upper()
            tercer_autor = form_data.get('tercer_autor', '').strip().upper()
            codigo_cdu_input = form_data.get('codigo_cdu', '').strip().upper()
            materia_input = form_data.get('materia', '').strip().upper()
            nombre_editorial_input = form_data.get('nombre_editorial', '').strip().upper()
            nombre_idioma_input = form_data.get('nombre_idioma', '').strip().upper()
            anio_str = form_data.get('anio', '').strip()
            paginas_str = form_data.get('paginas', '').strip()
            isbn = form_data.get('isbn', '').strip().upper()
            observaciones = form_data.get('observaciones', '').strip()
            disponible = 'Si'

            # Validaciones básicas
            errors = []
            if not titulo: errors.append('El título es un campo obligatorio.')
            if not autor_principal_nombre: errors.append('El autor principal es un campo obligatorio.')
            if not codigo_cdu_input: errors.append('El código CDU es un campo obligatorio.')
            if not materia_input: errors.append('La materia es un campo obligatorio.')
            if not nombre_editorial_input: errors.append('La editorial es un campo obligatorio.')
            if not nombre_idioma_input: errors.append('El idioma es un campo obligatorio.')

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

            libro_id = None
            if num_reg_input:
                try:
                    libro_id = int(num_reg_input)
                    if libro_id <= 0: errors.append('El número de registro debe ser un entero positivo.')
                except ValueError:
                    errors.append('El número de registro debe ser un número entero válido.')

                if not errors:
                    existing_libro = conn.execute("SELECT id FROM libros WHERE id = ?", (libro_id,)).fetchone()
                    if existing_libro:
                        errors.append(f'El número de registro {libro_id} ya existe. Por favor, elija otro.')

            if errors:
                return "\n".join(errors)

            # Gestión de Autor Principal
            cursor = conn.execute("SELECT id FROM autores WHERE nombre_autor = ?", (autor_principal_nombre,))
            autor_principal_id_row = cursor.fetchone()
            if not autor_principal_id_row:
                conn.execute("INSERT INTO autores (nombre_autor) VALUES (?)", (autor_principal_nombre,))
                conn.commit()
                autor_principal_id_row = conn.execute("SELECT id FROM autores WHERE nombre_autor = ?",
                                                      (autor_principal_nombre,)).fetchone()
            id_autor_principal = autor_principal_id_row['id']

            # Gestión de CDU
            cdu_existing_entry = conn.execute("SELECT id, materia FROM cdu WHERE codigo_cdu = ?",
                                              (codigo_cdu_input,)).fetchone()

            if cdu_existing_entry:
                # Si el código CDU ya existe, usamos su ID.
                id_cdu = cdu_existing_entry['id']
                # Además, comprobamos si la materia asociada ha cambiado y la actualizamos.
                if cdu_existing_entry['materia'] != materia_input:
                    conn.execute("UPDATE cdu SET materia = ? WHERE id = ?", (materia_input, id_cdu))
                    conn.commit()
            else:
                # Si el código CDU NO existe, lo insertamos.
                conn.execute("INSERT INTO cdu (codigo_cdu, materia) VALUES (?, ?)", (codigo_cdu_input, materia_input))
                conn.commit()

                id_cdu = conn.execute("SELECT id FROM cdu WHERE codigo_cdu = ?", (codigo_cdu_input,)).fetchone()['id']

            # Gestión de Editorial
            editorial_id_row = conn.execute("SELECT id FROM editoriales WHERE nombre_editorial = ?",(nombre_editorial_input,)).fetchone()
            if not editorial_id_row:
                conn.execute("INSERT INTO editoriales (nombre_editorial) VALUES (?)", (nombre_editorial_input,))
                conn.commit()
                editorial_id_row = conn.execute("SELECT id FROM editoriales WHERE nombre_editorial = ?",
                                                (nombre_editorial_input,)).fetchone()
            id_editorial = editorial_id_row['id']

            # Gestión de Idioma
            idioma_id_row = conn.execute("SELECT id FROM idiomas WHERE nombre_idioma = ?",
                                         (nombre_idioma_input,)).fetchone()
            if not idioma_id_row:
                conn.execute("INSERT INTO idiomas (nombre_idioma) VALUES (?)", (nombre_idioma_input,))
                conn.commit()
                idioma_id_row = conn.execute("SELECT id FROM idiomas WHERE nombre_idioma = ?",
                                             (nombre_idioma_input,)).fetchone()
            id_idioma = idioma_id_row['id']

            # Generar Letras de Autor y Título
            let_autor = remove_accents(autor_principal_nombre)[:3].upper() if autor_principal_nombre else ''
            let_titulo = titulo[:3].lower() if titulo else ''

            # Inserción en la tabla de libros
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
            return None

        except sqlite3.IntegrityError as e:
            conn.rollback()
            if "UNIQUE constraint failed: cdu.materia" in str(
                    e) or "UNIQUE constraint failed: cdu.codigo_cdu, cdu.materia" in str(e):
                existing_cdu = conn.execute("SELECT codigo_cdu, materia FROM cdu WHERE materia = ?",
                                            (materia_input,)).fetchone()
                if existing_cdu:
                    return f'Esa materia ya existe y su CDU asociado no es ese. El CDU para la materia "{existing_cdu["materia"]}" es "{existing_cdu["codigo_cdu"]}".'
                else:
                    return f'Error de integridad: Un valor que intentaste introducir ya existe o no es válido. {e}'
            elif "UNIQUE constraint failed: libros.id" in str(e) and form_data.get('num_reg'):
                return 'El Número de Registro (ID) que has introducido ya existe. Por favor, elige otro o déjalo vacío para asignación automática.'
            else:
                return f'Ocurrió un error de integridad en la base de datos: {e}. Asegúrate de que todas las referencias existen y el ID es único.'
        except Exception as e:
            conn.rollback()
            return f'Ocurrió un error inesperado al añadir el libro: {e}'

    def update_book(self, book_id: int, form_data: Dict[str, Any]) -> Optional[str]:
        conn = self.get_db()
        materia_input = form_data.get('materia', '').strip().upper()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id_autor_principal,id_editorial, id_idioma FROM libros WHERE id = ?", (book_id,))
            book_current_info = cursor.fetchone()
            old_autor_id = book_current_info['id_autor_principal'] if book_current_info else None
            old_editorial_id = book_current_info['id_editorial'] if book_current_info else None
            old_idioma_id = book_current_info['id_idioma'] if book_current_info else None
            titulo = form_data.get('titulo', '').strip().upper()
            subtitulo = form_data.get('subtitulo', '').strip()
            autor_principal_nombre = form_data.get('autor_principal', '').strip().upper()
            segundo_autor = form_data.get('segundo_autor', '').strip()
            tercer_autor = form_data.get('tercer_autor', '').strip()
            codigo_cdu_input = form_data.get('codigo_cdu', '').strip().upper()
            nombre_editorial_input = form_data.get('nombre_editorial', '').strip().upper()
            nombre_idioma_input = form_data.get('nombre_idioma', '').strip().upper()
            anio_str = form_data.get('anio')
            paginas_str = form_data.get('paginas')
            isbn = form_data.get('isbn', '').strip()
            observaciones = form_data.get('observaciones', '').strip()

            errors = []
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

            if not titulo: errors.append('El título es un campo obligatorio.')
            if not autor_principal_nombre: errors.append('El autor principal es un campo obligatorio.')
            if not codigo_cdu_input: errors.append('El código CDU es un campo obligatorio.')
            if not materia_input: errors.append('La materia es un campo obligatorio.')
            if not nombre_editorial_input: errors.append('La editorial es un campo obligatorio.')
            if not nombre_idioma_input: errors.append('El idioma es un campo obligatorio.')

            if errors:
                return "\n".join(errors)

            autor_principal_id_row = conn.execute("SELECT id FROM autores WHERE nombre_autor = ?",
                                                  (autor_principal_nombre,)).fetchone()
            if not autor_principal_id_row:
                conn.execute("INSERT INTO autores (nombre_autor) VALUES (?)", (autor_principal_nombre,))
                conn.commit()
                autor_principal_id_row = conn.execute("SELECT id FROM autores WHERE nombre_autor = ?",
                                                      (autor_principal_nombre,)).fetchone()
            id_autor_principal = autor_principal_id_row['id']

            cdu_entry = conn.execute("SELECT id, materia FROM cdu WHERE codigo_cdu = ?",
                                     (codigo_cdu_input,)).fetchone()
            if cdu_entry:
                id_cdu = cdu_entry['id']
                if cdu_entry['materia'] != materia_input:
                    conn.execute("UPDATE cdu SET materia = ? WHERE id = ?", (materia_input, id_cdu))
                    conn.commit()
            else:
                conn.execute("INSERT INTO cdu (codigo_cdu, materia) VALUES (?, ?)", (codigo_cdu_input, materia_input))
                conn.commit()
                id_cdu = conn.execute("SELECT id FROM cdu WHERE codigo_cdu = ?", (codigo_cdu_input,)).fetchone()['id']

            editorial_id_row = conn.execute("SELECT id FROM editoriales WHERE nombre_editorial = ?",
                                              (nombre_editorial_input,)).fetchone()
            if not editorial_id_row:
                conn.execute("INSERT INTO editoriales (nombre_editorial) VALUES (?)", (nombre_editorial_input,))
                conn.commit()
                editorial_id_row = conn.execute("SELECT id FROM editoriales WHERE nombre_editorial = ?",
                                                  (nombre_editorial_input,)).fetchone()
            id_editorial = editorial_id_row['id']

            idioma_id_row = conn.execute("SELECT id FROM idiomas WHERE nombre_idioma = ?",
                                           (nombre_idioma_input,)).fetchone()
            if not idioma_id_row:
                conn.execute("INSERT INTO idiomas (nombre_idioma) VALUES (?)", (nombre_idioma_input,))
                conn.commit()
                idioma_id_row = conn.execute("SELECT id FROM idiomas WHERE nombre_idioma = ?",
                                               (nombre_idioma_input,)).fetchone()
            id_idioma = idioma_id_row['id']

            let_autor = remove_accents(autor_principal_nombre)[:3].upper() if autor_principal_nombre else ''
            let_titulo = titulo[:3].lower() if titulo else ''

            conn.execute('''
                UPDATE libros SET
                    id_cdu = ?, let_autor = ?, let_titulo = ?, titulo = ?, subtitulo = ?,
                    id_autor_principal = ?, segundo_autor = ?, tercer_autor = ?,
                    anio = ?, id_editorial = ?, paginas = ?, id_idioma = ?,
                    observaciones = ?, isbn = ?
                WHERE id = ?
            ''',
                           (
                               id_cdu, let_autor, let_titulo, titulo, subtitulo,
                               id_autor_principal, segundo_autor, tercer_autor,
                               anio, id_editorial, paginas, id_idioma,
                               observaciones, isbn, book_id
                           ))
            conn.commit()
            if old_autor_id is not None and old_autor_id != id_autor_principal:
                self.eliminar_autor_si_huerfano(old_autor_id)

            if old_idioma_id is not None and old_idioma_id != id_idioma:
                self.eliminar_idioma_si_huerfano(old_idioma_id)

            print(f"DEBUG: [update_book] Revisando editorial. Editorial original (OLD): {old_editorial_id}, Editorial nueva (NEW): {id_editorial}")
            if old_editorial_id is not None and old_editorial_id != id_editorial:
                print(f"DEBUG: [update_book] ¡Cambio de editorial detectado! Llamando a eliminar_editorial_si_huerfana para OLD ID: {old_editorial_id}")
                self.eliminar_editorial_si_huerfana(old_editorial_id)
            else:
                print(
                    f"DEBUG: [update_book] No hubo cambio de editorial o la editorial original era None. No se necesita limpieza de editorial en este update.")
            return None  # Éxito

        except sqlite3.IntegrityError as e:
            conn.rollback()
            if "UNIQUE constraint failed: cdu.materia" in str(
                    e) or "UNIQUE constraint failed: cdu.codigo_cdu, cdu.materia" in str(e):
                existing_cdu = conn.execute("SELECT codigo_cdu, materia FROM cdu WHERE materia = ?",
                                              (materia_input,)).fetchone()
                if existing_cdu:
                    return f'Esa materia ya existe y su CDU asociado no es ese. El CDU para la materia "{existing_cdu["materia"]}" es "{existing_cdu["codigo_cdu"]}".'
                else:
                    return f'Error de integridad: Un valor que intentaste introducir ya existe o no es válido. {e}'
            else:
                return f'Ocurrió un error de integridad en la base de datos: {e}. Asegúrate de que todas las referencias existen y el ID es único.'
        except Exception as e:
            conn.rollback()
            return f'Ocurrió un error inesperado al actualizar el libro: {e}'

    def delete_book(self, book_id: int) -> Optional[str]:
        conn = self.get_db()
        libro_info = conn.execute(
            "SELECT titulo, disponible, id_autor_principal, id_editorial, id_idioma FROM libros WHERE id = ?",
            (book_id,)).fetchone()

        if libro_info is None:
            print(f"ERROR: [delete_book] Intento de eliminar libro ID {book_id}, pero no se encontró.")
            return 'Libro no encontrado para eliminar.'

        if libro_info['disponible'] == 'No':
            print(f"ADVERTENCIA: [delete_book] No se puede eliminar libro ID {book_id} ('{libro_info['titulo']}') porque está prestado.")
            return f'No se puede eliminar el libro "{libro_info["titulo"]}" porque está actualmente prestado (estado "No disponible"). Primero debe ser devuelto.'

        try:
            # Obtener los IDs de autor, editorial e idioma ANTES de borrar el libro
            autor_id_to_check = libro_info['id_autor_principal']
            editorial_id_to_check = libro_info['id_editorial']
            idioma_id_to_check = libro_info['id_idioma']
            conn.execute("DELETE FROM libros WHERE id = ?", (book_id,))
            conn.commit()
            self.eliminar_autor_si_huerfano(autor_id_to_check)

            if idioma_id_to_check is not None:
                self.eliminar_idioma_si_huerfano(idioma_id_to_check)

            print(
                f"DEBUG: [delete_book] Verificando editorial ID {editorial_id_to_check} después de eliminar libro {book_id}.")
            if editorial_id_to_check is not None:
                print(f"DEBUG: [delete_book] Llamando a eliminar_editorial_si_huerfana para ID: {editorial_id_to_check}")
                self.eliminar_editorial_si_huerfana(editorial_id_to_check)
            else:
                print(f"DEBUG: [delete_book] Editorial original era None para libro ID {book_id}. No se llama a eliminar_editorial_si_huerfana.")
            return None  # Éxito

        except sqlite3.IntegrityError as e:
            conn.rollback()
            print(f"ERROR: [delete_book] Error de integridad al eliminar libro ID {book_id}: {e}")
            if "FOREIGN KEY constraint failed" in str(e):
                return f'No se puede eliminar el libro "{libro_info["titulo"]}" porque tiene un historial de préstamos asociado. Solo se pueden eliminar libros que nunca han sido prestados.'
            else:
                return f'Ocurrió un error de integridad en la base de datos al intentar eliminar el libro: {e}'
        except Exception as e:
            conn.rollback()
            print(f"ERROR INESPERADO: [delete_book] Error inesperado al eliminar libro ID {book_id}: {e}")
            return f'Ocurrió un error inesperado al eliminar el libro: {e}'

    def autocomplete_authors(self, term: str) -> List[str]:
        conn = self.get_db()
        if not term: return []
        search_term = '%' + remove_accents(term).upper() + '%'
        authors = conn.execute(
            "SELECT nombre_autor FROM autores WHERE remove_accents(nombre_autor) LIKE ? ORDER BY nombre_autor LIMIT 10",
            (search_term,)
        ).fetchall()
        return [row['nombre_autor'] for row in authors]

    def autocomplete_titles(self, term: str) -> List[Dict[str, Any]]:
        conn = self.get_db()
        if not term:
            return []

        clean_term = unicodedata.normalize('NFKD', term).encode('ascii', 'ignore').decode('utf-8').upper()

        search_pattern = clean_term + '%'
        params: List[Any] = [search_pattern, clean_term]

        sql_query = f"""
            SELECT id, titulo
            FROM libros
            WHERE UPPER(remove_accents(titulo)) LIKE ? -- Aquí se filtra SOLO por prefijo en el título.
            ORDER BY
                CASE
                    WHEN UPPER(remove_accents(titulo)) = ? THEN 1 -- Prioridad máxima para coincidencia EXACTA del término completo.
                    ELSE 0
                END DESC,
                titulo ASC                                       -- Luego, ordena los resultados alfabéticamente por título.
            LIMIT 10                                             -- Limita a 10 resultados para no sobrecargar.
        """

        # Estos prints son CRÍTICOS si algo falla, para que puedas ver qué consulta se está generando.
        print(f"\nDEBUG (autocomplete_titles): SQL Query:\n{sql_query}")
        print(f"DEBUG (autocomplete_titles): Final Query Params: {params}\n")

        # Ejecuta la consulta y obtiene los resultados.
        results = conn.execute(sql_query, params).fetchall()

        # Devuelve una lista de diccionarios con 'label' (el texto a mostrar en el autocompletado) y 'value' (el ID real del libro).
        # Ya NO se incluye el subtítulo en el label, porque la búsqueda y sugerencia es solo por título.
        return [{'label': row['titulo'], 'value': row['id']} for row in results]


    def autocomplete_publishers(self, term: str) -> List[str]:
        conn = self.get_db()
        if not term: return []
        search_term = '%' + remove_accents(term).upper() + '%'
        publishers = conn.execute(
            "SELECT nombre_editorial FROM editoriales WHERE remove_accents(nombre_editorial) LIKE ? ORDER BY nombre_editorial LIMIT 10",
            (search_term,)
        ).fetchall()
        return [row['nombre_editorial'] for row in publishers]

    def autocomplete_languages(self, term: str) -> List[str]:
        conn = self.get_db()
        if not term: return []
        search_term = '%' + remove_accents(term).upper() + '%'
        languages = conn.execute(
            "SELECT nombre_idioma FROM idiomas WHERE remove_accents(nombre_idioma) LIKE ? ORDER BY nombre_idioma LIMIT 10",
            (search_term,)
        ).fetchall()
        return [row['nombre_idioma'] for row in languages]

    def autocomplete_cdu_codes(self, term: str) -> List[str]:
        conn = self.get_db()
        if not term: return []
        search_term = '%' + remove_accents(term).upper() + '%'
        cdu_codes = conn.execute(
            "SELECT codigo_cdu FROM cdu WHERE remove_accents(codigo_cdu) LIKE ? ORDER BY codigo_cdu LIMIT 10",
            (search_term,)
        ).fetchall()
        return [row['codigo_cdu'] for row in cdu_codes]

    def autocomplete_cdu_subjects(self, term: str) -> List[str]:
        conn = self.get_db()
        if not term: return []
        search_term = '%' + remove_accents(term).upper() + '%'
        cdu_subjects = conn.execute(
            "SELECT materia FROM cdu WHERE remove_accents(materia) LIKE ? ORDER BY materia LIMIT 10",
            (search_term,)
        ).fetchall()
        return [row['materia'] for row in cdu_subjects]
