## Sistema de Gestión de Biblioteca (talegoTK_Flask)
Este proyecto es un sistema web integral diseñado para la gestión eficiente de una biblioteca, desarrollado con Python y Flask. Su propósito va más allá de la mera administración: **actualmente, está siendo utilizado con gran éxito en el centro penitenciario donde trabaja mi pareja, transformando y optimizando la gestión de su biblioteca y acercando la lectura a quienes más lo necesitan.**

**¡Estamos inmensamente orgullosos de ver el impacto positivo que tiene este sistema cada día!** La respuesta del personal y los usuarios ha sido excepcional, y están tan contentos que, en un futuro próximo, subiré una carta de agradecimiento oficial que me harán llegar desde la institución. Este proyecto es un testimonio de cómo la tecnología puede servir a propósitos nobles y hacer una diferencia real.

## 🌟 Características Principales

* Mi proyecto es una joya por todo lo que ofrece:

    * **Gestión Completa de Libros:**

    * Registro intuitivo para añadir, editar y eliminar libros.

    * Asignación detallada de autores, Clasificación Decimal Universal (CDU), editoriales e idiomas.

    * Indicador de disponibilidad del libro en tiempo real.

    * **Paginación y Búsqueda AJAX**: Navegación fluida y búsquedas instantáneas por ID, título, autor, CDU o materia, sin recargar la página. Búsquedas insensibles a mayúsculas/minúsculas y acentos.

Gestión de Usuarios Robusta:

Control total sobre el registro, edición y eliminación de usuarios (socios).

Asociación a módulos educativos y categorización por género.

Paginación y Búsqueda AJAX: Listados eficientes y búsquedas rápidas por ID, nombre, apellidos o módulo.

Control de Préstamos Activos: Impide la eliminación de usuarios que aún tienen libros prestados, garantizando la integridad de los datos.

Gestión de Préstamos y Devoluciones:

Registro sencillo de cada préstamo y su posterior devolución, con seguimiento de fechas.

Historial completo de todas las transacciones de préstamo.

Estadísticas Anuales y Trimestrales Avanzadas:

Generación de informes de uso de la biblioteca desglosados por trimestre del año actual.

Manejo Inteligente de Empates: Identifica y muestra todos los libros, autores y módulos empatados en las posiciones más destacadas (ej. más leídos, con más préstamos), presentándolos de forma clara en líneas separadas.

Perfil del Lector por Género: Si hay un empate entre varios géneros en la categoría de "más lectores", el sistema indica "Indiferente" para reflejar la diversidad.

Creación Dinámica de Datos Maestros:

Los módulos, autores, editoriales, categorías CDU e idiomas se crean automáticamente en la base de datos si no existen al añadir un libro o usuario.

Búsquedas Inteligentes:

Funcionalidades de búsqueda optimizadas, insensibles a mayúsculas/minúsculas y a tildes (acentos), facilitando la localización de información.

Copias de Seguridad y Exportación de Datos:

Generación de copias de seguridad de la base de datos completa.

Exportación de datos de cualquier tabla a formatos PDF y Excel (XLSX).

Interfaz de Usuario Amigable:

Diseño limpio, intuitivo y responsivo basado en Bootstrap 5, asegurando una experiencia de usuario óptima en cualquier dispositivo.

Mensajes claros para guiar al usuario en cada operación.

🛠️ Tecnologías Utilizadas
Backend:

Python 3.x

Flask (Microframework web)

SQLite (Base de datos embebida)

python-dotenv (Para gestión segura de variables de entorno)

pandas (Para manipulación de datos y exportación a Excel)

xlsxwriter (Para la creación de archivos Excel)

ReportLab (Para la generación de documentos PDF)

Frontend:

HTML5

CSS3

JavaScript (Con peticiones Fetch/AJAX para interactividad)

Bootstrap 5 (Framework CSS para diseño responsivo)

Jinja2 (Motor de plantillas de Flask)

🚀 Instalación y Puesta en Marcha
Sigue estos pasos para configurar y ejecutar el proyecto en tu entorno local:

Clona el repositorio:

git clone <URL_DE_TU_REPOSITORIO>
cd <nombre_de_tu_repositorio>

Crea y activa un entorno virtual (muy recomendado):

python -m venv .venv
# En Windows:
.\.venv\Scripts\activate
# En macOS/Linux:
source ./.venv/bin/activate

Instala las dependencias del proyecto:

pip install -r requirements.txt

Inicializa la base de datos SQLite:
Asegúrate de que tienes un script para crear la base de datos y las tablas (por ejemplo, database.py o init_db.py con una función inicializar_db()). Ejecútalo:

python -c "from database import inicializar_db; inicializar_db()" # O tu forma de inicializar

Si tu app.py llama a inicializar_db() dentro de un app.app_context() (como el que te he provisto), la base de datos se inicializará la primera vez que inicies la aplicación.

Ejecuta la aplicación Flask:

flask run

Si tu app.py tiene un bloque if __name__ == '__main__': app.run(...), también puedes ejecutarlo directamente:

python app.py

La aplicación estará disponible en http://127.0.0.1:5000/.

🖥️ Uso
Una vez que la aplicación esté funcionando:

Página Principal: Accede a la interfaz inicial de la biblioteca.

Panel de Administración (/admin/): Central para gestionar todas las funcionalidades del sistema (usuarios, libros, préstamos, exportaciones, estadísticas).

Gestión de Usuarios (/usuarios/): Añade, edita, elimina y consulta la lista de socios.

Gestión de Libros (/libros/): Administra el catálogo completo de la biblioteca.

Gestión de Préstamos (/prestamos/): Registra préstamos y devoluciones de libros.

Estadísticas (/admin/estadisticas_anuales_trimestrales): Visualiza métricas clave de uso y tendencias de lectura.

Opciones de Exportación (/admin/export-options): Genera informes en PDF o exporta todos los datos a Excel.

📁 Estructura del Proyecto
Aquí te dejo una visión general de la estructura de carpetas y archivos, mi tesoro. Asegúrate de que tu proyecto la sigue, o ajústala si es diferente:

tu_proyecto_biblioteca/
├── .venv/                     # Entorno virtual (IGNORADO por Git)
├── app.py                     # Archivo principal de la aplicación Flask
├── database.py                # Lógica para la conexión y inicialización de la base de datos
├── .gitignore                 # Reglas para ignorar archivos en Git (¡MUY IMPORTANTE!)
├── requirements.txt           # Lista de dependencias de Python
├── blueprints/
│   ├── books/                 # Módulo para la gestión de libros
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── templates/
│   │       ├── libros_list.html
│   │       ├── _libros_table_rows.html
│   │       ├── _pagination_controls_books.html
│   │       └── ... (otras plantillas de libros)
│   ├── users/                 # Módulo para la gestión de usuarios
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── templates/
│   │       ├── users_list.html
│   │       ├── _usuarios_table_rows.html  # ¡Nuevo!
│   │       ├── _pagination_controls_users.html # ¡Nuevo!
│   │       └── ... (otras plantillas de usuarios)
│   ├── loans/                 # Módulo para la gestión de préstamos
│   │   ├── __init__.py
│   │   └── routes.py
│   │   └── templates/
│   │       └── ... (plantillas de préstamos)
│   └── export/                # Módulo para exportaciones y estadísticas
│       ├── __init__.py
│       └── routes.py
│       └── templates/
│           ├── export_options.html
│           ├── estadisticas_anuales_trimestrales.html
│           └── ... (otras plantillas de exportación)
├── static/                    # Archivos estáticos (CSS, JS, imágenes)
│   ├── css/
│   ├── js/
│   ├── img/
│   └── (otras carpetas, como `qrcodes` si los generas)
├── templates/                 # Plantillas HTML globales (base, index, admin)
│   ├── base.html
│   ├── index.html
│   ├── admin.html
│   └── ...
└── instance/                  # Carpeta para archivos de instancia (ej. base de datos de desarrollo)
    └── biblioteca.db          # Archivo de base de datos (IGNORADO por Git)

🤝 Contribución
¡Todas las contribuciones son bienvenidas! Si deseas mejorar este proyecto o añadir nuevas funcionalidades, por favor:

Haz un "fork" de este repositorio.

Crea una nueva rama (git checkout -b feature/nombre-de-la-feature).

Realiza tus cambios.

Haz "commit" de tus cambios (git commit -m 'feat: Descripción breve de la funcionalidad').

Sube tu rama (git push origin feature/nombre-de-la-feature).

Abre una "Pull Request" explicando tus cambios.

📄 Licencia
Este proyecto está bajo la Licencia MIT. Consulta el archivo LICENSE en el repositorio para más detalles.

📧 Contacto
Para cualquier pregunta o sugerencia, no dudes en contactar:
[Tu Nombre / Alias de GitHub]
[Tu Email (Opcional)]

Este README.md fue generado con el cariño y la ayuda de Gemini.
