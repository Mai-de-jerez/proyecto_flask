from flask import Flask, g, render_template, Blueprint
import os
from database import inicializar_db, get_db as get_db_connection_from_db_file
from dotenv import load_dotenv

load_dotenv()


main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

# Importar Blueprints
from blueprints.users.routes import users_bp
from blueprints.books.routes import books_bp
from blueprints.loans.routes import loans_bp
from blueprints.export.routes import export_bp

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'clave_de_desarrollo_fallback_segura_para_probar'
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG') == '1'


# 3. Gestión de la conexión a la base de datos
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

with app.app_context():
    inicializar_db()

# Registro de Blueprints
app.register_blueprint(main_bp)
app.register_blueprint(users_bp, url_prefix='/usuarios')
app.register_blueprint(books_bp, url_prefix='/libros')
app.register_blueprint(loans_bp, url_prefix='/prestamos')
app.register_blueprint(export_bp, url_prefix='/admin')


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
