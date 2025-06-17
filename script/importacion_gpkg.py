# import geopandas as gpd
# import pandas as pd
# import os
# import fiona
# from sqlalchemy import create_engine, text
# from sqlalchemy.exc import SQLAlchemyError
# from geoalchemy2 import Geometry
# from shapely.geometry import MultiPolygon, Polygon, shape, mapping

# # Configuración de conexión
# DATABASE_URL = 'postgresql://postgres:root@localhost:5432/local'
# SCHEMA_NAME = 'tren_carga'

# def habilitar_postgis():
#     # Verificar si la extensión PostGIS está habilitada
#     try:
#         engine = create_engine(DATABASE_URL)
#         with engine.connect() as conn:
#             print("🔌 Conectado a la base de datos.")
#             resultado = conn.execute(text("""
#                 SELECT EXISTS (
#                     SELECT 1 FROM pg_extension WHERE extname = 'postgis'
#                 );
#             """))
#             if resultado.scalar():
#                 print("La extensión PostGIS ya está habilitada.")
#             else:
#                 print("Habilitando PostGIS...")
#                 conn.execute(text("CREATE EXTENSION postgis;"))
#                 print("PostGIS habilitado exitosamente.")
#     except SQLAlchemyError as e:
#         print(f"Error al habilitar PostGIS: {e}")
#         raise

# def limpiar_texto(df):
#     # Limpiamos los textos en el DataFrame
#     for col in df.columns:
#         if df[col].dtype == object:
#             df[col] = df[col].apply(lambda val: (
#                 val.decode('utf-8', errors='ignore') if isinstance(val, bytes)
#                 else str(val).encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
#             ))
#     return df

# def drop_z(geom):
#     # Elimina las coordenadas Z de una geometría si existen
#     if geom and hasattr(geom, 'has_z') and geom.has_z:
#         geojson = mapping(geom)
#         def remove_z(coords):
#             if isinstance(coords[0], (float, int)):
#                 return coords[:2]
#             return [remove_z(c) for c in coords]
#         geojson['coordinates'] = remove_z(geojson['coordinates'])
#         return shape(geojson)
#     return geom

# def importar_gpkg(nombre):
#     # Verifica si la carpeta GPKS existe y contiene archivos .gpkg
#     habilitar_postgis()

#     if not os.path.exists('GPKS'):
#         print("La carpeta GPKS no existe.")
#         return

#     archivos = [f for f in os.listdir('GPKS') if f.endswith('.gpkg') and nombre in f]
#     if not archivos:
#         print(f"No se encontraron archivos que contengan '{nombre}'.")
#         return

#     gdfs = []
#     for archivo in archivos:
#         ruta = os.path.join('GPKS', archivo)
#         try:
#             capas = fiona.listlayers(ruta)
#             print(f"Cargando capa '{capas[0]}' de {archivo}")
#             gdf = gpd.read_file(ruta, layer=capas[0])
#             gdf = gdf.to_crs(epsg=6371)

#             # Convertir Polygons a MultiPolygons si es necesario
#             gdf['geometry'] = gdf['geometry'].apply(
#                 lambda geom: MultiPolygon([geom]) if isinstance(geom, Polygon) else geom
#             )

#             # Remover coordenadas Z
#             gdf['geometry'] = gdf['geometry'].apply(drop_z)

#             gdfs.append(gdf)
#         except Exception as e:
#             print(f"Error al procesar {archivo}: {e}")

#     if not gdfs:
#         print(f"No se pudieron cargar datos para {nombre}.")
#         return

#     gdf_total = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:6371")
#     gdf_total = limpiar_texto(gdf_total)

#     # Exportar a PostgreSQL
#     try:
#         engine = create_engine(DATABASE_URL)
#         print(f"Exportando {nombre} a PostgreSQL/PostGIS...")

#         gdf_total.to_postgis(
#             name=f"{nombre}_poligonos",
#             con=engine,
#             schema=SCHEMA_NAME,
#             if_exists='replace',
#             index=False,
#             dtype={'geometry': Geometry(geometry_type='MULTIPOLYGON', srid=6371)}
#         )

#         print(f"{nombre} exportado exitosamente a PostgreSQL/PostGIS.")
#     except Exception as e:
#         print(f"Error al exportar {nombre} a PostgreSQL/PostGIS: {e}")

# if __name__ == "__main__":
#     importar_gpkg('RETI')
#     importar_gpkg('DPP')
#     importar_gpkg('DPL')
#     print("Importación finalizada.")

import geopandas as gpd
import pandas as pd
import os
import fiona
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from geoalchemy2 import Geometry
from shapely.geometry import MultiPolygon, Polygon, shape, mapping

# Configuración de conexión a la base de datos PostgreSQL/PostGIS
DATABASE_URL = 'postgresql://postgres:root@localhost:5432/local'
SCHEMA_NAME = 'tren_carga'

def habilitar_postgis():
    """
    Verifica si la extensión PostGIS está habilitada en la base de datos.
    Si no está habilitada, intenta crearla.
    """
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            print("🔌 Conectado a la base de datos.")
            # Consulta para verificar la existencia de la extensión PostGIS
            resultado = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'postgis'
                );
            """))
            if resultado.scalar():
                print("La extensión PostGIS ya está habilitada.")
            else:
                print("Habilitando PostGIS...")
                # Habilita la extensión PostGIS
                conn.execute(text("CREATE EXTENSION postgis;"))
                print("PostGIS habilitado exitosamente.")
            conn.commit() # Asegurarse de que la transacción se guarda
    except SQLAlchemyError as e:
        print(f"Error al habilitar PostGIS: {e}")
        raise # Vuelve a lanzar la excepción para notificar el fallo

def limpiar_texto(df):
    """
    Limpia las columnas de tipo 'object' (usualmente cadenas) en un DataFrame
    para manejar correctamente codificaciones de caracteres.
    """
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(lambda val: (
                # Decodifica bytes a utf-8, ignorando errores
                val.decode('utf-8', errors='ignore') if isinstance(val, bytes)
                # Si no son bytes, intenta codificar a latin-1 y luego decodificar a utf-8
                else str(val).encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
            ))
    return df

def drop_z(geom):
    """
    Elimina la coordenada Z de una geometría (Point, LineString, Polygon, etc.)
    si esta existe. Convierte la geometría a 2D.
    """
    if geom and hasattr(geom, 'has_z') and geom.has_z:
        # Convierte la geometría a un diccionario GeoJSON
        geojson = mapping(geom)
        def remove_z(coords):
            # Si las coordenadas son un punto (float, int), toma solo X e Y
            if isinstance(coords[0], (float, int)):
                return coords[:2]
            # Si son una lista de coordenadas (para LineString, Polygon), aplica recursivamente
            return [remove_z(c) for c in coords]
        # Aplica la función para remover Z a las coordenadas de GeoJSON
        geojson['coordinates'] = remove_z(geojson['coordinates'])
        # Vuelve a crear la geometría desde el GeoJSON modificado
        return shape(geojson)
    return geom # Retorna la geometría original si no tiene Z o es nula

def importar_gpkg(nombre):
    """
    Busca archivos .gpkg que contengan el 'nombre' especificado de forma recursiva
    en la carpeta '../backup', los carga como GeoDataFrames, los procesa
    (convierte a MultiPolygon, elimina coordenadas Z, limpia texto)
    y los exporta a una tabla PostGIS.
    """
    habilitar_postgis() # Asegura que PostGIS esté habilitado antes de la importación

    # Verifica si la carpeta ../backup existe
    if not os.path.exists('../backup'):
        print("La carpeta ../backup no existe.")
        return

    archivos = []
    # Recorre recursivamente toda la carpeta ../backup
    for root, dirs, files in os.walk('../backup'):
        for f in files:
            # Filtra archivos .gpkg que contengan el nombre especificado
            if f.endswith('.gpkg') and nombre in f:
                print(f"Encontrado archivo: {f} en {root}")
                archivos.append(os.path.join(root, f))

    if not archivos:
        print(f"No se encontraron archivos que contengan '{nombre}'.")
        return
    
    gdfs = []
    for archivo in archivos:
        try:
            # Lista las capas dentro del archivo GPKG y carga la primera
            capas = fiona.listlayers(archivo)
            print(f"Cargando capa '{capas[0]}' de {archivo}")
            gdf = gpd.read_file(archivo, layer=capas[0])
            # Proyecta el GeoDataFrame al sistema de coordenadas EPSG:6371
            gdf = gdf.to_crs(epsg=6371)

            # Convierte geometrías Polygon a MultiPolygon si es necesario
            # Esto asegura consistencia en el tipo de geometría para la base de datos
            gdf['geometry'] = gdf['geometry'].apply(
                lambda geom: MultiPolygon([geom]) if isinstance(geom, Polygon) else geom
            )

            # Elimina las coordenadas Z de las geometrías
            gdf['geometry'] = gdf['geometry'].apply(drop_z)

            gdfs.append(gdf)
        except Exception as e:
            print(f"Error al procesar {archivo}: {e}")

    if not gdfs:
        print(f"No se pudieron cargar datos para {nombre}.")
        return

    # Concatena todos los GeoDataFrames cargados en uno solo
    gdf_total = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:6371")
    # Limpia el texto de todas las columnas del GeoDataFrame
    gdf_total = limpiar_texto(gdf_total)

    # Exportar a PostgreSQL/PostGIS
    try:
        engine = create_engine(DATABASE_URL)
        print(f"Exportando {nombre} a PostgreSQL/PostGIS...")      

        # Utiliza to_postgis para guardar el GeoDataFrame, especificando el tipo de geometría
        gdf_total.to_postgis(
            name=f"{nombre}_poligonos", # Nombre de la tabla en la base de datos
            con=engine, # Conexión a la base de datos
            schema=SCHEMA_NAME, # Esquema de la base de datos
            if_exists='replace', # Reemplaza la tabla si ya existe
            index=False, # No guarda el índice del DataFrame como columna
            # Especifica el tipo de geometría para la columna 'geometry' en PostGIS
            dtype={'geometry': Geometry(geometry_type='MULTIPOLYGON', srid=6371)}
        )

        print(f"{nombre} exportado exitosamente a PostgreSQL/PostGIS.")
    except Exception as e:
        print(f"Error al exportar {nombre} a PostgreSQL/PostGIS: {e}")

if __name__ == "__main__":
    # Ejecuta la importación para los nombres especificados
    importar_gpkg('RETI')
    importar_gpkg('DPP')
    importar_gpkg('DPL')
    print("Importación finalizada.")