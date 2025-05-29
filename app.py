# Importar los módulos necesarios
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

# Inicializar la aplicación Flask
app = Flask(__name__)

# Configurar una clave secreta para la gestión de sesiones.
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

# Nombre del archivo de la base de datos SQLite
DATABASE = 'usuarios.db'

# --- Funciones de Base de Datos ---

def get_db_connection():
    """
    Establece una conexión con la base de datos SQLite.
    Configura row_factory para acceder a las columnas por nombre.
    """
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row # Permite acceder a las columnas por nombre
    return conn

def init_db():
    """
    Inicializa la base de datos creando la tabla 'users' si no existe.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT NOT NULL,
            nombre_completo TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    print("Base de datos inicializada y tabla 'users' creada si no existía.")

# --- Rutas de la Aplicación ---

@app.route('/')
def index():
    """
    Renderiza la página de inicio.
    Si el usuario está logueado, recupera sus datos de la BD y los pasa a la plantilla.
    """
    user_info = None
    if 'user_id' in session:
        username = session['user_id']
        conn = get_db_connection()
        user_from_db = conn.execute('SELECT username, email, nombre_completo FROM users WHERE username = ?',
                                    (username,)).fetchone()
        conn.close()
        if user_from_db:
            user_info = dict(user_from_db)
    return render_template('index.html', user_info=user_info)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Maneja el registro de nuevos usuarios.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        nombre_completo = request.form.get('nombre_completo')

        if not username or not password or not email or not nombre_completo:
            flash('Todos los campos son obligatorios para el registro.', 'danger')
            return redirect(url_for('register'))

        conn = get_db_connection()
        cursor = conn.cursor()
        existing_user = cursor.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()

        if existing_user:
            flash('El nombre de usuario ya existe. Por favor, elige otro.', 'warning')
            conn.close()
            return redirect(url_for('register'))

        password_hash = generate_password_hash(password)
        try:
            cursor.execute('''
                INSERT INTO users (username, password_hash, email, nombre_completo)
                VALUES (?, ?, ?, ?)
            ''', (username, password_hash, email, nombre_completo))
            conn.commit()
            flash('¡Registro exitoso! Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('login')) # Redirigir a la página de login tras registro exitoso
        except sqlite3.IntegrityError:
            flash('Error al registrar el usuario.', 'danger')
        finally:
            conn.close()
        return redirect(url_for('register'))

    # Si es un método GET, simplemente mostrar la página de registro
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Maneja el inicio de sesión de usuarios existentes.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Nombre de usuario y contraseña son obligatorios.', 'danger')
            return redirect(url_for('login'))

        conn = get_db_connection()
        cursor = conn.cursor()
        user_data = cursor.execute('SELECT username, password_hash FROM users WHERE username = ?',
                                   (username,)).fetchone()
        conn.close()

        if user_data and check_password_hash(user_data['password_hash'], password):
            session['user_id'] = user_data['username']
            flash(f'¡Bienvenido de nuevo, {user_data["username"]}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Nombre de usuario o contraseña incorrectos.', 'danger')
            return redirect(url_for('login'))

    # Si es un método GET, simplemente mostrar la página de login
    return render_template('login.html')

@app.route('/logout')
def logout():
    """
    Cierra la sesión del usuario actual.
    """
    session.pop('user_id', None)
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('index'))

# --- Punto de entrada y Inicialización de BD ---
if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)