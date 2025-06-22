import io
import pandas as pd
from flask import Blueprint, send_file, current_app, render_template, g, request, jsonify
import sqlite3
import os
import calendar
from datetime import datetime
from database import get_db as get_db_connection_from_db_file
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from database import DATABASE_NAME
from pandas import errors as pd_errors

# Crea una instancia del Blueprint.
export_bp = Blueprint(
    'export',
    __name__,
    template_folder='templates'
)

@export_bp.before_app_request
def _before_app_request():
    if 'db' not in g or g.db is None:
        g.db = get_db_connection_from_db_file()

@export_bp.teardown_app_request
def _teardown_app_request(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()
        if exception:
            current_app.logger.error(
                "ERROR: La conexión a la base de datos se cerró después de una excepción en la solicitud.",
                exc_info=True
            )

@export_bp.route('/')
def export_options():
    return render_template('export_options.html')


@export_bp.route('/exportar-todo-xlsx')
def exportar_todo_xlsx():
    try:
        db_connection = g.get('db', None)
        if db_connection is None:
            current_app.logger.error(
                "Error (exportar_todo_xlsx): La conexión a la base de datos (g.db) es None. Asegúrate de que el decorador '@export_bp.before_app_request' está correctamente definido y funcionando en este Blueprint.")
            return "Error interno del servidor: La conexión a la base de datos no está disponible. Por favor, contacta al administrador.", 500

        if not isinstance(db_connection, sqlite3.Connection):
            current_app.logger.error(
                f"Error (exportar_todo_xlsx): g.db no es una conexión SQLite válida. Tipo de objeto: {type(db_connection)}. Asegúrate de que la función get_db_connection_from_db_file() en database.py devuelve un objeto sqlite3.Connection.")
            return "Error interno del servidor: Objeto de conexión a la base de datos inválido. (Tipo incorrecto)", 500

        cursor = db_connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]

        # Si no se encuentran tablas, se devuelve un mensaje informativo.
        if not table_names:
            current_app.logger.warning("Advertencia: No se encontraron tablas en la base de datos para exportar.")
            return "No hay tablas para exportar en la base de datos.", 200

        # Inicializamos el buffer de bytes y el escritor de Excel SÓLO si hay tablas para exportar.
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:  # type: ignore[call-overload]
            for table_name in table_names:
                try:
                    # Leer todos los datos de la tabla actual en un DataFrame de pandas
                    df = pd.read_sql_query(f"SELECT * FROM {table_name}", db_connection)

                    # Si el DataFrame está vacío, se omite la creación de la hoja para esa tabla.
                    if df.empty:
                        continue

                    # Exportar el DataFrame a una hoja de Excel, sin el índice de pandas
                    df.to_excel(writer, index=False, sheet_name=table_name)
                    current_app.logger.debug(f"DEBUG: Tabla '{table_name}' exportada a Excel.")

                    # Obtener el objeto worksheet de xlsxwriter para aplicar formato de tabla
                    worksheet = writer.sheets[table_name]
                    max_row, max_col = df.shape
                    worksheet.add_table(0, 0, max_row, max_col - 1, {'columns': [{'header': col} for col in df.columns]})
                    current_app.logger.debug(f"DEBUG: Formato de tabla aplicado a la hoja '{table_name}'.")

                except Exception as table_e:
                    current_app.logger.error(f"Error al leer la tabla '{table_name}' o aplicar formato de tabla: {table_e}",
                                             exc_info=True)
                    pass

        output.seek(0)

        # Devolvemos el archivo Excel al navegador para su descarga.
        return send_file(output,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True,
                         download_name='biblioteca_completa.xlsx') # Nombre del archivo para descargar

    except Exception as e:
        # Captura cualquier error inesperado y general que ocurra durante el proceso de exportación.
        current_app.logger.error(f"Error inesperado y general al exportar toda la base de datos a Excel: {e}",
                                 exc_info=True)
        return "Error al exportar la base de datos completa. Por favor, inténtelo de nuevo más tarde o contacte al soporte técnico.", 500


@export_bp.route('/copia-seguridad')
def copia_seguridad_options():
    return render_template('copia_seguridad_options.html')


@export_bp.route('/exportar-pdf', methods=['GET'])
def exportar_pdf_options():
    try:
        db_connection = g.get('db', None)
        if db_connection is None:
            current_app.logger.error("exportar_pdf_options: Conexión a la base de datos es None.")
            return "Error interno del servidor: Conexión a la base de datos no disponible.", 500

        cursor = db_connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        all_tables = cursor.fetchall()
        all_table_names = [table[0] for table in all_tables]
        allowed_tables = ["usuarios", "libros", "prestamos", "CDU", "editoriales", "idiomas", "autores", "modulos"]
        table_names = [name for name in all_table_names if name in allowed_tables]

        return render_template('exportar_pdf_options.html', table_names=table_names)
    except Exception as e:
        current_app.logger.error(f"Error al obtener nombres de tablas para exportar PDF: {e}", exc_info=True)
        return "Error al cargar opciones de exportación a PDF.", 500


@export_bp.route('/get-columns/<string:table_name>', methods=['GET'])
def get_columns(table_name):
    try:
        db_connection = g.get('db', None)
        if db_connection is None:
            current_app.logger.error("get_columns: Conexión a la base de datos es None.")
            return jsonify({"error": "Conexión a la base de datos no disponible."}), 500

        cursor = db_connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        if not cursor.fetchone():
            current_app.logger.warning(f"Intento de obtener columnas para tabla no existente: {table_name}")
            return jsonify({"error": "Tabla no encontrada."}), 404

        cursor.execute(f"PRAGMA table_info({table_name});")
        columns_info = cursor.fetchall()
        column_names = [col[1] for col in columns_info]

        return jsonify(column_names)
    except Exception as e:
        current_app.logger.error(f"Error al obtener columnas para la tabla '{table_name}': {e}", exc_info=True)
        return jsonify({"error": "Error al obtener columnas."}), 500


@export_bp.route('/exportar-pdf', methods=['POST'])
def generar_pdf():
    """
    Genera un archivo PDF con los datos de la tabla y columnas seleccionadas.
    Realiza mapeos de IDs a nombres legibles para algunas columnas clave.
    """
    try:
        selected_table = request.form.get('selected_table')
        selected_columns = request.form.getlist('selected_columns')

        if not selected_table:
            return "No se ha seleccionado ninguna tabla.", 400
        if not selected_columns:
            return "No se han seleccionado campos para exportar.", 400

        db_connection = g.get('db', None)
        if db_connection is None:
            current_app.logger.error("generar_pdf: Conexión a la base de datos es None.")
            return "Error interno del servidor: Conexión a la base de datos no disponible.", 500

        cursor = db_connection.cursor()

        # Verifica que la tabla seleccionada sea válida.
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (selected_table,))
        if not cursor.fetchone():
            return "Tabla seleccionada no válida.", 400

        # Verifica que todas las columnas seleccionadas existan en la tabla.
        cursor.execute(f"PRAGMA table_info({selected_table});")
        available_columns = [col[1] for col in cursor.fetchall()]
        for col in selected_columns:
            if col not in available_columns:
                return f"Columna '{col}' no válida para la tabla '{selected_table}'.", 400

        # Construye y ejecuta la consulta SQL para obtener los datos.
        columns_str = ", ".join([f'"{col}"' for col in selected_columns])
        query = f"SELECT {columns_str} FROM {selected_table};"

        df = pd.read_sql_query(query, db_connection)

        if df.empty:
            return "No hay datos para exportar en la tabla seleccionada con los campos elegidos.", 200

        # Define las configuraciones de lookup para traducir IDs a nombres legibles.
        lookup_configs = {
            'libros': {
                'id_cdu': ('CDU', 'materia', 'Clasificación CDU'),
                'id_autor_principal': ('autores', 'nombre_autor', 'Autor Principal'),
                'id_segundo_autor': ('autores', 'nombre_autor', 'Segundo Autor'),
                'id_editorial': ('editoriales', 'nombre_editorial', 'Editorial'),
                'id_idioma': ('idiomas', 'nombre_idioma', 'Idioma'),
            },
            'usuarios': {
                'id_modulo': ('modulos', 'nombre_modulo', 'Módulo'),
            },
            'prestamos': {
                'id_libro': ('libros', 'titulo', 'Título del Libro'),
            }
        }

        final_columns_to_display = list(selected_columns)

        # Aplica los lookups para transformar IDs en nombres.
        if selected_table in lookup_configs:
            current_table_lookups = lookup_configs[selected_table]
            for i, col in enumerate(selected_columns):
                # Lógica especial para el nombre completo de usuario en la tabla de préstamos.
                if selected_table == 'prestamos' and col == 'id_usuario':
                    display_name = 'Usuario (Nombre Completo)'
                    try:
                        lookup_df = pd.read_sql_query(f"SELECT id, nombre, apellidos FROM usuarios;", db_connection)
                        id_to_full_name_map = {}
                        for idx, row in lookup_df.iterrows():
                            full_name = f"{row['apellidos'] or ''}, {row['nombre'] or ''}".strip(', ').strip()
                            id_to_full_name_map[row['id']] = full_name

                        df[col] = df[col].map(id_to_full_name_map).fillna('')
                        final_columns_to_display[i] = display_name
                    # Captura errores específicos durante el mapeo de nombres de usuario.
                    except (sqlite3.Error, pd_errors.DatabaseError) as lookup_e:
                        current_app.logger.warning(
                            f"Advertencia: Error de base de datos/pandas al mapear nombre completo para el usuario de préstamos: {lookup_e}",
                            exc_info=True)
                        final_columns_to_display[i] = "Usuario (ID Fallido)"
                    except Exception as lookup_e:  # Último recurso
                        current_app.logger.warning(
                            f"Advertencia: Excepción inesperada al mapear nombre completo para el usuario de préstamos: {lookup_e}",
                            exc_info=True)
                        final_columns_to_display[i] = "Usuario (ID Fallido)"
                # Lógica general para otros lookups.
                elif col in current_table_lookups:
                    lookup_table, name_col, display_name = current_table_lookups[col]
                    try:
                        lookup_df = pd.read_sql_query(f"SELECT id, {name_col} FROM {lookup_table};", db_connection)
                        id_to_name_map = dict(zip(lookup_df['id'], lookup_df[name_col]))
                        df[col] = df[col].map(id_to_name_map).fillna('')
                        final_columns_to_display[i] = display_name
                    # Captura errores específicos durante otros mapeos.
                    except (sqlite3.Error, pd_errors.DatabaseError) as lookup_e:
                        current_app.logger.warning(
                            f"Advertencia: Error de base de datos/pandas al mapear la columna '{col}' en la tabla '{selected_table}': {lookup_e}",
                            exc_info=True)
                    except Exception as lookup_e:  # Último recurso
                        current_app.logger.warning(
                            f"Advertencia: Excepción inesperada al mapear la columna '{col}' en la tabla '{selected_table}': {lookup_e}",
                            exc_info=True)

        output_buffer = io.BytesIO()

        # Determina el tamaño de la página del PDF (retrato o apaisado) según el número de columnas.
        page_size = A4
        if len(final_columns_to_display) >= 7:
            page_size = landscape(A4)

        # Configura el documento PDF.
        doc = SimpleDocTemplate(
            output_buffer,
            pagesize=page_size,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=1.0 * inch
        )
        styles = getSampleStyleSheet()
        story = []

        # Añade el título al documento.
        title_text = f"Reporte de Tabla: {selected_table}"
        story.append(Paragraph(title_text, styles['h1']))
        story.append(Spacer(1, 0.2 * inch))

        # ¡CORRECCIÓN! Definir available_width después de que 'doc' y sus márgenes estén establecidos.
        available_width = page_size[0] - doc.leftMargin - doc.rightMargin

        # Prepara los datos para la tabla en el PDF.
        data_for_table = [final_columns_to_display] + df[selected_columns].astype(str).values.tolist()

        # Se obtiene el nombre de la fuente y tamaño, aunque no se usan directamente para el objeto Table,
        # sí se usan en TableStyle.
        font_name = styles['Normal'].fontName if 'Normal' in styles else 'Helvetica'
        font_size = styles['Normal'].fontSize if 'Normal' in styles else 9
        _ = (font_name, font_size)  # Variable dummy para evitar advertencia de variable no usada.

        # Define pesos proporcionales para el ancho de las columnas, permitiendo flexibilidad.
        column_proportional_weights = {
            'default_short': 1,
            'id': 1, 'anio': 1, 'paginas': 1, 'disponible': 1,
            'let_autor': 1.5, 'let_titulo': 1.5,
            'id_cdu': 2.5,
            'titulo': 5,
            'subtitulo': 3,
            'id_autor_principal': 2.5,
            'segundo_autor': 2,
            'tercer_autor': 2,
            'id_editorial': 2.5,
            'id_idioma': 1.5,
            'observaciones': 4,
            'isbn': 2,
            'apellidos': 2, 'nombre': 2, 'genero': 1, 'prestamos_activos': 1,
            'id_modulo': 2,
            'fecha_prestamo': 2, 'fecha_devolucion_estimada': 2, 'fecha_devolucion_real': 2,
            'estado_prestamo': 1.5,
            'id_usuario': 3,
            'id_libro': 3,
        }

        col_widths = []
        total_assigned_weight = 0

        # Calcula el peso total de las columnas seleccionadas.
        for original_col_name in selected_columns:
            weight = column_proportional_weights.get(original_col_name, column_proportional_weights['default_short'])
            total_assigned_weight += weight

        # Calcula el ancho de cada columna basado en su peso proporcional.
        if total_assigned_weight > 0:
            for original_col_name in selected_columns:
                weight = column_proportional_weights.get(original_col_name,
                                                         column_proportional_weights['default_short'])
                width = (weight / total_assigned_weight) * available_width
                col_widths.append(int(max(20, width)))  # Asegura que el ancho sea un entero y tenga un mínimo.
        else:
            # En caso de que no haya pesos definidos o total_assigned_weight sea 0.
            col_widths = [int(available_width / len(selected_columns))] * len(selected_columns)
            col_widths = [int(max(20, w)) for w in col_widths]

        # Crea la tabla con los datos y anchos de columna calculados.
        table = Table(data_for_table, colWidths=col_widths)

        # Aplica estilos a la tabla.
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.2, 0.2, 0.2)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Crucial para el texto largo.
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ]))
        story.append(table)

        # Construye el documento PDF.
        doc.build(story)

        output_buffer.seek(0)  # Vuelve al inicio del buffer.

        # Envía el archivo PDF al cliente.
        return send_file(output_buffer,
                         mimetype='application/pdf',
                         as_attachment=True,
                         download_name=f'{selected_table}_export.pdf')

    # Excepciones específicas para errores de base de datos o de pandas durante la generación.
    except (sqlite3.Error, pd_errors.DatabaseError) as e:
        current_app.logger.error(f"Error de base de datos o Pandas al generar PDF: {e}", exc_info=True)
        return "Error al procesar los datos para el PDF. Por favor, inténtelo de nuevo más tarde o contacte al soporte técnico (DB/Pandas).", 500
    except Exception as e:  # Último recurso para cualquier otro error inesperado (ej. ReportLab, errores de memoria, etc.).
        current_app.logger.error(f"Error inesperado al generar PDF con ReportLab: {e}", exc_info=True)
        return "Error general al generar el PDF. Por favor, inténtelo de nuevo más tarde o contacte al soporte técnico (General).", 500


@export_bp.route('/crear-copia-seguridad', methods=['POST'])
def crear_copia_seguridad():
    try:
        db_original_path = os.path.join(current_app.root_path, DATABASE_NAME)
        db_filename = os.path.basename(db_original_path)
        backup_dir = r"C:\backup\talegoTK-Flask"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)  # Crea el directorio si no existe

        # Generar un nombre de archivo único para la copia de seguridad con marca de tiempo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(db_filename)[0]  # 'biblioteca'
        extension = os.path.splitext(db_filename)[1]  # '.db'
        backup_filename = f"{base_name}_backup_{timestamp}{extension}"
        backup_path = os.path.join(backup_dir, backup_filename)

        # Obtenemos la conexión activa de la base de datos principal
        db_source_connection = g.get('db', None)
        if db_source_connection is None:
            current_app.logger.error(
                "crear_copia_seguridad: Conexión a la base de datos fuente es None. Esto no debería ocurrir con before_app_request en este Blueprint.")
            return "Error interno del servidor: Conexión a la base de datos no disponible. Por favor, inténtelo de nuevo.", 500

        with sqlite3.connect(backup_path) as backup_conn:
            db_source_connection.backup(backup_conn)
        current_app.logger.info(f"INFO: Copia de seguridad creada en: {backup_path} usando sqlite3.backup()")
        backup_files = [
            f for f in os.listdir(backup_dir)
            if f.startswith(base_name) and '_backup_' in f and f.endswith(extension)
        ]
        # Ordenar los archivos por su fecha de modificación, de más antiguo a más reciente
        backup_files.sort(key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)))

        # Eliminar las copias de seguridad más antiguas si hay más de 3
        while len(backup_files) > 3:
            oldest_backup = backup_files.pop(0)  # Elimina el archivo más antiguo de la lista
            os.remove(os.path.join(backup_dir, oldest_backup))  # Borra el archivo físico
            current_app.logger.info(f"INFO: Copia de seguridad antigua eliminada: {oldest_backup}")


    except Exception as e:
        current_app.logger.error(f"Error al crear la copia de seguridad: {e}", exc_info=True)
        return "Error al crear la copia de seguridad. Por favor, inténtelo de nuevo.", 500
    return "Copia de seguridad creada exitosamente y antiguas copias gestionadas.", 200


@export_bp.route('/estadisticas_anuales_trimestrales')
def estadisticas_anuales_trimestrales():
    """
    Ruta para mostrar las estadísticas anuales de préstamos, desglosadas por trimestres
    del año actual, mostrando solo los trimestres ya pasados.
    """
    conn = g.get('db')  # Acceder a la conexión de la base de datos desde el objeto global 'g'
    if conn is None:
        # Esto no debería ocurrir si el before_app_request funciona correctamente,
        # pero es bueno tener una capa de seguridad.
        current_app.logger.error("estadisticas_anuales_trimestrales: La conexión a la base de datos es None.")
        return "Error interno del servidor: La conexión a la base de datos no está disponible.", 500

    # Obtener el año actual para las estadísticas
    current_year = datetime.now().year

    # Obtener las estadísticas trimestrales (solo de los trimestres pasados/actuales)
    quarterly_stats = _obtener_estadisticas_trimestrales(conn, current_year)

    # Obtener el número total de libros en la biblioteca
    total_libros_biblioteca = conn.execute("SELECT COUNT(*) FROM libros").fetchone()[0]

    return render_template(
        'estadisticas_anuales_trimestrales.html',
        year=current_year,
        stats=quarterly_stats,
        total_libros_biblioteca=total_libros_biblioteca
    )

def _obtener_estadisticas_trimestrales(conn, year):
    stats_by_quarter = {}
    current_month = datetime.now().month
    quarter_map = {
        1: {'name': "Enero-Marzo", 'start_month': 1, 'end_month': 3},
        2: {'name': "Abril-Junio", 'start_month': 4, 'end_month': 6},
        3: {'name': "Julio-Septiembre", 'start_month': 7, 'end_month': 9},
        4: {'name': "Octubre-Diciembre", 'start_month': 10, 'end_month': 12}
    }

    for q_num, quarter_info in quarter_map.items():
        # Calcular el mes de inicio y fin para el trimestre actual
        start_month = quarter_info['start_month']
        end_month = quarter_info['end_month']
        quarter_name = quarter_info['name']

        # Solo procesar trimestres que ya han comenzado o terminado
        if current_month < start_month and datetime.now().year == year:
            continue  # Si el mes actual es menor que el inicio del trimestre, no ha llegado

        last_day_of_end_month = calendar.monthrange(year, end_month)[1]
        start_date = datetime(year, start_month, 1).strftime('%Y-%m-%d')
        end_date = datetime(year, end_month, last_day_of_end_month).strftime('%Y-%m-%d')

        # Si el trimestre actual aún no ha terminado, ajusta la fecha de fin al día actual
        if year == datetime.now().year and current_month < end_month:
            end_date = datetime.now().strftime('%Y-%m-%d')


        # 1. Libro más leído (manejo de empates)
        max_libro_count_query = conn.execute("""
            SELECT COUNT(*) as count
            FROM estadisticas
            WHERE fecha_prestamo BETWEEN ? AND ?
            GROUP BY titulo_libro, nombre_autor
            ORDER BY count DESC
            LIMIT 1
        """, (start_date, end_date)).fetchone()

        max_libro_count = max_libro_count_query['count'] if max_libro_count_query else 0

        # Luego, seleccionar todos los libros que tienen esa cuenta máxima
        libros_mas_leidos = []
        if max_libro_count > 0:
            libros_mas_leidos_results = conn.execute(f"""
                SELECT titulo_libro, nombre_autor, COUNT(*) as count
                FROM estadisticas
                WHERE fecha_prestamo BETWEEN ? AND ?
                GROUP BY titulo_libro, nombre_autor
                HAVING count = ?
                ORDER BY titulo_libro ASC, nombre_autor ASC
            """, (start_date, end_date, max_libro_count)).fetchall()

            # Formatear la salida para incluir todos los libros empatados
            libros_mas_leidos = [f"{l['titulo_libro']} (de {l['nombre_autor']})" for l in libros_mas_leidos_results]

        # 2. Perfil del lector
        genero_counts_results = conn.execute("""
            SELECT genero_usuario_historial, COUNT(*) as count
            FROM estadisticas
            WHERE fecha_prestamo BETWEEN ? AND ? AND genero_usuario_historial IS NOT NULL AND genero_usuario_historial != ''
            GROUP BY genero_usuario_historial
            ORDER BY genero_usuario_historial ASC -- Ordenar para una presentación consistente (ej. 'Hombre' antes que 'Mujer')
        """, (start_date, end_date)).fetchall()

        perfil_lector_genero_display = 'N/A'
        if genero_counts_results:
            formatted_genero_stats = []
            for entry in genero_counts_results:
                formatted_genero_stats.append(f"{entry['genero_usuario_historial']}: {entry['count']}")
            perfil_lector_genero_display = "<br>".join(formatted_genero_stats)


        # 3. Autor más leído (manejo de empates)
        max_autor_count_query = conn.execute("""
            SELECT COUNT(*) as count
            FROM estadisticas
            WHERE fecha_prestamo BETWEEN ? AND ? AND nombre_autor IS NOT NULL AND nombre_autor != ''
            GROUP BY nombre_autor
            ORDER BY count DESC
            LIMIT 1
        """, (start_date, end_date)).fetchone()

        max_autor_count = max_autor_count_query['count'] if max_autor_count_query else 0

        autores_mas_leidos = []
        if max_autor_count > 0:
            autores_mas_leidos_results = conn.execute(f"""
                SELECT nombre_autor, COUNT(*) as count
                FROM estadisticas
                WHERE fecha_prestamo BETWEEN ? AND ? AND nombre_autor IS NOT NULL AND nombre_autor != ''
                GROUP BY nombre_autor
                HAVING count = ?
                ORDER BY nombre_autor ASC
            """, (start_date, end_date, max_autor_count)).fetchall()

            autores_mas_leidos = [a['nombre_autor'] for a in autores_mas_leidos_results]

        # 4. Módulo con más préstamos (manejo de empates)
        max_modulo_count_query = conn.execute("""
            SELECT COUNT(*) as count
            FROM estadisticas
            WHERE fecha_prestamo BETWEEN ? AND ? AND modulo_usuario_historial IS NOT NULL AND modulo_usuario_historial != ''
            GROUP BY modulo_usuario_historial
            ORDER BY count DESC
            LIMIT 1
        """, (start_date, end_date)).fetchone()

        max_modulo_count = max_modulo_count_query['count'] if max_modulo_count_query else 0

        modulos_mas_prestamos = []
        if max_modulo_count > 0:
            modulos_mas_prestamos_results = conn.execute(f"""
                SELECT modulo_usuario_historial, COUNT(*) as count
                FROM estadisticas
                WHERE fecha_prestamo BETWEEN ? AND ? AND modulo_usuario_historial IS NOT NULL AND modulo_usuario_historial != ''
                GROUP BY modulo_usuario_historial
                HAVING count = ?
                ORDER BY modulo_usuario_historial ASC
            """, (start_date, end_date, max_modulo_count)).fetchall()

            modulos_mas_prestamos = [m['modulo_usuario_historial'] for m in modulos_mas_prestamos_results]

        # 5. Total de préstamos en el trimestre
        total_prestamos_trimestre = conn.execute("""
            SELECT COUNT(*) FROM estadisticas WHERE fecha_prestamo BETWEEN ? AND ?
        """, (start_date, end_date)).fetchone()[0]

        stats_by_quarter[quarter_name] = {
            'libro_mas_leido': ("<br>".join(libros_mas_leidos)) if libros_mas_leidos else 'N/A',
            'perfil_lector_genero': perfil_lector_genero_display,
            'autor_mas_leido': ("<br>".join(autores_mas_leidos)) if autores_mas_leidos else 'N/A',
            'modulo_mas_prestamos': ("<br>".join(modulos_mas_prestamos)) if modulos_mas_prestamos else 'N/A',
            'total_prestamos_trimestre': total_prestamos_trimestre
        }

    return stats_by_quarter