# import geopandas as gpd
# import pandas as pd
# import os
# import fiona
# from sqlalchemy import create_engine

# def limpiar_texto(df):
#     for col in df.select_dtypes(include=['object']).columns:
#         df[col] = df[col].astype(str).apply(lambda x: x.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore'))
#     return df

# def importar_gpkg(nombre_archivo, nombre):
#     if not os.path.exists('GPKS'):
#         print("La carpeta GPKS no existe.")
#         exit()

#     archivos = [f for f in os.listdir('GPKS') if f.endswith('.gpkg') and nombre in f]
#     print("Archivos encontrados:", archivos)

#     if not archivos:
#         print("No se encontraron archivos que contengan '{}'.".format(nombre))
#         exit()

#     gdfs = []

#     for archivo in archivos:
#         ruta = os.path.join('GPKS', archivo)

#         try:
#             capas = fiona.listlayers(ruta)
#         except Exception as e:
#             print(f"⚠️ Error al leer capas en {archivo}: {e}")
#             continue

#         if not capas:
#             print(f"⚠️ No se encontraron capas en {archivo}")
#             continue

#         print(f"📄 Cargando capa '{capas[0]}' de {archivo}")
#         gdf = gpd.read_file(ruta, layer=capas[0])

#         if not isinstance(gdf, gpd.GeoDataFrame):
#             print(f"⚠️ {archivo} no es un GeoDataFrame válido.")
#             continue

#         gdf = gdf.to_crs(epsg=6371)
#         gdfs.append(gdf)

#     if gdfs:
#         gdf_total = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:6371")
#         gdf_total.to_file(f'GPKS/{nombre}_poligonos.geojson', driver='GeoJSON')
#         gdf_total.to_csv(f'GPKS/{nombre}.csv', index=False)
#         gdf_total.to_file(f'GPKS/{nombre}_poligonos.gpkg', driver='GPKG')

#         if nombre == 'RETI':
#             try:
#                 engine = create_engine('postgresql://postgres:postgres@localhost:5432/local')
#                 gdf_total = limpiar_texto(gdf_total)

#                 # Elimina 'encoding' porque no es válido en to_sql
#                 gdf_total.to_sql(
#                     f'{nombre}_poligonos',
#                     engine,
#                     if_exists='replace',
#                     index=False,
#                     schema='tren_carga',
#                     method='multi'
#                 )
#                 print("🗃️ Datos exportados a PostgreSQL en esquema 'tre_carga'.")
#             except Exception as e:
#                 print(f"❌ Error al exportar a PostgreSQL: {e}")

#         print("✅ Archivos guardados correctamente.")
#     else:
#         print("❌ No se cargaron datos válidos.")

# if __name__ == "__main__":
#     importar_gpkg('RETI', 'RETI')
#     importar_gpkg('DPP', 'DPP')
#     importar_gpkg('DPL', 'DPL')

import geopandas as gpd
import pandas as pd
import os
import fiona
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from geoalchemy2 import Geometry
from shapely.geometry import MultiPolygon, Polygon

# Configuración de conexión
DATABASE_URL = 'postgresql://postgres:root@localhost:5432/local'
SCHEMA_NAME = 'tren_carga'
def habilitar_postgis():
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            print("🔌 Conectado a la base de datos.")
            conn.execute(text("SET search_path TO public;"))  # PostGIS se instala en public

            resultado = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'postgis'
                );
            """))
            if resultado.scalar():
                print("✅ La extensión PostGIS ya está habilitada.")
            else:
                print("ℹ️ Habilitando PostGIS...")
                conn.execute(text("CREATE EXTENSION postgis;"))
                print("✅ PostGIS habilitado exitosamente.")
    except SQLAlchemyError as e:
        print(f"❌ Error al habilitar PostGIS: {e}")
        raise


def limpiar_texto(df):
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(lambda val: (
                val.decode('utf-8', errors='ignore') if isinstance(val, bytes)
                else str(val).encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
            ))
    return df

def importar_gpkg(nombre):
    habilitar_postgis()

    if not os.path.exists('GPKS'):
        print("❌ La carpeta GPKS no existe.")
        return

    archivos = [f for f in os.listdir('GPKS') if f.endswith('.gpkg') and nombre in f]
    if not archivos:
        print(f"❌ No se encontraron archivos que contengan '{nombre}'.")
        return

    gdfs = []
    for archivo in archivos:
        ruta = os.path.join('GPKS', archivo)
        try:
            capas = fiona.listlayers(ruta)
            print(f"📄 Cargando capa '{capas[0]}' de {archivo}")
            gdf = gpd.read_file(ruta, layer=capas[0])
            gdf = gdf.to_crs(epsg=6371)

            gdf['geometry'] = gdf['geometry'].apply(
                lambda geom: MultiPolygon([geom]) if isinstance(geom, Polygon) else geom
            )

            gdfs.append(gdf)
        except Exception as e:
            print(f"⚠️ Error al procesar {archivo}: {e}")

    if not gdfs:
        print(f"❌ No se pudieron cargar datos para {nombre}.")
        return

    gdf_total = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:6371")
    gdf_total = limpiar_texto(gdf_total)

    # Exportaciones locales
    gdf_total.to_file(f'GPKS/{nombre}_poligonos.geojson', driver='GeoJSON')
    gdf_total.to_csv(f'GPKS/{nombre}.csv', index=False)
    gdf_total.to_file(f'GPKS/{nombre}_poligonos.gpkg', driver='GPKG')

    # Exportar a PostgreSQL
    try:
        engine = create_engine(DATABASE_URL)
        print(f"⬆️ Exportando {nombre} a PostgreSQL/PostGIS...")

        # El parámetro schema se usa explícitamente aquí
        gdf_total.to_postgis(
            name=f"{nombre}_poligonos",
            con=engine,
            schema=SCHEMA_NAME,
            if_exists='replace',
            index=False,
            dtype={'geometry': Geometry(geometry_type='MULTIPOLYGON', srid=6371)}
        )

        print(f"✅ {nombre} exportado exitosamente a PostgreSQL/PostGIS.")
    except Exception as e:
        print(f"❌ Error al exportar {nombre} a PostgreSQL/PostGIS: {e}")

if __name__ == "__main__":
    importar_gpkg('RETI')
    importar_gpkg('DPP')
    importar_gpkg('DPL')
    print("🏁 Importación finalizada.")
