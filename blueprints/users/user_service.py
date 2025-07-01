# talegoTK_Flask/blueprints/users/user_service.py
import sqlite3
import unicodedata
import math
from typing import List, Any, Dict, Optional

# Constante de paginación para usuarios (tomada del original)
PER_PAGE_USERS = 20

def remove_accents(input_str: str) -> str:
    """Elimina tildes y caracteres combinantes de una cadena."""
    if not isinstance(input_str, str):
        return input_str
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

class UserService:
    def __init__(self, db_connection_factory):
        self.get_db = db_connection_factory

    @staticmethod
    def _get_or_create_modulo_id(conn: sqlite3.Connection, modulo_name: str) -> Optional[int]:

        modulo_name_upper = modulo_name.strip().upper()
        existing_modulo = conn.execute("SELECT id FROM modulos WHERE nombre_modulo = ?", (modulo_name_upper,)).fetchone()

        if existing_modulo:
            return existing_modulo['id']
        else:
            try:
                conn.execute("INSERT INTO modulos (nombre_modulo) VALUES (?)", (modulo_name_upper,))
                conn.commit()
                # Obtener el ID del módulo recién insertado
                return conn.execute("SELECT id FROM modulos WHERE nombre_modulo = ?", (modulo_name_upper,)).fetchone()['id']
            except sqlite3.IntegrityError:
                conn.rollback()
                existing_modulo_after_error = conn.execute("SELECT id FROM modulos WHERE nombre_modulo = ?", (modulo_name_upper,)).fetchone()
                if existing_modulo_after_error:
                    return existing_modulo_after_error['id']
                else:
                    return None
            except sqlite3.Error as e:
                conn.rollback()
                print(f"Error de base de datos al crear/obtener módulo: {e}")
                return None
            except Exception as e:
                conn.rollback()
                print(f"Error inesperado al crear/obtener módulo: {e}")
                return None

    def eliminar_modulo_si_huerfano(self, modulo_id: int) -> bool:
        conn = self.get_db()
        cursor = conn.cursor()
        try:
            modulo = cursor.execute('SELECT nombre_modulo FROM modulos WHERE id = ?', (modulo_id,)).fetchone()
            if not modulo:
                return False

            # Cuenta cuántos usuarios tienen este modulo asignado
            cursor.execute("SELECT COUNT(*) FROM usuarios WHERE id_modulo = ?", (modulo_id,))
            count = cursor.fetchone()[0]

            if count == 0:
                # Si el contador es 0, significa que el módulo NO es usado por ningún usuario
                cursor.execute("DELETE FROM modulos WHERE id = ?", (modulo_id,))
                conn.commit()
                return True
            else:
                return False

        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR: [eliminar_modulo_si_huerfano] Error de SQLite para ID {modulo_id}: {e}")
            return False
        except Exception as e:
            conn.rollback()
            print(f"ERROR: [eliminar_modulo_si_huerfano] Error INESPERADO para ID {modulo_id}: {e}")
            return False

    def get_paginated_users(self, params: Dict[str, Any]) -> Dict[str, Any]:
        conn = self.get_db()
        cursor = conn.cursor()

        # Recopilar parámetros
        search_query = params.get('q', '').strip()
        page_str = params.get('page', '1')
        try:
            page = int(page_str)
        except ValueError:
            page = 1

        # Parámetros de ordenación
        sort_by = params.get('sort_by', 'id').strip() # 'id' como orden por defecto
        sort_direction = params.get('sort_direction', 'asc').upper() # 'ASC' por defecto

        params_for_sql_select: List[Any] = []
        where_clauses_for_filtering: List[str] = []
        params_for_where_clause: List[Any] = []

        clean_search_query_lower = unicodedata.normalize('NFKD', search_query.strip()).encode('ascii', 'ignore').decode(
            'utf-8').lower()

        relevance_score_select_clause = "0 AS relevance_score"

        order_by_parts: List[str] = []
        direction = 'ASC' if sort_direction == 'ASC' else 'DESC'  # La dirección se aplica a cada parte de la ordenación

        if sort_by == 'id':
            order_by_parts.append(f"u.id {direction}")
        elif sort_by == 'nombre':
            order_by_parts.append(f"remove_accents(u.nombre) {direction}")
        elif sort_by == 'apellidos':
            order_by_parts.append(f"remove_accents(u.apellidos) {direction}")
        elif sort_by == 'modulo':
            # Lógica para ordenar módulos que son números (ej. 'modulo 1', 'modulo 10') numéricamente
            # y el resto (ej. 'enfermeria') alfabéticamente, colocando los numerados primero.
            order_by_parts.append(f"""
                        CASE
                            WHEN m.nombre_modulo LIKE 'modulo %' THEN 0
                            ELSE 1
                        END {direction},
                        CASE
                            WHEN m.nombre_modulo LIKE 'modulo %' THEN CAST(SUBSTR(m.nombre_modulo, INSTR(m.nombre_modulo, ' ') + 1) AS INTEGER)
                            ELSE m.nombre_modulo COLLATE NOACCENTS
                        END {direction}
                    """)
        else:
            # Fallback a ordenación por ID si el sort_by no es válido
            order_by_parts.append("u.id ASC")

        final_order_by_clause = f"ORDER BY {', '.join(order_by_parts)}"

        if clean_search_query_lower:
            try:
                user_id_search = int(clean_search_query_lower)
                where_clauses_for_filtering.append("u.id = ?")
                params_for_where_clause.append(user_id_search)

                relevance_score_select_clause = "100 AS relevance_score"
                # Cuando se busca por ID numérico, la ordenación por relevancia es prioritaria
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

                # Si hay búsqueda por texto, la relevancia es prioritaria, luego la ordenación elegida
                final_order_by_clause = f"ORDER BY relevance_score DESC, {', '.join(order_by_parts)}"

        base_sql_from_join = '''
            FROM usuarios AS u
            LEFT JOIN modulos AS m ON u.id_modulo = m.id
        '''

        sql_where_clause_string = ""
        if where_clauses_for_filtering:
            sql_where_clause_string = " WHERE " + " AND ".join(where_clauses_for_filtering)

        count_query = f"SELECT COUNT(*) {base_sql_from_join} {sql_where_clause_string}"
        total_results = cursor.execute(count_query, params_for_where_clause).fetchone()[0]
        total_pages = math.ceil(total_results / PER_PAGE_USERS) if total_results > 0 else 1
        page = max(1, min(page, max(1, total_pages)))
        offset = (page - 1) * PER_PAGE_USERS

        main_sql_select_fields = f'''
            u.id, u.apellidos, u.nombre, u.genero, u.observaciones,
            m.nombre_modulo,
            (SELECT COUNT(*) FROM prestamos WHERE id_usuario = u.id AND fecha_devolucion_real IS NULL) AS prestamos_activos,
            {relevance_score_select_clause}
        '''

        sql_query = f"SELECT {main_sql_select_fields} {base_sql_from_join} {sql_where_clause_string} {final_order_by_clause} LIMIT ? OFFSET ?"
        final_params = params_for_sql_select + params_for_where_clause + [PER_PAGE_USERS, offset]

        users_result = cursor.execute(sql_query, final_params).fetchall()

        return {
            'usuarios': [dict(row) for row in users_result],
            'q': search_query,
            'page': page,
            'per_page': PER_PAGE_USERS,
            'total_pages': total_pages,
            'total_results': total_results,
            'sort_by': sort_by,
            'sort_direction': sort_direction,
            'base_ajax_url': 'users.listar_usuarios_ajax'
        }

    def get_user_details(self, user_id: int) -> Optional[Dict[str, Any]]:
        conn = self.get_db()
        usuario = conn.execute('''
            SELECT
                u.id, u.nombre, u.apellidos,
                m.nombre_modulo,
                u.genero,
                u.observaciones,
                (SELECT COUNT(*) FROM prestamos WHERE id_usuario = u.id AND fecha_devolucion_real IS NULL) AS prestamos_activos
            FROM usuarios AS u
            LEFT JOIN modulos AS m ON u.id_modulo = m.id
            WHERE u.id = ?
        ''', (user_id,)).fetchone()
        if usuario:
            usuario_dict = dict(usuario)
            if 'observaciones' in usuario_dict:
                obs_value = usuario_dict['observaciones']
                if obs_value == 'None' or obs_value is None or (isinstance(obs_value, str) and obs_value.strip() == ''):
                    usuario_dict['observaciones'] = None
            return usuario_dict
        return None

    def get_user_loans(self, user_id: int) -> List[Dict[str, Any]]:
        conn = self.get_db()
        prestamos = conn.execute('''
            SELECT
                p.id,
                l.titulo || ' (' || a.nombre_autor || ')' AS libro_info,
                p.fecha_prestamo,
                p.fecha_devolucion_estimada,
                p.fecha_devolucion_real,
                p.estado_prestamo
            FROM prestamos p
            JOIN libros l ON p.id_libro = l.id
            JOIN autores a ON l.id_autor_principal = a.id
            WHERE p.id_usuario = ?
            ORDER BY p.fecha_prestamo DESC
        ''', (user_id,)).fetchall()
        return [dict(row) for row in prestamos]

    def get_user_for_edit(self, user_id: int) -> Optional[Dict[str, Any]]:
        conn = self.get_db()
        user_data = conn.execute('''
            SELECT
                u.id,
                u.nombre,
                u.apellidos,
                u.id_modulo,
                m.nombre_modulo,
                u.genero,
                u.observaciones
            FROM usuarios AS u
            LEFT JOIN modulos AS m ON u.id_modulo = m.id
            WHERE u.id = ?
        ''', (user_id,)).fetchone()
        if user_data:
            return dict(user_data)
        return None

    def get_modulos(self) -> List[Dict[str, Any]]:
        conn = self.get_db()
        return [dict(row) for row in conn.execute(f"""
                    SELECT id, nombre_modulo FROM modulos
                    ORDER BY
                        CASE
                            WHEN nombre_modulo LIKE 'modulo %' THEN 0
                            ELSE 1
                        END,
                        CASE
                            WHEN nombre_modulo LIKE 'modulo %' THEN CAST(SUBSTR(nombre_modulo, INSTR(nombre_modulo, ' ') + 1) AS INTEGER)
                            ELSE nombre_modulo COLLATE NOACCENTS
                        END ASC
                """).fetchall()]

    def get_existing_generos(self) -> List[Dict[str, Any]]:
        conn = self.get_db()
        return [dict(row) for row in conn.execute('SELECT DISTINCT genero FROM usuarios WHERE genero IS NOT NULL ORDER BY genero').fetchall()]

    def add_user(self, form_data: Dict[str, Any]) -> Optional[str]:
        conn = self.get_db()
        try:
            user_id_input = form_data.get('user_id', '').strip()
            apellidos = form_data.get('apellidos', '').strip().upper()
            nombre = form_data.get('nombre', '').strip().upper()
            id_modulo_input = form_data.get('id_modulo', '').strip()
            genero_input = form_data.get('genero', '').strip().upper()
            observaciones = form_data.get('observaciones', '').strip()

            errors = []
            if not apellidos: errors.append('Los apellidos son obligatorios.')
            if not nombre: errors.append('El nombre es obligatorio.')
            if not genero_input: errors.append('El género es obligatorio.')
            if not id_modulo_input: errors.append('El módulo es obligatorio.')

            user_id: Optional[int] = None
            if user_id_input:
                try:
                    user_id = int(user_id_input)
                    if user_id <= 0:
                        errors.append('El ID de usuario debe ser un número entero positivo.')
                except ValueError:
                    errors.append('El ID de usuario debe ser un número entero válido.')

                if not errors and user_id is not None:
                    existing_user = conn.execute("SELECT id FROM usuarios WHERE id = ?", (user_id,)).fetchone()
                    if existing_user:
                        errors.append(f'El ID de usuario {user_id} ya existe. Por favor, elija otro.')

            if errors: return "\n".join(errors)

            id_modulo = self._get_or_create_modulo_id(conn, id_modulo_input)
            if id_modulo is None:
                return f'Error: No se pudo determinar el módulo "{id_modulo_input}". Por favor, inténtelo de nuevo.'

            prestamos_activos_initial = 0 # Valor por defecto 0 como en el original

            if user_id is not None:
                conn.execute(
                    'INSERT INTO usuarios (id, apellidos, nombre, id_modulo, genero, observaciones, prestamos_activos) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (user_id, apellidos, nombre, id_modulo, genero_input, observaciones, prestamos_activos_initial)
                )
            else:
                conn.execute(
                    'INSERT INTO usuarios (apellidos, nombre, id_modulo, genero, observaciones, prestamos_activos) VALUES (?, ?, ?, ?, ?, ?)',
                    (apellidos, nombre, id_modulo, genero_input, observaciones, prestamos_activos_initial)
                )
            conn.commit()
            return None
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return f'Ocurrió un error de integridad de base de datos: {e}'
        except sqlite3.Error as e:
            conn.rollback()
            return f'Ocurrió un error de base de datos al añadir el usuario: {e}'
        except Exception as e:
            conn.rollback()
            return f'Ocurrió un error inesperado al añadir el usuario: {e}'

    def update_user(self, user_id: int, form_data: Dict[str, Any]) -> Optional[str]:
        conn = self.get_db()
        try:
            cursor = conn.cursor()
            # Obtener el ID del módulo actual del usuario antes de la actualización
            cursor.execute("SELECT id_modulo FROM usuarios WHERE id = ?", (user_id,))
            user_current_info = cursor.fetchone()
            old_modulo_id = user_current_info['id_modulo'] if user_current_info else None
            apellidos = form_data['apellidos'].strip().upper()
            nombre = form_data['nombre'].strip().upper()
            modulo_input = form_data['modulo'].strip().upper()
            genero_input = form_data['genero'].strip().upper()
            observaciones = form_data.get('observaciones', '').strip()

            errors = []
            if not apellidos: errors.append('Los apellidos son obligatorios.')
            if not nombre: errors.append('El nombre es obligatorio.')
            if not modulo_input: errors.append('El módulo es obligatorio.')
            if not genero_input: errors.append('El género es obligatorio.')
            elif genero_input not in ['HOMBRE', 'MUJER', 'OTRO']:
                errors.append('El género debe ser "Hombre", "Mujer" u "Otro".')

            if errors: return "\n".join(errors)

            id_modulo = self._get_or_create_modulo_id(conn, modulo_input)
            if id_modulo is None:
                return f'Error: No se pudo determinar el módulo "{modulo_input}". Por favor, inténtelo de nuevo.'

            conn.execute('''
                UPDATE usuarios SET
                    apellidos = ?,
                    nombre = ?,
                    id_modulo = ?,
                    genero = ?,
                    observaciones = ?
                WHERE id = ?
            ''', (apellidos, nombre, id_modulo, genero_input, observaciones, user_id))
            conn.commit()
            # Limpieza de Módulo
            if old_modulo_id is not None and old_modulo_id != id_modulo:
                self.eliminar_modulo_si_huerfano(old_modulo_id)
            return None

        except sqlite3.IntegrityError as e:
            conn.rollback()
            print(f"ERROR: [update_user] Error de integridad al actualizar usuario ID {user_id}: {e}")
            return f'Ocurrió un error de integridad de base de datos: {e}'
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR: [update_user] Error de base de datos al actualizar el usuario ID {user_id}: {e}")
            return f'Ocurrió un error de base de datos al actualizar el usuario: {e}'
        except Exception as e:
            conn.rollback()
            print(f"ERROR: [update_user] Error inesperado al actualizar usuario ID {user_id}: {e}")
            return f'Ocurrió un error inesperado al actualizar el usuario: {e}'

    def delete_user(self, user_id: int) -> Optional[str]:
        conn = self.get_db()
        user_info = conn.execute('SELECT nombre, apellidos, id_modulo FROM usuarios WHERE id = ?', (user_id,)).fetchone()
        if user_info is None:
            print(f"ERROR: [delete_user] Intento de eliminar usuario ID {user_id}, pero no se encontró.")
            return "Usuario no encontrado."
        try:
            modulo_id_to_check = user_info['id_modulo'] if user_info['id_modulo'] is not None else None
            user_name = f"{user_info['nombre']} {user_info['apellidos']}"
            active_loans_count = conn.execute(
                'SELECT COUNT(*) FROM prestamos WHERE id_usuario = ? AND fecha_devolucion_real IS NULL',
                (user_id,)
            ).fetchone()[0]

            if active_loans_count > 0:
                return f'No se puede eliminar a {user_info["nombre"]} {user_info["apellidos"]} porque tiene {active_loans_count} préstamos activos.'

            conn.execute(
                'DELETE FROM prestamos WHERE id_usuario = ? AND fecha_devolucion_real IS NOT NULL',(user_id,)
            )

            conn.execute('DELETE FROM usuarios WHERE id = ?', (user_id,))
            conn.commit()
            print(f"DEBUG: [delete_user] Usuario ID {user_id} ('{user_name}') ELIMINADO correctamente.")
            # Limpieza de Módulo
            if modulo_id_to_check is not None:
                self.eliminar_modulo_si_huerfano(modulo_id_to_check)

            return None
        except sqlite3.IntegrityError as e:
            conn.rollback()
            print(f"ERROR: [delete_user] Error de integridad al eliminar usuario ID {user_id}: {e}")
            return f'Ocurrió un error de integridad de base de datos al eliminar el usuario: {e}. Asegúrate de que no hay préstamos asociados (incluidos los históricos).'
        except sqlite3.Error as e:
            conn.rollback()
            print(f"ERROR: [delete_user] Error de base de datos al eliminar el usuario ID {user_id}: {e}")
            return f'Ocurrió un error de base de datos al eliminar el usuario: {e}'
        except Exception as e:
            conn.rollback()
            print(f"ERROR: [delete_user] Error inesperado al eliminar usuario ID {user_id}: {e}")
            return f'Ocurrió un error inesperado al eliminar el usuario: {e}'

    def autocomplete_users_name(self, term: str) -> List[str]:
        conn = self.get_db()
        if not term: return []
        search_term = '%' + remove_accents(term).upper() + '%'
        users = conn.execute(
            "SELECT nombre, apellidos FROM usuarios WHERE remove_accents(nombre) LIKE ? OR remove_accents(apellidos) LIKE ? ORDER BY nombre, apellidos LIMIT 10",
            (search_term, search_term)
        ).fetchall()
        return [f"{row['nombre']} {row['apellidos']}" for row in users]

    def autocomplete_modulos(self, term: str) -> List[str]:
        conn = self.get_db()
        if not term: return []
        search_term = '%' + remove_accents(term).upper() + '%'
        return [row['nombre_modulo'] for row in conn.execute(f"""
                    SELECT nombre_modulo FROM modulos WHERE remove_accents(nombre_modulo) LIKE ?
                    ORDER BY
                        CASE
                            WHEN nombre_modulo LIKE 'modulo %' THEN 0
                            ELSE 1
                        END,
                        CASE
                            WHEN nombre_modulo LIKE 'modulo %' THEN CAST(SUBSTR(nombre_modulo, INSTR(nombre_modulo, ' ') + 1) AS INTEGER)
                            ELSE nombre_modulo COLLATE NOACCENTS
                        END ASC
                    LIMIT 10
                """, (search_term,)).fetchall()]