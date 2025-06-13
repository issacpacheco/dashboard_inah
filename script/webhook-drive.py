from flask import Flask, request
from script.descargar_drive import DriveBackup
from google.oauth2 import service_account
from googleapiclient.discovery import build
import MySQLdb

app = Flask(__name__)

# Conexión a base de datos
def get_folder_ids_from_db():
    db = MySQLdb.connect(host="localhost", user="root", passwd="", db="tren_carga", charset="utf8mb4")
    cursor = db.cursor()
    cursor.execute("SELECT folder_id FROM folders_drive")
    folder_ids = [row[0] for row in cursor.fetchall()]
    cursor.close()
    db.close()
    return folder_ids

def get_saved_token_from_db():
    db = MySQLdb.connect(host="localhost", user="root", passwd="", db="tren_carga", charset="utf8mb4")
    cursor = db.cursor()
    cursor.execute("SELECT token FROM drive_tokens ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    cursor.close()
    db.close()
    if row:
        return row[0]
    else:
        return None

def save_new_token_to_db(token):
    db = MySQLdb.connect(host="localhost", user="root", passwd="", db="tren_carga", charset="utf8mb4")
    cursor = db.cursor()
    cursor.execute("INSERT INTO drive_tokens (token) VALUES (%s)", (token,))
    db.commit()
    cursor.close()
    db.close()

@app.route('/drive-webhook', methods=['POST'])
def webhook():
    channel_id = request.headers.get('X-Goog-Channel-ID')
    resource_id = request.headers.get('X-Goog-Resource-ID')
    print(f"🔔 Cambio recibido - Channel: {channel_id}, Resource: {resource_id}")

    credentials = service_account.Credentials.from_service_account_file(
        'credenciales.json',
        scopes=['https://www.googleapis.com/auth/drive']
    )
    service = build('drive', 'v3', credentials=credentials)

    # Obtener la lista de cambios desde el último token
    start_token = get_saved_token_from_db()  # Este debes guardar en la BD o en archivo
    changes = service.changes().list(pageToken=start_token, spaces='drive', fields='*').execute()

    folder_ids = get_folder_ids_from_db()

    for change in changes.get('changes', []):
        file = change.get('file', {})
        parents = file.get('parents', [])
        if any(folder_id in parents for folder_id in folder_ids):
            print(f"📁 Archivo cambiado en carpeta monitoreada: {file['name']}")
            # Llama al proceso de respaldo para esa carpeta
            folder_id = next((fid for fid in parents if fid in folder_ids), None)
            if folder_id:
                backup = DriveBackup(
                    name_folder='Respaldo_' + folder_id,
                    credentials_path='credenciales.json',
                    folder_ids=[folder_id],
                    output_dir='descargas/',
                    zip_output='respaldos_zip/'
                )
                backup.run()

    save_new_token_to_db(changes['newStartPageToken'])  # Guarda el nuevo token
    return '', 200

if __name__ == '__main__':
    app.run(port=5000)
