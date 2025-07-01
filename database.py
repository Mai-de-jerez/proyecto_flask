import sqlite3
from flask import g
import unicodedata
import os
import sys
import logging

# --- Configuración de Logging para database.py ---
if not logging.getLogger().handlers:
    log_file_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
    log_file_path = os.path.join(log_file_dir, 'app_log.txt')
    logging.basicConfig(filename=log_file_path, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

# --- DEFINICIÓN DE RUTAS ---
BASE_DE_DATOS_FOLDER = "C:/biblioteca_data"
DATABASE_NAME = 'biblioteca.db'
DATABASE_PATH = os.path.join(BASE_DE_DATOS_FOLDER, DATABASE_NAME)
COPIAS_SEGURIDAD_FOLDER = os.path.join(BASE_DE_DATOS_FOLDER, "copias_seguridad")

logging.info(f"Ruta de la base de datos configurada en: {DATABASE_PATH}")
logging.info(f"Ruta de copias de seguridad configurada en: {COPIAS_SEGURIDAD_FOLDER}")
# --- FIN DE DEFINICIÓN DE RUTAS ---


def remove_accents(input_str):
    if not isinstance(input_str, str):
        return input_str
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def collate_no_accents(string1, string2):
    """
    Función de cotejo personalizada para SQLite que compara cadenas sin acentos.
    """
    str1_normalized = remove_accents(string1).lower()
    str2_normalized = remove_accents(string2).lower()
    if str1_normalized == str2_normalized:
        return 0
    elif str1_normalized < str2_normalized:
        return -1
    else:
        return 1

def get_db():
    if 'db' not in g:
        conn = None # Inicializar conn a None
        try:
            # Creamos la carpeta BASE_DE_DATOS_FOLDER si no existe.
            logging.info(f"Verificando/creando carpeta de base de datos: {BASE_DE_DATOS_FOLDER}")
            if not os.path.exists(BASE_DE_DATOS_FOLDER):
                os.makedirs(BASE_DE_DATOS_FOLDER)
                logging.info(f"Carpeta '{BASE_DE_DATOS_FOLDER}' creada exitosamente.")
            else:
                logging.info(f"Carpeta '{BASE_DE_DATOS_FOLDER}' ya existe.")

            # Comprobamos si el archivo de la base de datos YA EXISTE antes de conectar.
            db_is_new = not os.path.exists(DATABASE_PATH)
            logging.info(f"Verificando existencia de DB en '{DATABASE_PATH}'. ¿Es nueva?: {db_is_new}")

            conn = sqlite3.connect(
                DATABASE_PATH,
                detect_types=sqlite3.PARSE_DECLTYPES
            )
            logging.info(f"Conexión a la base de datos SQLite establecida en: {DATABASE_PATH}")

            conn.execute("PRAGMA foreign_keys = ON;")
            conn.row_factory = sqlite3.Row
            conn.create_function("remove_accents", 1, remove_accents)
            conn.create_collation("NOACCENTS", collate_no_accents)
            g.db = conn

            if db_is_new:
                logging.info("La base de datos es nueva, iniciando proceso de inicialización de tablas.")
                inicializar_db()
            else:
                logging.info("La base de datos ya existe, no es necesario inicializar tablas.")
        except sqlite3.Error as e:
            logging.error(f"Error al conectar o inicializar la base de datos SQLite: {e}", exc_info=True)
            if conn:
                conn.close()
            # Es crucial relanzar la excepción para que Flask la capture y la registre
            raise
        except Exception as e:
            logging.error(f"Error inesperado en get_db: {e}", exc_info=True)
            if conn:
                conn.close()
            raise

    return g.db

def close_db(_e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
        logging.info("Conexión a la base de datos SQLite cerrada.")

def inicializar_db():
    conn = None
    try:
        conn = get_db() # Aquí ya se ha gestionado la conexión y posible creación de carpeta
        if conn is None:
            logging.error("No se pudo obtener conexión a la base de datos para inicializarla en inicializar_db.")
            return

        cursor = conn.cursor()
        logging.info("Iniciando creación/verificación de tablas.")

        # Mis tablas:
        cursor.execute('''
                CREATE TABLE IF NOT EXISTS editoriales (
                    id INTEGER PRIMARY KEY,
                    nombre_editorial TEXT NOT NULL UNIQUE
                );
                   ''')

        cursor.execute('''
                CREATE TABLE IF NOT EXISTS idiomas (
                    id INTEGER PRIMARY KEY,
                    nombre_idioma TEXT NOT NULL UNIQUE
                );
                   ''')

        cursor.execute('''
                    CREATE TABLE IF NOT EXISTS cdu (
                        id INTEGER PRIMARY KEY,
                        codigo_cdu TEXT NOT NULL,
                        materia TEXT NOT NULL UNIQUE
                    );
                       ''')
        logging.info("Tabla 'cdu' verificada/creada.")

        cursor.execute('''
                        CREATE TABLE IF NOT EXISTS autores (
                            id INTEGER PRIMARY KEY,
                            nombre_autor TEXT NOT NULL UNIQUE
                        );
                           ''')
        logging.info("Tabla 'autores' verificada/creada.")

        # --- Tabla de MODULOS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS modulos (
                id INTEGER PRIMARY KEY,
                nombre_modulo TEXT NOT NULL UNIQUE
            );
               ''')
        logging.info("Tabla 'modulos' verificada/creada.")

        # --- Tabla de libros ---
        cursor.execute('''
                CREATE TABLE IF NOT EXISTS libros (
                    id INTEGER PRIMARY KEY,
                    id_cdu INTEGER NOT NULL,
                    let_autor TEXT,
                    let_titulo TEXT,
                    titulo TEXT NOT NULL,
                    subtitulo TEXT,
                    id_autor_principal INTEGER NOT NULL,
                    segundo_autor TEXT,
                    tercer_autor TEXT,
                    anio INTEGER,
                    id_editorial INTEGER,
                    paginas INTEGER,
                    id_idioma INTEGER NOT NULL,
                    observaciones TEXT,
                    isbn TEXT,
                    disponible TEXT DEFAULT 'Si',
                    FOREIGN KEY (id_cdu) REFERENCES cdu(id) ON DELETE RESTRICT,
                    FOREIGN KEY (id_autor_principal) REFERENCES autores(id) ON DELETE RESTRICT,
                    FOREIGN KEY (id_editorial) REFERENCES editoriales(id) ON DELETE RESTRICT,
                    FOREIGN KEY (id_idioma) REFERENCES idiomas(id) ON DELETE RESTRICT
                    )
                ''')
        logging.info("Tabla 'libros' verificada/creada.")

        # Tabla de Usuarios
        cursor.execute('''
                     CREATE TABLE IF NOT EXISTS usuarios (
                         id INTEGER PRIMARY KEY,
                         apellidos TEXT NOT NULL,
                         nombre TEXT NOT NULL,
                         id_modulo INTEGER NOT NULL,
                         genero TEXT NOT NULL,
                         observaciones TEXT,
                         prestamos_activos INTEGER DEFAULT 0,
                         FOREIGN KEY (id_modulo) REFERENCES modulos(id) ON DELETE SET NULL
                     )
                 ''')
        logging.info("Tabla 'usuarios' verificada/creada.")

        # --- Tabla de préstamos ---
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prestamos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_libro INTEGER NOT NULL,
                id_usuario INTEGER NOT NULL,
                fecha_prestamo TEXT NOT NULL,
                fecha_devolucion_estimada TEXT,
                fecha_devolucion_real TEXT,
                estado_prestamo TEXT NOT NULL DEFAULT 'Prestado',
                FOREIGN KEY (id_libro) REFERENCES libros(id) ON DELETE CASCADE,
                FOREIGN KEY (id_usuario) REFERENCES usuarios(id) ON DELETE RESTRICT
            )
        ''')
        logging.info("Tabla 'prestamos' verificada/creada.")

        cursor.execute('''
             CREATE TABLE IF NOT EXISTS estadisticas (
                 id_prestamo INTEGER PRIMARY KEY,
                 titulo_libro TEXT NOT NULL,
                 nombre_autor TEXT NOT NULL,
                 genero_usuario_historial TEXT NOT NULL,
                 modulo_usuario_historial TEXT NOT NULL,
                 fecha_prestamo TEXT NOT NULL,
                 FOREIGN KEY (id_prestamo) REFERENCES prestamos(id) ON DELETE CASCADE
             );
         ''')

        conn.commit()
        logging.info("Todas las tablas de la base de datos han sido verificadas/creadas y los cambios confirmados.")
    except sqlite3.Error as e:
        conn.rollback()
        logging.error(f"Error SQL al inicializar la base de datos: {e}", exc_info=True)
    except Exception as e:
        logging.error(f"Error inesperado al inicializar la base de datos: {e}", exc_info=True)
    finally:
        pass

# Función para ejecutar consultas genéricas
def execute_query(query, params=(), fetch_one=False):
    conn = None # Inicializar conn a None
    try:
        conn = get_db()
        if conn is None:
            logging.error("No se pudo obtener conexión a la base de datos para ejecutar consulta en execute_query.")
            return None

        cursor = conn.cursor()
        cursor.execute(query, params)
        if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
            conn.commit()
            return cursor.lastrowid
        else:
            if fetch_one:
                return cursor.fetchone()
            else:
                return cursor.fetchall()
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Error SQL al ejecutar la consulta: {e}\nQuery: {query}\nParams: {params}", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"Error inesperado al ejecutar la consulta: {e}\nQuery: {query}\nParams: {params}", exc_info=True)
        return None
    finally:
        if conn:
            conn.close()


