## Sistema de Gestión de Biblioteca (talegoTK_Flask)
Este proyecto es un sistema web integral diseñado para la gestión eficiente de una biblioteca, desarrollado con Python, Flask y sqlite3. Su propósito va más allá de la mera administración: **actualmente, está siendo utilizado con gran éxito en el centro penitenciario donde trabaja mi pareja, transformando y optimizando la gestión de su biblioteca y acercando la lectura a quienes más lo necesitan.**

**¡Estamos inmensamente orgullosos de ver el impacto positivo que tiene este sistema cada día!** La respuesta del personal y los usuarios ha sido excepcional, y están tan contentos que, en un futuro próximo, subiré una carta de agradecimiento oficial que me harán llegar desde la institución. Este proyecto es un testimonio de cómo la tecnología puede servir a propósitos nobles y hacer una diferencia real.
La utilidad real es que este proyecto no necesita internet, que es un handicup que tienen lugares como una cárcel, entonces pensé que Flask y SQLite eran una buena opción, no es una biblioteca inmensa así que pienso que les puede ir bien.
Aunque en un futuro no muy lejano volveré a subir este proyecto usando MYSQL, mysql-connector y SQLAlquemy.

## 🌟 Características Principales

* Mi proyecto es una joya por todo lo que ofrece:

    * **Gestión Completa de Libros:**

    * Registro intuitivo para añadir, editar y eliminar libros, usuarios y préstamos.

    * Asignación detallada de autores, Clasificación Decimal Universal (CDU), editoriales e idiomas.

    * Indicador de disponibilidad del libro en tiempo real.

    * **Paginación y Búsqueda AJAX**: Navegación fluida y búsquedas instantáneas por ID, título, autor, CDU o materia, sin recargar la página.
    
    * **Filtros de búsqueda** y **ordenación** por distintos campos.

* **Gestión de Usuarios Robusta:**

   * Control total sobre el registro, edición y eliminación de usuarios (socios).

   * Asociación a módulos educativos y categorización por género.

   * **Paginación, Búsqueda AJAX, Filtros y Ordenación:** Listados eficientes y búsquedas rápidas por ID, nombre, apellidos o módulo.
   
   * **Control de Préstamos Activos:** Impide la eliminación de usuarios que aún tienen libros prestados, garantizando la integridad de los datos.

* **Gestión de Préstamos y Devoluciones:**

   * Registro sencillo de cada préstamo y su posterior devolución, con seguimiento de fechas.

   * Historial completo de todas las transacciones de préstamo.

* **Estadísticas Anuales y Trimestrales Avanzadas:**

   * Generación de informes de uso de la biblioteca desglosados por trimestre del año actual.

   * **Manejo Inteligente de Empates**: Identifica y muestra todos los libros, autores y módulos empatados en las posiciones más destacadas (ej. más leídos, con más préstamos), presentándolos de forma clara en líneas separadas.

   * **Perfil del Lector por Género**: muestra el número de libros leídos por cada género.

* **Creación Dinámica de Datos Maestros:**

   * Los módulos, autores, editoriales, categorías CDU e idiomas se crean automáticamente en la base de datos si no existen al añadir un libro o usuario.
   
   * Eficiencia máxima: si un autor/idioma/módulo/editorial ya no existe en las tablas usuarios/libros, se elimina automáticamente de la base de datos.

* **Búsquedas Inteligentes:**

   * Funcionalidades de búsqueda optimizadas, insensibles a mayúsculas/minúsculas y a tildes (acentos), facilitando la localización de información.

* **Copias de Seguridad y Exportación de Datos:**

   * Generación de copias de seguridad de la base de datos completa.

   * Exportación de datos de cualquier tabla a formatos PDF y Excel (XLSX).

   * Restauración automática de copias de seguridad.

* **Interfaz de Usuario Amigable:**

   * Diseño limpio, intuitivo y **responsivo** basado en Bootstrap 5, asegurando una experiencia de usuario óptima en cualquier dispositivo.

   * Mensajes claros para guiar al usuario en cada operación.

   * Paginación en cada pantalla de listados.

## 🛠️ Tecnologías Utilizadas

* **Backend:**

   * [Python 3.13](https://www.python.org/)

   * [Flask](https://flask.palletsprojects.com/) (Microframework web)

   * [SQLite](https://www.sqlite.org/) (Base de datos embebida)

   * [python-dotenv](https://pypi.org/project/python-dotenv/)(Para gestión segura de variables de entorno)

   * [Pandas](https://pandas.pydata.org/) 

   * [xlsxwriter](https://xlsxwriter.readthedocs.io/) (Para la creación de archivos Excel)

   * [ReportLab](https://docs.reportlab.com/) (Para la generación de documentos PDF)

   * [Waitress](https://docs.pylonproject.org/projects/waitress/en/latest/) (Servidor WSGI de producción)

* **Frontend:**

   * [HTML5](https://developer.mozilla.org/es/docs/Web/HTML)

   * [CSS3](https://developer.mozilla.org/es/docs/Web/CSS)

   * [JavaScript](https://developer.mozilla.org/es/docs/Web/JavaScript) (Con peticiones Fetch/AJAX para interactividad)

   * [Bootstrap 5](https://getbootstrap.com/) (Framework CSS para diseño responsivo)

   * [Jinja2](https://jinja.palletsprojects.com/en/stable/) (Motor de plantillas de Flask)



## 🖥️ Uso

* Una vez que la aplicación está funcionando hace estas cosas:

* **Página Principal:** Accede a la interfaz inicial de la biblioteca.

* **Panel de Administración** (`/admin/`): Central para gestionar todas las funcionalidades del sistema (usuarios, libros, préstamos, exportaciones, estadísticas, creación y restauración de copias de seguridad).

* **Gestión de Usuarios** (`/usuarios/`): Añade, edita, elimina y consulta la lista de socios.

* **Gestión de Libros** (`/libros/`): Administra el catálogo completo de la biblioteca.

* **Gestión de Préstamos** (`/prestamos/`): Registra préstamos y devoluciones de libros.

* **Estadísticas** (`/admin/estadisticas_anuales_trimestrales`): Visualiza métricas clave de uso y tendencias de lectura.

* **Opciones de Exportación** (`/admin/export-options`): Genera informes en PDF o exporta todos los datos a Excel.

## 📁 Estructura del Proyecto

Aquí te dejo una visión general de la estructura de carpetas y archivos:

```
tu_proyecto_biblioteca/
├── .venv/                     # Entorno virtual (IGNORADO por Git)
├── app.py                     # Define la aplicación Flask, sus Blueprints y la gestión de contexto de base de datos
├── run_server.py              # Script principal para iniciar la aplicación
├── database.py                # Lógica para la conexión y inicialización de la base de datos
├── .gitignore                 # Reglas para ignorar archivos en Git (¡MUY IMPORTANTE!)
├── requirements.txt           # Lista de dependencias de Python
├── blueprints/
│   ├── books/                 # Módulo para la gestión de libros
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── book_service.py
│   │   └── templates/
│   │       ├── libros_list.html
│   │       ├── _libros_table_rows.html
│   │       ├── _pagination_controls_books.html
│   │       └── ... (otras plantillas de libros)
│   ├── users/                 # Módulo para la gestión de usuarios
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── user_service.py
│   │   └── templates/
│   │       ├── users_list.html
│   │       ├── _usuarios_table_rows.html  # ¡Nuevo!
│   │       ├── _pagination_controls_users.html # ¡Nuevo!
│   │       └── ... (otras plantillas de usuarios)
│   ├── loans/                 # Módulo para la gestión de préstamos
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── loan_service.py
│   │   └── templates/
│   │       └── ... (plantillas de préstamos)
│   └── export/                # Módulo para exportaciones y estadísticas
│       ├── __init__.py
│       ├── routes.py
│       └── templates/
│           ├── export_options.html
│           ├── estadisticas_anuales_trimestrales.html
│           └── ... (otras plantillas de exportación)
├── static/                    # Archivos estáticos (CSS, JS, imágenes)
│   ├── css/
│   ├── boostrap/
│   └──  img/
│   
└── templates/                 # Plantillas HTML globales (base, index)
    ├── base.html
    └── index.html

```

## 📄 Licencia

Este proyecto no está licenciado para uso, copia, distribución ni modificación.
No está permitido el uso comercial ni personal sin autorización expresa.

## 📧 Contacto

Para cualquier pregunta o sugerencia, no dudes en contactar:
[https://github.com/Mai-de-jerez/]  
[mainen1985@gmail.com]

Este proyecto fue generado con el cariño y la ayuda de `GEMINI`, una IA fascinante.
