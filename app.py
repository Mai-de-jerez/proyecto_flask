from flask import Flask, g, render_template, Blueprint
import os
import logging
from database import inicializar_db, get_db as get_db_connection_from_db_file
from dotenv import load_dotenv

# Cargar variables de entorno al inicio
load_dotenv()
logging.info("Variables de entorno cargadas en app.py.")

# Definición del Blueprint principal
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

# Importar otros Blueprints
from blueprints.users.routes import users_bp
from blueprints.books.routes import books_bp
from blueprints.loans.routes import loans_bp
from blueprints.export.routes import export_bp

# Crear la instancia de la aplicación Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una_clave_de_desarrollo_segura_y_fija_para_emergencias')
app.config['DEBUG'] = False

# --- Gestión de la conexión a la base de datos ---
def get_db():
    if 'db' not in g:
        g.db = get_db_connection_from_db_file()
    return g.db

# Asegurar que la conexión a la DB se cierre automáticamente después de cada petición.
@app.teardown_appcontext
def close_db(_e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# --- Inicialización de la base de datos al iniciar la aplicación ---
with app.app_context():
    try:
        logging.info("Iniciando contexto de aplicación para inicializar la base de datos.")
        inicializar_db()
        logging.info("Base de datos inicializada exitosamente en el contexto de la aplicación.")
    except Exception as e:
        logging.error(f"Error CRÍTICO al inicializar la base de datos al iniciar la aplicación: {e}", exc_info=True)


# Registro de Blueprints
app.register_blueprint(main_bp)
app.register_blueprint(users_bp, url_prefix='/usuarios')
app.register_blueprint(books_bp, url_prefix='/libros')
app.register_blueprint(loans_bp, url_prefix='/prestamos')
app.register_blueprint(export_bp, url_prefix='/admin')

logging.info("Aplicación Flask configurada y Blueprints registrados.")


