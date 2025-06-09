import os
import io
import zipfile
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
import MySQLdb

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'passwd': '',
    'db': 'tren_carga',
    'charset': 'utf8mb4'
}

class DriveBackup:

    @staticmethod
    def get_db_connection():
        return MySQLdb.connect(**DB_CONFIG)

    def __init__(self, credentials_path, folder_ids, output_dir, zip_output):
        self.credentials_path = credentials_path
        self.folder_ids = folder_ids if isinstance(folder_ids, list) else [folder_ids]
        self.output_dir = output_dir
        self.zip_output = zip_output
        self.processed_folders = set()
        self.files_downloaded_counter = 0
        self.service = None
        self.db_conn = self.get_db_connection()
        self.messages = []  # Store messages for HTML display

    def detener_backup(self):
        self.processed_folders.clear()
        self.files_downloaded_counter = 0
        self.service = None
        if self.db_conn:
            self.db_conn.close()
            self.db_conn = None
        self.messages.append("Backup detenido.")

    def ensure_dir(self, path):
        os.makedirs(path, exist_ok=True)

    def authenticate(self):
        if not os.path.isfile(self.credentials_path) or not self.credentials_path.endswith('.json'):
            raise FileNotFoundError(f"Credenciales inválidas: {self.credentials_path}")
        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_path,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        self.service = build('drive', 'v3', credentials=credentials)

    def get_files_in_folder(self, folder_id, max_retries=3):
        query = f"'{folder_id}' in parents and trashed=false"
        files = []
        page_token = None
        while True:
            for attempt in range(1, max_retries + 1):
                try:
                    response = self.service.files().list(
                        q=query,
                        spaces='drive',
                        fields='nextPageToken, files(id, name, mimeType, modifiedTime, shortcutDetails)',
                        pageToken=page_token
                    ).execute()
                    break
                except Exception as e:
                    menssage = f"⚠️ Error al listar archivos en la carpeta {folder_id} (Intento {attempt}/{max_retries}): {e}"
                    print(menssage)
                    self.messages.append(menssage)
                    if attempt == max_retries:
                        menssage = f"❌ No se pudo obtener la lista de la carpeta {folder_id}."
                        print(menssage)
                        self.messages.append(menssage)
                        return files
            files.extend(response.get('files', []))
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        return files

    def download_file(self, file_id, file_name, folder_path, mime_type=None, max_retries=3):
        if mime_type and mime_type.startswith('application/vnd.google-apps'):
            export_mime_types = {
                'application/vnd.google-apps.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.google-apps.spreadsheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.google-apps.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'application/vnd.google-apps.drawing': 'image/png'
            }
            export_mime = export_mime_types.get(mime_type, 'application/pdf')
            request = self.service.files().export_media(fileId=file_id, mimeType=export_mime)
            ext_map = {
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
                'image/png': '.png',
                'application/pdf': '.pdf'
            }
            file_name += ext_map.get(export_mime, '.pdf')
        else:
            request = self.service.files().get_media(fileId=file_id)

        self.ensure_dir(folder_path)
        file_path = os.path.join(folder_path, file_name)

        for attempt in range(1, max_retries + 1):
            try:
                with io.FileIO(file_path, 'wb') as fh:
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                        if status:
                            menssage = f"Descargando {file_name}... {int(status.progress() * 100)}%"
                            print(menssage)
                            self.messages.append(menssage)
                menssage = f"✅ Descarga completada: {file_name}"
                print(menssage)
                self.messages.append(menssage)
                self.files_downloaded_counter += 1
                break
            except Exception as e:
                menssage = f"⚠️ Error al descargar {file_name} (Intento {attempt}/{max_retries}): {e}"
                print(menssage)
                self.messages.append(menssage)
                if attempt == max_retries:
                    menssage = f"❌ No se pudo descargar {file_name}."
                    print(menssage)
                    self.messages.append(menssage)

    def process_folder(self, folder_id, folder_path, drive_service):
        if folder_id in self.processed_folders:
            return
        self.processed_folders.add(folder_id)
        menssage = f"📂 Procesando carpeta: {folder_path}"
        print(menssage)
        self.messages.append(menssage)
        self.ensure_dir(folder_path)
        files = self.get_files_in_folder(folder_id)
        cursor = self.db_conn.cursor()

        for file in files:
            file_id = file['id']
            file_name = file['name']
            mime_type = file['mimeType']
            modified_time = file.get('modifiedTime')

            local_path = os.path.join(folder_path, file_name)
            cursor.execute("SELECT fecha_modificacion FROM archivos WHERE id_file = %s", (file_id,))
            row = cursor.fetchone()
            ya_existia = os.path.exists(local_path)

            if row and row[0] == modified_time and ya_existia and mime_type != 'application/vnd.google-apps.folder':
                menssage = f"⏩ Sin cambios: {file_name}"
                print(menssage)
                self.messages.append(menssage)
                continue

            if row:
                cursor.execute("""
                    UPDATE archivos SET fecha_modificacion = %s WHERE id_file = %s
                """, (modified_time, file_id))
            else:
                cursor.execute("""
                    INSERT INTO archivos (id_file, nombre, tipo, fecha_modificacion)
                    VALUES (%s, %s, %s, %s)
                """, (file_id, file_name, mime_type, modified_time))

            if mime_type == 'application/vnd.google-apps.shortcut':
                target_id = file['shortcutDetails']['targetId']
                target_file = self.service.files().get(
                    fileId=target_id,
                    fields='id, name, mimeType, modifiedTime'
                ).execute()

                if target_file['mimeType'] == 'application/vnd.google-apps.folder':
                    self.process_folder(target_id, os.path.join(folder_path, target_file['name']), self.service)
                else:
                    self.download_file(
                        target_file['id'], target_file['name'], folder_path,
                        target_file['mimeType']
                    )
                    self.files_downloaded_counter += 1
                continue

            if mime_type == 'application/vnd.google-apps.folder':
                self.process_folder(file_id, os.path.join(folder_path, file_name), self.service)
            else:
                self.download_file(file_id, file_name, folder_path, mime_type)
                self.files_downloaded_counter += 1

        self.db_conn.commit()
        cursor.close()

    def zip_directory(self):
        zip_name = f"descarga_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = os.path.join(str(self.zip_output), zip_name)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(self.output_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, self.output_dir)
                    zipf.write(file_path, arcname)
        return zip_path

    def run(self):
        menssage = "🚀 Iniciando respaldo..."
        print(menssage)
        self.messages.append(menssage)
        self.authenticate()
        self.ensure_dir(self.output_dir)
        self.ensure_dir(self.zip_output)

        for folder_id in self.folder_ids:
            self.process_folder(folder_id, os.path.join(self.output_dir, folder_id), self.service)
            return self.messages 

        zip_path = self.zip_directory()
        menssage = f"✅ Respaldo completado. ZIP generado: {zip_path}"
        print(menssage)
        self.messages.append(menssage)
        return self.messages  # Return all messages for HTML display
