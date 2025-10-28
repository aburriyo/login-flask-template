# Importar los módulos necesarios
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
import os
from datetime import datetime

# Inicializar la aplicación Flask
app = Flask(__name__)

# Filtro personalizado para formatear fechas
@app.template_filter('date_spanish')
def date_spanish_filter(date):
    """Formatea una fecha en español"""
    if isinstance(date, str):
        try:
            date = datetime.strptime(date, '%Y-%m-%d')
        except:
            return date
    meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 
             'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    return f"{date.day} de {meses[date.month - 1]}"

# Configurar una clave secreta para la gestión de sesiones.
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

# Configuración de la base de datos MySQL
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'perroverde22',
    'database': 'usuarios_tahia_db',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# --- Funciones de Base de Datos ---

def get_db_connection():
    """
    Establece una conexión con la base de datos MySQL.
    Utiliza cursorclass=DictCursor para acceder a las columnas por nombre.
    """
    conn = pymysql.connect(**DB_CONFIG)
    return conn

def init_db():
    """
    Inicializa la base de datos creando la base de datos y las tablas necesarias si no existen.
    """
    # Primero conectar sin especificar la base de datos para crearla si no existe
    conn = pymysql.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        charset=DB_CONFIG['charset']
    )
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
    conn.commit()
    cursor.close()
    conn.close()
    
    # Ahora conectarse a la base de datos específica
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla de usuarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            nombre VARCHAR(255) NOT NULL,
            apellido VARCHAR(255) NOT NULL,
            password_hash VARCHAR(255) NOT NULL
        )
    ''')
    
    # Tabla de películas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INT AUTO_INCREMENT PRIMARY KEY,
            titulo VARCHAR(255) UNIQUE NOT NULL,
            director VARCHAR(255) NOT NULL,
            fecha_estreno DATE NOT NULL,
            sinopsis TEXT NOT NULL,
            user_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Tabla de comentarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            contenido TEXT NOT NULL,
            movie_id INT NOT NULL,
            user_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Base de datos inicializada y tablas creadas si no existían.")


# --- Rutas de la Aplicación ---


@app.route('/')
def index():
    """
    Renderiza la página de inicio.
    Si el usuario está logueado, recupera sus datos de la BD y los pasa a la plantilla.
    """
    user_info = None
    if 'user_id' in session:
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, email, nombre, apellido FROM users WHERE id = %s',
                       (user_id,))
        user_from_db = cursor.fetchone()
        cursor.close()
        conn.close()
        if user_from_db:
            user_info = user_from_db
    return render_template('index.html', user_info=user_info)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Maneja el registro de nuevos usuarios.
    """
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        email = request.form.get('email')

        # Validaciones
        if not nombre or not apellido or not password or not password_confirm or not email:
            flash('Todos los campos son obligatorios para el registro.', 'danger')
            return redirect(url_for('register'))
        
        if len(nombre) < 2 or len(apellido) < 2:
            flash('El nombre y apellido deben tener al menos 2 caracteres.', 'danger')
            return redirect(url_for('register'))
        
        if password != password_confirm:
            flash('Las contraseñas no coinciden.', 'danger')
            return redirect(url_for('register'))
        
        if '@' not in email or '.' not in email.split('@')[1]:
            flash('Por favor ingresa un email válido.', 'danger')
            return redirect(url_for('register'))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE email = %s', (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Este email ya está registrado. Por favor, usa otro.', 'warning')
            cursor.close()
            conn.close()
            return redirect(url_for('register'))

        password_hash = generate_password_hash(password)
        result = 'error'
        try:
            cursor.execute('''
                INSERT INTO users (nombre, apellido, password_hash, email)
                VALUES (%s, %s, %s, %s)
            ''', (nombre, apellido, password_hash, email))
            conn.commit()
            flash('¡Registro exitoso! Ahora puedes iniciar sesión.', 'success')
            result = 'success'
        except pymysql.err.IntegrityError:
            flash('Error al registrar el usuario.', 'danger')
        finally:
            cursor.close()
            conn.close()
        
        if result == 'success':
            return redirect(url_for('login'))
        else:
            return redirect(url_for('register'))

    # Si es un método GET, simplemente mostrar la página de registro
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Maneja el inicio de sesión de usuarios existentes.
    """
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('Email y contraseña son obligatorios.', 'danger')
            return redirect(url_for('login'))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, email, nombre, apellido, password_hash FROM users WHERE email = %s',
                      (email,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()

        if user_data and check_password_hash(user_data['password_hash'], password):
            session['user_id'] = user_data['id']
            session['user_email'] = user_data['email']
            session['user_nombre'] = user_data['nombre']
            flash(f'¡Bienvenido de nuevo, {user_data["nombre"]}!', 'success')
            return redirect(url_for('cine_dashboard'))
        else:
            flash('Email o contraseña incorrectos.', 'danger')
            return redirect(url_for('login'))

    # Si es un método GET, simplemente mostrar la página de login
    return render_template('login.html')

@app.route('/logout')
def logout():
    """
    Cierra la sesión del usuario actual.
    """
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('user_nombre', None)
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('login'))

# --- Rutas de CinePedia ---

@app.route('/cine')
def cine_dashboard():
    """
    Dashboard principal que muestra todas las películas.
    """
    if 'user_id' not in session:
        flash('Debes iniciar sesión para ver las películas.', 'warning')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT m.*, u.nombre as creador_nombre, u.apellido as creador_apellido
        FROM movies m
        JOIN users u ON m.user_id = u.id
        ORDER BY m.created_at DESC
    ''')
    movies = cursor.fetchall()
    cursor.close()
    conn.close()
    
    user_id = session['user_id']
    return render_template('cine/dashboard.html', movies=movies, user_id=user_id)

@app.route('/cine/nueva', methods=['GET', 'POST'])
def nueva_pelicula():
    """
    Crear una nueva película.
    """
    if 'user_id' not in session:
        flash('Debes iniciar sesión para crear películas.', 'warning')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        director = request.form.get('director')
        fecha_estreno = request.form.get('fecha_estreno')
        sinopsis = request.form.get('sinopsis')
        
        # Validaciones
        if not titulo or not director or not fecha_estreno or not sinopsis:
            flash('Todos los campos son obligatorios.', 'danger')
            return render_template('cine/nueva.html', sinopsis=sinopsis)
        
        if len(titulo) < 3 or len(director) < 3 or len(sinopsis) < 3:
            flash('Todos los campos deben tener al menos 3 caracteres.', 'danger')
            return render_template('cine/nueva.html', sinopsis=sinopsis)
        
        user_id = session['user_id']
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar si ya existe una película con el mismo título
        cursor.execute('SELECT id FROM movies WHERE titulo = %s', (titulo,))
        existing_movie = cursor.fetchone()
        
        if existing_movie:
            flash('Ya existe una película con ese nombre.', 'danger')
            cursor.close()
            conn.close()
            return render_template('cine/nueva.html', sinopsis=sinopsis)
        
        try:
            cursor.execute('''
                INSERT INTO movies (titulo, director, fecha_estreno, sinopsis, user_id)
                VALUES (%s, %s, %s, %s, %s)
            ''', (titulo, director, fecha_estreno, sinopsis, user_id))
            conn.commit()
            flash('Película guardada exitosamente.', 'success')
            cursor.close()
            conn.close()
            return redirect(url_for('cine_dashboard'))
        except Exception as e:
            flash('Error al guardar la película.', 'danger')
            cursor.close()
            conn.close()
            return render_template('cine/nueva.html', sinopsis=sinopsis)
    
    return render_template('cine/nueva.html')

@app.route('/cine/<int:movie_id>')
def ver_pelicula(movie_id):
    """
    Ver los detalles de una película específica.
    """
    if 'user_id' not in session:
        flash('Debes iniciar sesión para ver películas.', 'warning')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT m.*, u.nombre as creador_nombre, u.apellido as creador_apellido
        FROM movies m
        JOIN users u ON m.user_id = u.id
        WHERE m.id = %s
    ''', (movie_id,))
    movie = cursor.fetchone()
    
    if not movie:
        cursor.close()
        conn.close()
        flash('Película no encontrada.', 'danger')
        return redirect(url_for('cine_dashboard'))
    
    # Obtener comentarios
    cursor.execute('''
        SELECT c.*, u.nombre as usuario_nombre, u.apellido as usuario_apellido
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.movie_id = %s
        ORDER BY c.created_at DESC
    ''', (movie_id,))
    comments = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('cine/ver.html', movie=movie, comments=comments)

@app.route('/cine/editar/<int:movie_id>', methods=['GET', 'POST'])
def editar_pelicula(movie_id):
    """
    Editar una película existente.
    """
    if 'user_id' not in session:
        flash('Debes iniciar sesión para editar películas.', 'warning')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM movies WHERE id = %s', (movie_id,))
    movie = cursor.fetchone()
    
    if not movie:
        cursor.close()
        conn.close()
        flash('Película no encontrada.', 'danger')
        return redirect(url_for('cine_dashboard'))
    
    if movie['user_id'] != user_id:
        cursor.close()
        conn.close()
        flash('Solo puedes editar tus propias películas.', 'danger')
        return redirect(url_for('cine_dashboard'))
    
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        director = request.form.get('director')
        fecha_estreno = request.form.get('fecha_estreno')
        sinopsis = request.form.get('sinopsis')
        
        # Validaciones
        if not titulo or not director or not fecha_estreno or not sinopsis:
            flash('Todos los campos son obligatorios.', 'danger')
            return render_template('cine/editar.html', movie=movie, sinopsis=sinopsis)
        
        if len(titulo) < 3 or len(director) < 3 or len(sinopsis) < 3:
            flash('Todos los campos deben tener al menos 3 caracteres.', 'danger')
            return render_template('cine/editar.html', movie=movie, sinopsis=sinopsis)
        
        # Verificar si el título es único (pero no contar la película actual)
        cursor.execute('SELECT id FROM movies WHERE titulo = %s AND id != %s', (titulo, movie_id))
        existing_movie = cursor.fetchone()
        
        if existing_movie:
            flash('Ya existe otra película con ese nombre.', 'danger')
            return render_template('cine/editar.html', movie=dict(movie, titulo=titulo, director=director, fecha_estreno=fecha_estreno, sinopsis=sinopsis))
        
        try:
            cursor.execute('''
                UPDATE movies 
                SET titulo = %s, director = %s, fecha_estreno = %s, sinopsis = %s
                WHERE id = %s
            ''', (titulo, director, fecha_estreno, sinopsis, movie_id))
            conn.commit()
            flash('Película actualizada exitosamente.', 'success')
            cursor.close()
            conn.close()
            return redirect(url_for('cine_dashboard'))
        except Exception as e:
            flash('Error al actualizar la película.', 'danger')
            cursor.close()
            conn.close()
            return render_template('cine/editar.html', movie=dict(movie, titulo=titulo, director=director, fecha_estreno=fecha_estreno, sinopsis=sinopsis))
    
    cursor.close()
    conn.close()
    return render_template('cine/editar.html', movie=movie)

@app.route('/cine/borrar/<int:movie_id>')
def borrar_pelicula(movie_id):
    """
    Borrar una película.
    """
    if 'user_id' not in session:
        flash('Debes iniciar sesión para borrar películas.', 'warning')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM movies WHERE id = %s', (movie_id,))
    movie = cursor.fetchone()
    
    if not movie:
        cursor.close()
        conn.close()
        flash('Película no encontrada.', 'danger')
        return redirect(url_for('cine_dashboard'))
    
    if movie['user_id'] != user_id:
        cursor.close()
        conn.close()
        flash('Solo puedes borrar tus propias películas.', 'danger')
        return redirect(url_for('cine_dashboard'))
    
    cursor.execute('DELETE FROM movies WHERE id = %s', (movie_id,))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('Película borrada exitosamente.', 'success')
    return redirect(url_for('cine_dashboard'))

@app.route('/cine/<int:movie_id>/comentar', methods=['POST'])
def comentar_pelicula(movie_id):
    """
    Agregar un comentario a una película.
    """
    if 'user_id' not in session:
        flash('Debes iniciar sesión para comentar.', 'warning')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    contenido = request.form.get('contenido')
    
    if not contenido or len(contenido.strip()) == 0:
        flash('El comentario no puede estar vacío.', 'danger')
        return redirect(url_for('ver_pelicula', movie_id=movie_id))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verificar que la película existe
    cursor.execute('SELECT user_id FROM movies WHERE id = %s', (movie_id,))
    movie = cursor.fetchone()
    
    if not movie:
        cursor.close()
        conn.close()
        flash('Película no encontrada.', 'danger')
        return redirect(url_for('cine_dashboard'))
    
    # BONUS: No permitir que el usuario comente en su propia película
    if movie['user_id'] == user_id:
        cursor.close()
        conn.close()
        flash('No puedes comentar en tu propia película.', 'warning')
        return redirect(url_for('ver_pelicula', movie_id=movie_id))
    
    cursor.execute('''
        INSERT INTO comments (contenido, movie_id, user_id)
        VALUES (%s, %s, %s)
    ''', (contenido, movie_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('Comentario agregado exitosamente.', 'success')
    return redirect(url_for('ver_pelicula', movie_id=movie_id))

@app.route('/cine/comentario/<int:comment_id>/borrar')
def borrar_comentario(comment_id):
    """
    Borrar un comentario.
    """
    if 'user_id' not in session:
        flash('Debes iniciar sesión para borrar comentarios.', 'warning')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM comments WHERE id = %s', (comment_id,))
    comment = cursor.fetchone()
    
    if not comment:
        cursor.close()
        conn.close()
        flash('Comentario no encontrado.', 'danger')
        return redirect(url_for('cine_dashboard'))
    
    if comment['user_id'] != user_id:
        cursor.close()
        conn.close()
        flash('Solo puedes borrar tus propios comentarios.', 'danger')
        return redirect(url_for('ver_pelicula', movie_id=comment['movie_id']))
    
    movie_id = comment['movie_id']
    cursor.execute('DELETE FROM comments WHERE id = %s', (comment_id,))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('Comentario borrado exitosamente.', 'success')
    return redirect(url_for('ver_pelicula', movie_id=movie_id))

# --- Punto de entrada y Inicialización de BD ---
if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, port=4069)
