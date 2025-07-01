import os
import sys
import logging
import threading
import time
import webbrowser

from dotenv import load_dotenv
from waitress import serve

# --- Configuración global del servidor ---
GLOBAL_HOST = '0.0.0.0'
GLOBAL_PORT = 5000
SERVER_URL = f"http://127.0.0.1:{GLOBAL_PORT}"

# --- Configuración de Logging ---
# Determina la ruta del archivo de log.
log_file_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
log_file_path = os.path.join(log_file_dir, 'app_log.txt')

# Configura el sistema de logging para escribir en el archivo.
logging.basicConfig(filename=log_file_path, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("Iniciando run_server.py para la aplicación TalegoTK.")

# --- GANCHO GLOBAL PARA ERRORES NO CAPTURADOS ---
def handle_unhandled_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("¡Excepción no manejada detectada!", exc_info=(exc_type, exc_value, exc_traceback))
    if getattr(sys, 'frozen', False):
        import time
        time.sleep(5)

sys.excepthook = handle_unhandled_exception
logging.info("Gancho de excepciones no manejadas configurado.")

# --- Definición de la función para iniciar Waitress ---
def run_waitress_server(host_param, port_param, application_instance):
    logging.info(f"Intentando iniciar el servidor Waitress en http://{host_param}:{port_param}")
    serve(application_instance, host=host_param, port=port_param)
    logging.info("Servidor Waitress iniciado exitosamente.")

# --- Bloque principal de ejecución ---
if __name__ == '__main__':
    try:
        # --- Carga de Variables de Entorno (.env) ---
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # noinspection PyProtectedMember
            dotenv_path = os.path.join(sys._MEIPASS, '.env')
            logging.info(f"Modo PyInstaller detectado. Intentando cargar .env desde: {dotenv_path}")
        else:
            dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
            logging.info(f"Modo de desarrollo detectado. Intentando cargar .env desde: {dotenv_path}")

        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path=dotenv_path)
            logging.info(f"Archivo .env cargado exitosamente desde: {dotenv_path}")
        else:
            logging.warning(f"Archivo .env NO ENCONTRADO en: {dotenv_path}. La aplicación puede no funcionar correctamente sin las variables de entorno.")

        # --- Importación de la Aplicación Flask ---
        from app import app as application

        # --- Configuración Adicional de Logging para Werkzeug ---
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.INFO)
        werkzeug_logger.addHandler(logging.StreamHandler(sys.stdout))
        werkzeug_logger.addHandler(logging.FileHandler(log_file_path))

        # --- Lógica Condicional para Desarrollo vs. Producción ---
        if getattr(sys, 'frozen', False):
            # --- MODO PYINSTALLER (PRODUCCIÓN) ---
            # Inicia el servidor en un hilo separado para que el hilo principal pueda abrir el navegador.
            server_thread = threading.Thread(target=run_waitress_server, args=(GLOBAL_HOST, GLOBAL_PORT, application))
            server_thread.daemon = True
            server_thread.start()

            # Da un pequeño tiempo al servidor para que se inicialice.
            time.sleep(1)

            # Abre la URL del servidor en el navegador web predeterminado del sistema.
            logging.info(f"Abriendo el navegador en {SERVER_URL} (desde ejecutable).")
            webbrowser.open(SERVER_URL)

            # Mantén el hilo principal vivo para que el servidor siga ejecutándose.
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logging.info("\nServidor detenido por el usuario (Ctrl+C).")
            except Exception as e:
                logging.error(f"\nSe produjo un error inesperado en el hilo principal del ejecutable: {e}", exc_info=True)

        else:
            # --- MODO DESARROLLO (PYCHARM/TERMINAL) ---
            # La lógica para desarrollo es la misma que antes.
            server_thread = threading.Thread(target=run_waitress_server, args=(GLOBAL_HOST, GLOBAL_PORT, application))
            server_thread.daemon = True
            server_thread.start()

            time.sleep(1)

            logging.info(f"Abriendo el navegador en {SERVER_URL} (desde desarrollo).")
            webbrowser.open(SERVER_URL)

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logging.info("\nServidor detenido por el usuario (Ctrl+C).")
            except Exception as e:
                logging.error(f"\nSe produjo un error inesperado en el hilo principal: {e}", exc_info=True)

    except Exception as e:
        logging.critical(f"¡Error CRÍTICO al iniciar la aplicación! Detalles: {e}", exc_info=True)
        import time
        time.sleep(5)
        sys.exit(1)
