# talegoTK_flask/database.py
import sqlite3
from flask import g
import unicodedata
import os

DATABASE_NAME = 'biblioteca.db'
DATABASE_PATH = os.path.join(os.path.dirname(__file__), DATABASE_NAME)

def remove_accents(input_str):
    if not isinstance(input_str, str):
        return input_str
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def get_db():
    if 'db' not in g:
        conn = sqlite3.connect(
            DATABASE_NAME,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        conn.create_function("remove_accents", 1, remove_accents)
        g.db = conn
    return g.db

def close_db(_e=None):
    db = g.pop('db', None) # Obtiene la conexión de 'g' y la elimina
    if db is not None:
        db.close()

def inicializar_db():
    conn = get_db()
    cursor = conn.cursor()

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

    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS autores (
                        id INTEGER PRIMARY KEY,
                        nombre_autor TEXT NOT NULL UNIQUE
                    );
                       ''')

    # --- Tabla de MODULOS
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS modulos (
            id INTEGER PRIMARY KEY,
            nombre_modulo TEXT NOT NULL UNIQUE
        );
           ''')

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
    print("Base de datos y tablas inicializadas (o ya existentes).")


