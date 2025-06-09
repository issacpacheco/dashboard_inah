from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, send_file
from descargar_drive import DriveBackup
from flask_bcrypt import Bcrypt
import MySQLdb

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'

# Configuración de conexión
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'passwd': '',
    'db': 'tren_carga',
    'charset': 'utf8mb4'
}

bcrypt = Bcrypt(app)

# Función para obtener una conexión
def get_db_connection():
    return MySQLdb.connect(**DB_CONFIG)

# Función para agregar cabeceras de no caché
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('panel'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        username = request.form['usuario']
        contrasena = request.form['contrasena']

        cur.execute('SELECT * FROM usuarios WHERE correo = %s', (username,))
        user = cur.fetchone()

        if user and bcrypt.check_password_hash(user[3], contrasena):
            session['username'] = username
            cur.close()
            conn.close()
            return redirect(url_for('panel'))
        else:
            flash('Usuario o contraseña incorrectos')
            cur.close()
            conn.close()
            return redirect(url_for('login'))

    response = make_response(render_template('login.html'))
    return add_no_cache_headers(response)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['usuario']
        contrasena = request.form['contrasena']
        hashed_password = bcrypt.generate_password_hash(contrasena).decode('utf-8')

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute('SELECT * FROM usuarios WHERE correo = %s', (username,))
        existing_user = cur.fetchone()
        if existing_user:
            cur.close()
            conn.close()
            flash('El usuario ya existe. Por favor, elige otro correo.')
            return redirect(url_for('register'))

        try:
            cur.execute('INSERT INTO usuarios (correo, contrasena) VALUES (%s, %s)', (username, hashed_password))
            conn.commit()
            flash('Registro exitoso. Por favor, inicia sesión.')
        except Exception as e:
            flash('Error al registrar el usuario: {}'.format(str(e)))
        finally:
            cur.close()
            conn.close()
        return redirect(url_for('login'))

    response = make_response(render_template('register.html'))
    return add_no_cache_headers(response)

@app.route('/panel')
def panel():
    if 'username' not in session:
        return redirect(url_for('login'))
    response = make_response(render_template('panel.html'))
    return add_no_cache_headers(response)

@app.route('/backup', methods=['GET', 'POST'])
def backup():
    global backup_instance
    zip_file = None

    if request.method == "POST":
        if request.form.get("stop"):
            if backup_instance:
                backup_instance.detener_backup()
                backup_instance = None
                flash("Respaldo detenido exitosamente.")
            else:
                flash("No hay un respaldo en curso.")
            return redirect(url_for('backup'))

        # Obtener datos del formulario
        json_path = request.form.get("json_path")
        folder_id = request.form.get("folder_id")
        download_path = request.form.get("download_path")
        zip_path = request.form.get("zip_path")

        # Validar campos
        if not all([json_path, folder_id, download_path, zip_path]):
            return "❌ Error: Todos los campos son obligatorios."

        # Obtener configuración del usuario
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM usuarios WHERE correo = %s", (session['username'],))
        user = cur.fetchone()

        if not user:
            cur.close()
            conn.close()
            flash("Usuario no encontrado.")
            return redirect(url_for('panel'))

        user_id = user[0]

        cur.execute("SELECT * FROM usuarios_configuracion WHERE id_usuario = %s", (user_id,))
        config = cur.fetchone()

        if not config:
            cur.execute("""
                INSERT INTO usuarios_configuracion (id_usuario, ruta_json, folder_id, ruta_descargar, ruta_zip)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, json_path, folder_id, download_path, zip_path))
        else:
            cur.execute("""
                UPDATE usuarios_configuracion
                SET ruta_json = %s, folder_id = %s, ruta_descargar = %s, ruta_zip = %s
                WHERE id_usuario = %s
            """, (json_path, folder_id, download_path, zip_path, user_id))

        conn.commit()
        cur.close()
        conn.close()

        try:
            backup_instance = DriveBackup(
                credentials_path=json_path,
                folder_ids=[folder_id],
                output_dir=download_path,
                zip_output=zip_path
            )
            zip_file = backup_instance.run()
            #Mostramos los archivos descargados
            return make_response(render_template('backup.html', output_text=backup_instance.messages))
        except Exception as e:
            flash(f"Error al iniciar el respaldo: {str(e)}")

        return send_file(zip_file, as_attachment=True)

    # GET: cargar configuración
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM usuarios WHERE correo = %s", (session['username'],))
    user = cur.fetchone()

    if not user:
        cur.close()
        conn.close()
        return "❌ Error: Usuario no encontrado."

    user_id = user[0]

    cur.execute("SELECT * FROM usuarios_configuracion WHERE id_usuario = %s", (user_id,))
    config = cur.fetchone()

    cur.close()
    conn.close()

    if config:
        json_path = config[2]
        folder_id = config[3]
        download_path = config[4]
        zip_path = config[5]
    else:
        json_path = ""
        folder_id = ""
        download_path = ""
        zip_path = ""

    context = {
        "json_path": json_path,
        "folder_id": folder_id,
        "download_path": download_path,
        "zip_path": zip_path,
    }

    return render_template("backup.html", **context)

@app.route('/files', methods=['GET', 'POST'])
def files():
    # Implementar la lógica para mostrar los archivos
    # Obtendremos el id de la carpeta con la informacion de la base de datos relacionada al usuario
    # Obtener configuración del usuario
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM usuarios WHERE correo = %s", (session['username'],))
    user = cur.fetchone()

    if not user:
        cur.close()
        conn.close()
        flash("Usuario no encontrado.")
        return redirect(url_for('logout'))
    
    #Obtenemos las carpetas y el id del drive
    id_usuario = user[0]
    cur.execute("SELECT * FROM usuarios_configuracion WHERE id_usuario = %s", (id_usuario,))
    config = cur.fetchone()

    if not config:
        cur.close()
        conn.close()
        flash("Configuración no encontrada.")
        return redirect(url_for('logout'))

    folder_id = config[3]
    folder_path = config[4]

    # Procesamos la información para buscarlo en el archivo local
    ruta_local = folder_path, folder_id
    
    cur.close()
    conn.close()
        
    response = make_response(render_template('files.html'))
    return add_no_cache_headers(response)

@app.route('/logout')
def logout():
    session.pop('username', None)
    response = make_response(redirect(url_for('login')))
    return add_no_cache_headers(response)

if __name__ == '__main__':
    app.run(debug=True)
