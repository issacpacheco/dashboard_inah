import os
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import MySQLdb
import MySQLdb.cursors

# Datos de conexión
usuario = 'root'
contraseña = ''
host = 'localhost'
puerto = 3306
basedatos = 'tren_carga'
tabla = 'registro_excavacion_topografia'

class ExportarGeoPackage:
    def __init__(self, nombre_poligono, id_monumento):
        self.nombre_poligono = nombre_poligono
        self.id_monumento = id_monumento

    def exportar_geopackage(self):
        conn = None
        try:
            # Conectar a la base de datos usando MySQLdb
            print("📡 Conectando a la base de datos...")
            conn = MySQLdb.connect(
                host=host,
                user=usuario,
                passwd=contraseña,
                db=basedatos,
                port=puerto,
                cursorclass=MySQLdb.cursors.DictCursor,
                charset='utf8mb4'
            )
            cursor = conn.cursor()
            query = f"SELECT * FROM {tabla} WHERE codigo_poligono = %s AND id_monumento = %s"
            print(f"🔍 Ejecutando consulta: {query} con parámetros ({self.nombre_poligono}, {self.id_monumento})")
            cursor.execute(query, (self.nombre_poligono, self.id_monumento,))
            rows = cursor.fetchall()
            df = pd.DataFrame(rows)

            if df.empty:
                return "⚠️ No se encontraron registros con ese código de polígono."

            print("📍 Procesando coordenadas...")
            df['x'] = pd.to_numeric(df['e'], errors='coerce')
            df['y'] = pd.to_numeric(df['n'], errors='coerce')
            df = df.dropna(subset=['x', 'y'])

            if df.empty:
                return "⚠️ Todos los registros tienen coordenadas inválidas."

            geometry = [Point(xy) for xy in zip(df['x'], df['y'])]
            gdf = gpd.GeoDataFrame(df, geometry=geometry)
            gdf.set_crs(epsg=6371, inplace=True)

            filename = f"registro_excavacion_topografia_{self.nombre_poligono}_{self.id_monumento}.gpkg"
            gdf.to_file(filename, layer=tabla, driver="GPKG")

            if os.path.exists(filename):
                return f"✅ Exportación completada: {filename}"
            else:
                return "❌ Error al guardar el archivo GeoPackage."

        except MySQLdb.Error as e:
            return f"❌ Error de base de datos: {str(e)}"
        except Exception as e:
            return f"❌ Error general: {str(e)}"
        finally:
            if conn:
                conn.close()

# Si ejecutas este script directamente
if __name__ == "__main__":
    nombre = input("🔷 Ingresa el nombre del polígono a exportar: ")
    exportador = ExportarGeoPackage(nombre)
    mensaje = exportador.exportar_geopackage()
    print(mensaje)
