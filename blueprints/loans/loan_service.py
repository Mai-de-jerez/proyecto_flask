# blueprints/loans/loan_service.py
import sqlite3
import unicodedata
import math
from typing import List, Any, Dict, Optional
from datetime import date, timedelta, datetime

# Constante de paginación para préstamos
PER_PAGE = 10
LOAN_TERM_DAYS = 15

def remove_accents(input_str: str) -> str:
    """Elimina tildes y caracteres combinantes de una cadena."""
    if not isinstance(input_str, str):
        return input_str
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


class LoanService:
    def __init__(self, db_connection_factory):
        self.get_db = db_connection_factory


    @staticmethod
    def _update_overdue_loans(conn: sqlite3.Connection):
        """Actualiza el estado de los préstamos a 'Vencido' si han superado la fecha estimada."""
        today_date = date.today().isoformat()
        conn.execute('''
            UPDATE prestamos
            SET estado_prestamo = 'Vencido'
            WHERE fecha_devolucion_real IS NULL
            AND fecha_devolucion_estimada IS NOT NULL
            AND fecha_devolucion_estimada < ?
            AND estado_prestamo != 'Vencido';
        ''', (today_date,))
        conn.commit()

    def get_paginated_loans(self, params: Dict[str, Any]) -> Dict[str, Any]:
        conn = self.get_db()
        cursor = conn.cursor()

        # Asegurarse de que los préstamos vencidos estén actualizados antes de la consulta
        self._update_overdue_loans(conn)

        # Recopilar parámetros
        search_query = params.get('q', '').strip()
        page_str = params.get('page', '1')
        try:
            page = int(page_str)
        except ValueError:
            page = 1

        # Nuevos parámetros de filtro y ordenación
        filter_status = params.get('filter_status', '').strip()
        sort_by = params.get('sort_by', 'fecha_prestamo').strip()
        sort_direction = params.get('sort_direction', 'desc').upper()

        base_sql_from_join = '''
            FROM prestamos AS p
            JOIN usuarios AS u ON p.id_usuario = u.id
            JOIN libros AS l ON p.id_libro = l.id
            JOIN autores AS a ON l.id_autor_principal = a.id
        '''

        # Listas para almacenar los parámetros de la consulta y las condiciones WHERE
        params_for_where_clause: List[Any] = []
        where_clauses: List[str] = []

        if search_query:
            clean_search_query_lower = remove_accents(search_query).lower()
            search_pattern = f'%{clean_search_query_lower}%'

            # Condiciones de búsqueda por nombre de usuario, título de libro y autor
            where_clauses.append(
                "(u.nombre COLLATE NOACCENTS LIKE ? OR u.apellidos COLLATE NOACCENTS LIKE ? OR l.titulo COLLATE NOACCENTS LIKE ? OR a.nombre_autor COLLATE NOACCENTS LIKE ?)"
            )
            params_for_where_clause.extend([search_pattern, search_pattern, search_pattern, search_pattern])

        # Añadir filtro por estado del préstamo
        if filter_status:
            # Asegurarse de que el estado sea uno de los valores permitidos
            if filter_status in ['Prestado', 'Devuelto', 'Vencido']:
                where_clauses.append("p.estado_prestamo = ?")
                params_for_where_clause.append(filter_status)
            else:
                # Opcional: Loggear o manejar un valor de filter_status inválido
                print(f"Advertencia: filter_status '{filter_status}' no es válido. Ignorando filtro.")

        sql_where_clause_string = ""
        if where_clauses:
            sql_where_clause_string = " WHERE " + " AND ".join(where_clauses)

        # Contar resultados totales
        count_query = f"SELECT COUNT(*) {base_sql_from_join} {sql_where_clause_string}"
        total_results = cursor.execute(count_query, params_for_where_clause).fetchone()[0]

        total_pages = math.ceil(total_results / PER_PAGE) if total_results > 0 else 1
        page = max(1, min(page, max(1, total_pages)))
        offset = (page - 1) * PER_PAGE
        order_by_sql_parts = ["p.fecha_prestamo DESC", "p.id DESC"]

        if sort_by == 'fecha_prestamo':
            direction = 'ASC' if sort_direction == 'ASC' else 'DESC'
            order_by_sql_parts = [f"p.fecha_prestamo {direction}", "p.id DESC"]
        elif sort_by == 'fecha_devolucion_estimada':
            direction = 'ASC' if sort_direction == 'ASC' else 'DESC'
            order_by_sql_parts = [f"p.fecha_devolucion_estimada {direction}", "p.id DESC"]
        elif sort_by == 'titulo_libro':
            direction = 'ASC' if sort_direction == 'ASC' else 'DESC'
            order_by_sql_parts = [f"l.titulo COLLATE NOACCENTS {direction}"]
        elif sort_by == 'nombre_usuario':
            direction = 'ASC' if sort_direction == 'ASC' else 'DESC'
            order_by_sql_parts = [
                f"u.apellidos COLLATE NOACCENTS {direction}",
                f"u.nombre COLLATE NOACCENTS {direction}"
            ]

        order_by_clause = f" ORDER BY {', '.join(order_by_sql_parts)}"

        main_sql_select_fields = '''
            p.id,
            l.titulo AS libro_titulo,
            u.apellidos || ', ' || u.nombre AS usuario_nombre_completo,
            p.fecha_prestamo,
            p.fecha_devolucion_estimada,
            p.fecha_devolucion_real,
            p.estado_prestamo
        '''

        sql_query = f"SELECT {main_sql_select_fields} {base_sql_from_join} {sql_where_clause_string} {order_by_clause} LIMIT ? OFFSET ?"
        final_params = params_for_where_clause + [PER_PAGE, offset]


        prestamos = cursor.execute(sql_query, final_params).fetchall()

        return {
            'prestamos': [dict(row) for row in prestamos],
            'q': search_query,
            'page': page,
            'per_page': PER_PAGE,
            'total_pages': total_pages,
            'total_results': total_results,
            'filter_status': filter_status,
            'sort_by': sort_by,
            'sort_direction': sort_direction,
            'base_ajax_url': 'loans.listar_prestamos_ajax'
        }

    def get_loan_form_initial_data(self, request_args: Dict[str, Any]) -> Dict[str, Any]:
        conn = self.get_db()
        cursor = conn.cursor()

        today_date = date.today().isoformat()
        estimated_return_date = (date.today() + timedelta(days=LOAN_TERM_DAYS)).isoformat()

        usuario_preseleccionado = None
        id_usuario_param = request_args.get('id_usuario_seleccionado')

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
        id_libro_param = request_args.get('id_libro_seleccionado')

        if id_libro_param:
            libro_details = cursor.execute("SELECT id, titulo FROM libros WHERE id = ?", (id_libro_param,)).fetchone()
            if libro_details:
                libro_preseleccionado = {
                    'id': libro_details['id'],
                    'titulo': libro_details['titulo']
                }

        # También pasamos las fechas que puedan venir en los parámetros de la URL
        fecha_prestamo_url = request_args.get('fecha_prestamo', today_date)
        fecha_devolucion_estimada_url = request_args.get('fecha_devolucion_estimada', estimated_return_date)

        return {
            'today_date': fecha_prestamo_url,
            'estimated_return_date': fecha_devolucion_estimada_url,
            'usuario_preseleccionado': usuario_preseleccionado,
            'libro_preseleccionado': libro_preseleccionado
        }

    def add_loan(self, form_data: Dict[str, Any]) -> Optional[str]:
        """Añade un nuevo préstamo a la base de datos."""
        conn = self.get_db()
        cursor = conn.cursor()
        errors = []

        id_prestamo_input = form_data.get('id_prestamo')
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

        id_usuario = form_data.get('id_usuario')
        id_libro = form_data.get('id_libro')
        fecha_prestamo_form = form_data.get('fecha_prestamo')
        fecha_devolucion_estimada_form = form_data.get('fecha_devolucion_estimada')

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
            errors.append('Formato de fecha inválido. Usa AAAA-MM-DD.')
            prestamo_date = None
            devolucion_estimada_date = None

        if prestamo_date and devolucion_estimada_date and prestamo_date > devolucion_estimada_date:
            errors.append('La fecha de devolución estimada no puede ser anterior a la fecha de préstamo.')

        if errors:
            return "\n".join(errors)

        try:
            libro_disponible = cursor.execute("SELECT disponible FROM libros WHERE id = ?", (id_libro,)).fetchone()
            if not libro_disponible or libro_disponible['disponible'] != 'Si':
                return 'El libro seleccionado no está disponible para préstamo.'

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
                prestamo_id_generado = cursor.lastrowid  # Obtener el ID generado automáticamente

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
            return None  # Éxito
        except sqlite3.Error as e:
            conn.rollback()
            return f'Error de base de datos al realizar el préstamo: {e}'
        except Exception as e:
            conn.rollback()
            return f'Ocurrió un error inesperado al realizar el préstamo: {e}'

    def return_loan(self, id_prestamo: int) -> Optional[str]:
        """Registra la devolución de un préstamo."""
        conn = self.get_db()
        cursor = conn.cursor()

        try:
            prestamo_info = cursor.execute(
                'SELECT id_libro, id_usuario, fecha_devolucion_real, estado_prestamo FROM prestamos WHERE id = ?',
                (id_prestamo,)).fetchone()

            if prestamo_info is None:
                return 'Préstamo no encontrado.'

            if prestamo_info['fecha_devolucion_real'] is not None:
                return 'Este préstamo ya ha sido devuelto.'

            if prestamo_info['estado_prestamo'] == 'Devuelto':
                return 'Este préstamo ya ha sido devuelto.'

            id_libro = prestamo_info['id_libro']
            id_usuario = prestamo_info['id_usuario']
            fecha_devolucion_actual = datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
                UPDATE prestamos
                SET fecha_devolucion_real = ?, estado_prestamo = 'Devuelto'
                WHERE id = ?
            ''', (fecha_devolucion_actual, id_prestamo))

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
            return None  # Éxito

        except sqlite3.Error as e:
            conn.rollback()
            return f'Error de base de datos al devolver el préstamo: {e}'
        except Exception as e:
            conn.rollback()
            return f'Ocurrió un error inesperado al devolver el préstamo: {e}'

    def get_loan_details(self, id_prestamo: int) -> Optional[Dict[str, Any]]:
        """Obtiene los detalles completos de un préstamo."""
        conn = self.get_db()
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
            LEFT JOIN modulos AS m ON u.id_modulo = m.id
            WHERE p.id = ?
        ''', (id_prestamo,)).fetchone()

        if prestamo:
            return dict(prestamo)
        return None

    def delete_loan(self, id_prestamo: int) -> Optional[str]:
        """Elimina un préstamo y actualiza el estado del libro/usuario si es necesario."""
        conn = self.get_db()
        cursor = conn.cursor()

        try:
            prestamo_info = cursor.execute(
                'SELECT id_libro, id_usuario, fecha_devolucion_real, estado_prestamo FROM prestamos WHERE id = ?',
                (id_prestamo,)).fetchone()

            if prestamo_info is None:
                return 'Préstamo no encontrado.'

            id_libro = prestamo_info['id_libro']
            id_usuario = prestamo_info['id_usuario']
            fecha_devolucion_real = prestamo_info['fecha_devolucion_real']
            estado_prestamo = prestamo_info['estado_prestamo']

            # Si el préstamo NO ha sido devuelto (fecha_devolucion_real es NULL)
            if fecha_devolucion_real is None and estado_prestamo != 'Devuelto':
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

            # Eliminar el registro del préstamo de la tabla 'prestamos'
            cursor.execute('DELETE FROM prestamos WHERE id = ?', (id_prestamo,))
            conn.commit()

            return None  # Éxito

        except sqlite3.Error as e:
            conn.rollback()
            return f'Error de base de datos al eliminar el préstamo: {e}'
        except Exception as e:
            conn.rollback()
            return f'Ocurrió un error inesperado al eliminar el préstamo: {e}'