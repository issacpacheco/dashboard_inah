import os
import pandas as pd
from script.conexion import Conexion

class ExportExcel:
    def __init__(self, name_folder):
        self.name_folder = name_folder

    def procesar_codigo_poligono(self):
        connection_mysql = None
        connection_postgres = None
        cursor = None

        try:
            # 🔌 Conexiones a las bases de datos
            connection_mysql = Conexion.conectar_mysql()
            connection_postgres = Conexion.conectar_postgres()

            if connection_mysql is None or connection_postgres is None:
                if connection_mysql:
                    print("❌ No se pudo establecer la conexion a MySQL.")
                if connection_postgres:
                    print("❌ No se pudo establecer la conexion a PostgreSQL.")
                return

            cursor = connection_mysql.cursor()
            base_path = f'./backup/{self.name_folder}'

            for root, _, files in os.walk(base_path):
                for file in files:
                    if file.endswith('.xlsx') and '01. REGISTRO' in root:
                        file_path = os.path.join(root, file)
                        print(f"📂 Procesando archivo: {file_path}")
                        try:
                            df = pd.read_excel(file_path)

                            if df.shape[1] < 23:
                                print(f"⚠️ {file_path} tiene menos de 23 columnas. Se omite.")
                                continue

                            for _, row in df.iterrows():
                                codigo_poligono = self.name_folder
                                clave_registro = os.path.basename(os.path.dirname(root))
                                clave_excavacion = None if pd.isna(row.iloc[0]) else row.iloc[0]
                                codigo_topografo = None if pd.isna(row.iloc[5]) else row.iloc[5]

                                # Verificar si ya existe el registro
                                sql_check = """
                                    SELECT COUNT(*) FROM registro_excavacion 
                                    WHERE codigo_poligono = %s AND clave_registro = %s AND clave_excavacion = %s
                                """
                                cursor.execute(sql_check, (codigo_poligono, clave_registro, clave_excavacion))
                                exists = cursor.fetchone()[0]

                                valores_base = [None if pd.isna(row.iloc[i]) else row.iloc[i] for i in range(1, 24)]

                                if exists:
                                    print(f"🔁 Modificando registro {clave_excavacion}")
                                    sql_update = """
                                        UPDATE registro_excavacion SET
                                            tramo = %s, id_monumento = %s, no_arqueologo = %s, punto_georeferencia = %s,
                                            codigo = %s, id_topografo = %s, no_bolsa = %s, procedencia = %s, contexto_excavacion = %s,
                                            tipo_excavacion = %s, coordenada_x = %s, coordenada_y = %s, capa = %s, material = %s,
                                            meteria_prima = %s, asociacion = %s, descripcion_punto = %s, descripcion_estrato = %s,
                                            fecha_registro = %s, foto_1 = %s, foto_2 = %s, foto_3 = %s, foto_4 = %s
                                        WHERE codigo_poligono = %s AND clave_registro = %s AND clave_excavacion = %s
                                    """
                                    valores_update = tuple(valores_base + [codigo_poligono, clave_registro, clave_excavacion])
                                    cursor.execute(sql_update, valores_update)
                                else:
                                    print(f"➕ Insertando nuevo registro {clave_excavacion}")
                                    sql_insert = """
                                        INSERT INTO registro_excavacion(
                                            codigo_poligono, clave_registro, clave_excavacion, tramo, id_monumento, no_arqueologo,
                                            punto_georeferencia, codigo, id_topografo, no_bolsa, procedencia, contexto_excavacion,
                                            tipo_excavacion, coordenada_x, coordenada_y, capa, material, meteria_prima, asociacion,
                                            descripcion_punto, descripcion_estrato, fecha_registro, foto_1, foto_2, foto_3, foto_4)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    """
                                    valores_insert = tuple([codigo_poligono, clave_registro, clave_excavacion] + valores_base)
                                    cursor.execute(sql_insert, valores_insert)

                                # 🔄 Consultar PostgreSQL para datos topográficos
                                try:
                                    print(f"🔎 Buscando topografía para {clave_excavacion}")
                                    cursor_postgres = connection_postgres.cursor()
                                    sql_check_topo = """
                                        SELECT id_punto, n, e, z, codigo FROM tren_carga.tc_topografia WHERE id_punto = %s AND codigo = %s
                                    """
                                    cursor_postgres.execute(sql_check_topo, (clave_excavacion,codigo_topografo,))
                                    result = cursor_postgres.fetchone()
                                    cursor_postgres.close()
                                    # print(f"🔎 Resultado de la consulta: {result}")

                                    if result:
                                        _, n, e, z, codigo = result
                                        #Consultamos si ya existe el registro en la base de datos
                                        sql_check = """
                                            SELECT COUNT(*) FROM registro_excavacion_topografia 
                                            WHERE codigo_poligono = %s AND clave_registro = %s AND clave_excavacion = %s
                                        """
                                        cursor.execute(sql_check, (codigo_poligono, clave_registro, clave_excavacion))
                                        exists = cursor.fetchone()[0]

                                        if exists:
                                            print(f"🔁 Modificando registro topográfico {clave_excavacion}")
                                            #Modificamos todos los campos del registro
                                            sql_update_topografia = """
                                                UPDATE registro_excavacion_topografia SET
                                                    tramo = %s, id_monumento = %s, no_arqueologo = %s, punto_georeferencia = %s,
                                                    codigo = %s, id_topografo = %s, no_bolsa = %s, procedencia = %s, contexto_excavacion = %s,
                                                    tipo_excavacion = %s, coordenada_x = %s, coordenada_y = %s, capa = %s, material = %s,
                                                    meteria_prima = %s, asociacion = %s, descripcion_punto = %s, descripcion_estrato = %s,
                                                    fecha_registro = %s, foto_1 = %s, foto_2 = %s, foto_3 = %s, foto_4 = %s,
                                                    n = %s, e = %s, z = %s, codigo_topo = %s
                                                WHERE codigo_poligono = %s AND clave_registro = %s AND clave_excavacion = %s
                                            """
                                            valores_update_topografia = tuple(valores_base + [n, e, z, codigo] + [codigo_poligono, clave_registro, clave_excavacion])
                                            cursor.execute(sql_update_topografia, valores_update_topografia)
                                        else:
                                            sql_insert_topografia = """
                                                INSERT INTO registro_excavacion_topografia(
                                                    codigo_poligono, clave_registro, clave_excavacion, tramo, id_monumento, no_arqueologo,
                                                    punto_georeferencia, codigo, id_topografo, no_bolsa, procedencia, contexto_excavacion,
                                                    tipo_excavacion, coordenada_x, coordenada_y, capa, material, meteria_prima, asociacion,
                                                    descripcion_punto, descripcion_estrato, fecha_registro, foto_1, foto_2, foto_3, foto_4,
                                                    n, e, z, codigo_topo)
                                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                                        %s, %s, %s, %s)
                                            """
                                            valores_topografia = tuple(
                                                [codigo_poligono, clave_registro, clave_excavacion] +
                                                valores_base +
                                                [n, e, z, codigo]
                                            )
                                            if cursor.execute(sql_insert_topografia, valores_topografia):
                                                print(f"✅ Topografía insertada para {clave_excavacion}")
                                            else:
                                                print(f"⚠️ Error al insertar topografía para {clave_excavacion}")
                                    else:
                                        print(f"⚠️ No se encontraron datos topográficos para {clave_excavacion}")
                                except Exception as e:
                                    print(f"⚠️ Error al insertar topografía para {clave_excavacion}: {str(e)}")

                        except Exception as e:
                            print(f"❌ Error procesando {file_path}: {str(e)}")

            connection_mysql.commit()
            print("✅ Registros insertados correctamente.")

        except Exception as e:
            print(f"❌ Error general: {str(e)}")

        finally:
            if cursor is not None:
                cursor.close()
            if connection_mysql is not None:
                connection_mysql.close()
            if connection_postgres is not None:
                connection_postgres.close()
