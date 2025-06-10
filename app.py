from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, send_file, abort, send_from_directory
from werkzeug.utils import safe_join
from flask_autoindex import AutoIndex
from script.descargar_drive import DriveBackup
from flask_bcrypt import Bcrypt
import MySQLdb
import os

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

@app.route('/config_drive/config_drive', methods=['GET', 'POST'])
def config_drive():
    # Obtener configuración del usuario
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM config_drive")
    config_drive = cur.fetchone()
    cur.close()


    arreglo_config_drive = []
    if config_drive:
        arreglo_config_drive.append({
            'id': config_drive[0],
            'nombre' : config_drive[1],
            'folder_id': config_drive[2],
            'ruta_json': config_drive[3],
            'ruta_local': config_drive[4],
            'ruta_zip': config_drive[5]
        })


    response = make_response(render_template('config_drive/config_drive.html', config_drive=arreglo_config_drive))
    return add_no_cache_headers(response)

@app.route('/config_drive/config_drive_abc', methods=['GET', 'POST'])
def config_drive_abc():
    config_drive = None
    id = None
    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == 'GET':
        accion = request.args.get("accion")
        if accion == "agregar":
            context = {
                'accion': accion
            }
        elif accion == "editar":
            id = request.args.get("id")
            cur.execute("SELECT * FROM config_drive WHERE id = %s", (id,))
            config_drive = cur.fetchone()
            context = {
                'id': config_drive[0],
                'nombre': config_drive[1],
                'folder_id': config_drive[2],
                'ruta_json': config_drive[3],
                'ruta_local': config_drive[4],
                'ruta_zip': config_drive[5],
                'accion': accion,
                'id': id
            }
        elif accion == "eliminar":
            id = request.args.get("id")
            cur.execute("SELECT * FROM config_drive WHERE id = %s", (id,))
            config_drive = cur.fetchone()
            context = {
                'id': config_drive[0],
                'nombre': config_drive[1],
                'folder_id': config_drive[2],
                'ruta_json': config_drive[3],
                'ruta_local': config_drive[4],
                'ruta_zip': config_drive[5],
                'accion': accion,
                'id': id
            }
        else:
            flash("Acción no reconocida.", "error")

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        id_folder = request.form.get('id_folder')
        json_path = request.form.get('json_path')
        download_path = request.form.get('download_path')
        zip_path = request.form.get('zip_path')
        accion = request.form.get('accion')
        id = request.form.get('id')

        if accion == 'agregar':
            cur.execute('INSERT INTO config_drive (nombre, id_folder, ruta_json, ruta_descargar, ruta_zip) VALUES (%s, %s, %s, %s, %s)', (nombre, id_folder, json_path, download_path, zip_path))
            conn.commit()
            flash("Configuración guardada exitosamente.")
        elif accion == 'editar':
            cur.execute('UPDATE config_drive SET nombre=%s, id_folder=%s, ruta_json=%s, ruta_descargar=%s, ruta_zip=%s WHERE id=%s', (nombre, id_folder, json_path, download_path, zip_path, id))
            conn.commit()
            flash("Configuración actualizada exitosamente.")
        elif accion == 'eliminar':
            cur.execute('DELETE FROM config_drive WHERE id=%s', (id,))
            conn.commit()
            flash("Configuración eliminada exitosamente.")
        else:
            flash("Acción no reconocida.", "error")

        cur.close()
        conn.close()
        return redirect(url_for('config_drive'))

    cur.close()
    conn.close()
    response = make_response(render_template('config_drive/config_drive_abc.html', **context))
    return add_no_cache_headers(response)

@app.route('/respaldo', methods=['GET', 'POST'])
def backup():
    global backup_instance
    zip_file = None
    if request.method == 'POST':
        accion = request.form.get('accion')
        id = request.form.get('id')
        if accion == "detener_respaldo":
            if backup_instance:
                backup_instance.detener_backup()
                backup_instance = None
                flash("Respaldo detenido exitosamente.")
            else:
                flash("No hay un respaldo en curso.")
            return redirect(url_for('backup'))
        elif accion == 'iniciar_respaldo':
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("SELECT * FROM config_drive WHERE id = %s", (id,))
            config_drive = cur.fetchone()

            cur.close()
            conn.close()

            if not config_drive:
                flash("Configuración no encontrada.")
                return redirect(url_for('backup'))

            nombre = config_drive[1]
            folder_id = config_drive[2]
            json_path = config_drive[3]
            download_path = config_drive[4]
            zip_path = config_drive[5]

            try:
                backup_instance = DriveBackup(
                    name_folder=nombre,
                    credentials_path=json_path,
                    folder_ids=[folder_id],
                    output_dir=download_path,
                    zip_output=zip_path
                )
                zip_file = backup_instance.run()
                #Mostramos los archivos descargados
                return make_response(render_template('respaldo.html', output_text=backup_instance.messages))
            except Exception as e:
                flash(f"Error al iniciar el respaldo: {str(e)}")

            return send_file(zip_file, as_attachment=True)
        else:
            flash("Acción no reconocida.", "error")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM config_drive")
    config_drive = cur.fetchone()
    cur.close()

    arreglo_config_drive = []
    if config_drive:
        arreglo_config_drive.append({
            'id': config_drive[0],
            'nombre' : config_drive[1],
            'folder_id': config_drive[2],
            'ruta_json': config_drive[3],
            'ruta_local': config_drive[4],
            'ruta_zip': config_drive[5]
        })

    response = make_response(render_template('respaldo.html', config_drive=arreglo_config_drive))
    return add_no_cache_headers(response)

@app.route('/files')
def files():    
    return redirect(url_for('explorer'))

@app.route('/files/repositorios/', defaults={'req_path': '', 'folder_id': ''})
@app.route('/files/repositorios/<path:req_path>', defaults={'folder_id': ''})
def explorer(folder_id, req_path):
    print("Empieza files")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM config_drive")
    config = cur.fetchone()
    cur.close()
    conn.close()

    if not config:
        flash("Configuración no encontrada.")
        return redirect(url_for('logout'))

    arreglo_config = []
    if config:
        arreglo_config.append({
            'id': config[0],
            'name': config[1],
            'folder_id': config[2],
            'json_path': config[3],
            'download_path': config[4],
            'zip_path': config[5]
        })

    name_folder = config[1]       # Nombre de la carpeta que se va a descargar
    base_path = config[4]         # Ruta local al respaldo
    folder_id_config = config[3]  # folder_id real del drive (no se usa en la navegación local)

    req_path = req_path.strip('/')
    abs_path = os.path.join(base_path, req_path)

    if not os.path.exists(abs_path):
        return abort(404)

    if os.path.isfile(abs_path):
        return send_file(abs_path, as_attachment=True)

    files = os.listdir(abs_path)
    files.sort()

    return render_template(
        'files.html',
        name_folder=name_folder,
        config_drive=arreglo_config,
        files=files,
        folder_id=folder_id,      # el mismo que vino por URL
        current_path=req_path,    # usado en la vista para la navegación
        abs_path=abs_path,
        os=os                     # pasamos el módulo os para usar en la plantilla
    )

@app.route('/backup/<path:file_path>', methods=['GET'])
def view_file(file_path):
    # Define la ruta base donde están tus archivos respaldados
    base_dir = os.path.abspath('./backup')  # cámbiala a tu ruta real

    # Combina de forma segura la ruta base con la solicitada
    safe_path = safe_join(base_dir, file_path)

    # Verifica que el archivo exista
    if not os.path.exists(safe_path):
        abort(404)

    # Obtén el directorio y nombre del archivo
    directory = os.path.dirname(safe_path)
    filename = os.path.basename(safe_path)

    # Envía el archivo sin forzar la descarga
    return send_from_directory(directory, filename, as_attachment=False)

@app.route('/logout')
def logout():
    session.pop('username', None)
    response = make_response(redirect(url_for('login')))
    return add_no_cache_headers(response)

if __name__ == '__main__':
    app.run(debug=True)
