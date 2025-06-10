#En este script haremos la importacion de los archivos excel que estan dentro de nuestras carpetas de google drive que descargamos
#La ruta es la siguiente: backup/poxila/025 -  Lopez Gomez Francisco/TC_13358/01. REGISTROS/TC_13358.xlsx y asi es con todos los archivos
#haremos un recorrido de todas las carpetas buscando los archivos excel que esten dentro de 01. REGISTROS y los importaremos a nuestra base de datos

#Importamos la libreria de pandas
import os
import io
import zipfile
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
import MySQLdb
import pandas as pd

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'passwd': '',
    'db': 'tren_carga',
    'charset': 'utf8mb4'
}

#Definimos donde empieza la carpeta del backup
path = './backup'

class ExportExcel:
    @staticmethod
    def get_db_connection():
        return MySQLdb.connect(**DB_CONFIG)
    
    def __init__(self, name_folder):
        self.name_folder = name_folder
    
    def procesar_codigo_poligono(self):
        connection = self.get_db_connection()
        cursor = connection.cursor()
        try:
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.endswith('.xlsx') and '01. REGISTROS' in root:
                        file_path = os.path.join(root, file)
                        try:
                            df = pd.read_excel(file_path)
                            if df.shape[1] < 24:
                                print(f"⚠️ {file_path} tiene menos de 24 columnas. Se omite.")
                                continue

                            codigo_poligono = os.path.basename(os.path.dirname(root))
                            clave_registro = os.path.basename(root)

                            for _, row in df.iterrows():
                                sql = """
                                INSERT INTO registro_excavacion(
                                    codigo_poligono, clave_registro, clave_excavacion, tramo, id_monumento, no_arqueologo,
                                    punto_georeferencia, codigo, id_topografo, no_bolsa, procedencia, contexto_excavacion,
                                    tipo_excavacion, coordenada_x, coordenada_y, capa, meteria_prima, asociacion,
                                    descripcion_punto, descripcion_estrato, fecha_registro, foto_1, foto_2, foto_3, foto_4
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                                valores = tuple([codigo_poligono, clave_registro] + [row[i] for i in range(24)])
                                cursor.execute(sql, valores)
                        except Exception as e:
                            print(f"Error leyendo archivo {file_path}: {str(e)}")
            connection.commit()
            print("✅ Registros insertados correctamente.")
        except Exception as e:
            print(f"❌ Error general: {str(e)}")
        finally:
            cursor.close()
            connection.close()
