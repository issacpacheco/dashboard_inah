from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, send_file, abort, send_from_directory, jsonify
from werkzeug.utils import safe_join
from flask_autoindex import AutoIndex
from pyngrok import ngrok  # Agregado
from script.descargar_drive import DriveBackup
from script.registros_excavaciones import ExportExcel
from script.exportar_geopackage import ExportarGeoPackage
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
    return redirect(url_for('panel'))

@app.route('/panel')
def panel():
    response = make_response(render_template('panel.html'))
    return add_no_cache_headers(response)

@app.context_processor
def cargar_menu():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT nombre FROM config_drive")
        resultados = cur.fetchall()
        cur.close()
        conn.close()
        if resultados:
            menu = [{'nombre': item[0]} for item in resultados]
        else:
            menu = None
        return dict(menu=menu)
    except Exception as e:
        print("Error al cargar el menú global:", e)
        return dict(menu=None)


@app.route('/config_drive/config_drive', methods=['GET', 'POST'])
def config_drive():
    # Obtener configuración del usuario
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM config_drive")
    config_drive = cur.fetchall()
    cur.close()


    arreglo_config_drive = []
    if config_drive:
        for drive in config_drive:
            arreglo_config_drive.append({
                'id': drive[0],
                'nombre' : drive[1],
                'folder_id': drive[2],
                'ruta_json': drive[3],
                'ruta_local': drive[4],
                'ruta_zip': drive[5]
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
                return make_response(render_template('respaldo.html', output_text=backup_instance.messages))
            except Exception as e:
                flash(f"Error al iniciar el respaldo: {str(e)}")
                return redirect(url_for('backup'))

        elif accion == 'actualizar_registros':
            codigo = request.form.get('codigo_poligono')
            print(">> Código recibido:", codigo)  # Temporal para depuración

            if not codigo:
                flash("No se proporcionó el código de polígono.", "danger")
                return redirect(url_for('backup'))

            try:
                exportador = ExportExcel(codigo)
                total = exportador.procesar_codigo_poligono()
                flash(f"Exportación completada. Se actualizaron {total} registros.", "success")
            except Exception as e:
                flash(f"Error al actualizar registros: {str(e)}", "danger")

            return redirect(url_for('backup'))

        else:
            flash("Acción no reconocida.", "error")
            return redirect(url_for('backup'))

    # GET: Cargar configuraciones
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM config_drive")
    config_drive = cur.fetchall()
    cur.close()
    conn.close()

    arreglo_config_drive = [{
        'id': drive[0],
        'nombre': drive[1],
        'folder_id': drive[2],
        'ruta_json': drive[3],
        'ruta_local': drive[4],
        'ruta_zip': drive[5]
    } for drive in config_drive]

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
        # return redirect(url_for('logout'))

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

    name_folder = config[1]
    base_path = config[4]
    folder_id_config = config[3]

    req_path = req_path.strip('/')
    abs_path = os.path.join(base_path, req_path)

    if not os.path.exists(abs_path):
        return abort(404)

    if os.path.isfile(abs_path):
        return send_file(abs_path, as_attachment=True)

    raw_files = os.listdir(abs_path)
    raw_files.sort()

    files = []
    for filename in raw_files:
        full_path = os.path.join(abs_path, filename)
        if os.path.isdir(full_path):
            files.append({
                'name': filename,
                'is_dir': True,
                'count': len(os.listdir(full_path)),
                'size': None
            })
        else:
            files.append({
                'name': filename,
                'is_dir': False,
                'count': None,
                'size': round(os.path.getsize(full_path) / 1024, 2)  # Tamaño en KB
            })

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

@app.route('/poligonos/<string:nombre_poligono>/', defaults={'id_monumento': None}, methods=['GET', 'POST'])
@app.route('/poligonos/<string:nombre_poligono>/<string:id_monumento>', methods=['GET', 'POST'])
def poligonos(nombre_poligono, id_monumento):
    arreglo_poligonos = []
    
    conn = get_db_connection()
    cur = conn.cursor()

    if id_monumento:
        print(f"Consultando con polígono: {nombre_poligono} e id_monumento: {id_monumento}")
        cur.execute("""
            SELECT clave_excavacion, tramo, id_monumento, no_arqueologo, 
                    punto_georeferencia, codigo, id_topografo, no_bolsa, 
                    procedencia, contexto_excavacion, tipo_excavacion, 
                    coordenada_x, coordenada_y, capa, material, meteria_prima, 
                    asociacion, descripcion_punto, descripcion_estrato, fecha_registro, 
                    foto_1, foto_2, foto_3, foto_4, n, e, z, codigo_topo  
            FROM registro_excavacion_topografia 
            WHERE id_monumento = %s AND codigo_poligono = %s
        """, (id_monumento, nombre_poligono))

        monumentos = cur.fetchall()
        cur.close()
        conn.close()

        #pasamos toda la informacion de la tabla sin agragarlo a un arreglo
        arreglo_monumentos = []
        for monumento in monumentos:
            arreglo_monumentos.append({
                'clave_excavacion': monumento[0],
                'tramo': monumento[1],
                'id_monumento': monumento[2],
                'no_arqueologo': monumento[3],
                'punto_georeferencia': monumento[4],
                'codigo': monumento[5], 
                'id_topografo': monumento[6],
                'no_bolsa': monumento[7],
                'procedencia': monumento[8],
                'contexto_excavacion': monumento[9],
                'tipo_excavacion': monumento[10],
                'coordenada_x': monumento[11],
                'coordenada_y': monumento[12],
                'capa': monumento[13],
                'material': monumento[14],
                'meteria_prima': monumento[15],
                'asociacion': monumento[16],
                'descripcion_punto': monumento[17],
                'descripcion_estrato': monumento[18],
                'fecha_registro': monumento[19],
                'foto_1': monumento[20],
                'foto_2': monumento[21],
                'foto_3': monumento[22],
                'foto_4': monumento[23],
                'n': monumento[24],
                'e': monumento[25],
                'z': monumento[26],
                'codigo_topo': monumento[27]
            })
        return render_template(
            'poligonos.html',
            monumentos=arreglo_monumentos,
            nombre_poligono=nombre_poligono,
            id_monumento=id_monumento or ""
        )
    else:
        print(f"Consultando solo por polígono: {nombre_poligono}")
        cur.execute("""
            SELECT id, codigo_poligono, tramo, id_monumento, no_arqueologo FROM registro_excavacion_topografia 
            WHERE codigo_poligono = %s GROUP BY clave_registro
        """, (nombre_poligono,))

        poligonos = cur.fetchall()
        cur.close()
        conn.close()

        for poligono in poligonos:
            arreglo_poligonos.append({
                'id': poligono[0],
                'codigo_poligono': poligono[1],
                'tramo': poligono[2],
                'clave_registro': poligono[3],
                'no_arqueologo': poligono[4]
            })

        return render_template(
            'poligonos.html',
            poligonos=arreglo_poligonos,
            nombre_poligono=nombre_poligono,
            id_monumento=id_monumento or ""
        )
@app.route('/descargar_gpkg')
def descargar_gpkg():
    nombre_poligono = request.args.get('nombre_poligono')
    id_monumento = request.args.get('id_monumento')
    if not nombre_poligono:
        return "Nombre de polígono no proporcionado", 400

    try:
        exportador = ExportarGeoPackage(nombre_poligono, id_monumento)
        exportador.exportar_geopackage()
        filepath = f"registro_excavacion_topografia_{nombre_poligono}_{id_monumento}.gpkg"
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        return str(e), 500
@app.route('/importar_bitacora_estatica', methods=['POST'])
def importar_bitacora_estatica():
    importar_excel_bitacora()
    return redirect(url_for('backup'))

def importar_excel_bitacora():
    """Importa datos desde un archivo Excel ubicado en backup/BITACORA hacia la tabla 'bitacora' en la base de datos."""
    import pandas as pd

    try:
        # Cargar el archivo Excel
        df = pd.read_excel('backup/BITACORA/Bitacora de enlaces.xlsx', engine='openpyxl')

        # Omitir la primera fila (asumiendo que es encabezado o fila no deseada)
        df = df.iloc[1:]

        # Conectar a la base de datos
        conn = get_db_connection()
        cur = conn.cursor()

        for index, row in df.iterrows():
            # Saltar filas donde la primera columna esté vacía
            if pd.isna(row.iloc[0]) or str(row.iloc[0]).strip() == "":
                print(f"Fila {index} omitida porque la primera columna está vacía.")
                continue

            # Validar que haya al menos 41 columnas
            if len(row) < 41:
                print(f"Fila {index} tiene menos de 41 columnas, se omite.")
                continue

            id_monumento = row.iloc[1]  # columna 1 = id_monumento
            enlace_carpeta = row.iloc[2]  # columna 2 = enlace_carpeta

            valores_base = []
            for i in range(3, 43):  # Tomar desde la columna 3 hasta la 42 (total 40 columnas)
                val = row.iloc[i]
                if pd.isna(val):
                    valores_base.append("")
                else:
                    try:
                        int_val = int(float(val))
                        valores_base.append("{:03d}".format(int_val))
                    except (ValueError, TypeError):
                        valores_base.append(str(val))

            if len(valores_base) != 40:
                print(f"Fila {index} con id_monumento {id_monumento} tiene longitud incorrecta.")
                continue

            # Verificar si ya existe
            cur.execute("SELECT COUNT(*) FROM bitacora WHERE id_monumento = %s", (id_monumento,))
            count = cur.fetchone()[0]

            if count > 0:
                print(f"Registro con id_monumento {id_monumento} ya existe, se actualizará.")
                valores_update = [id_monumento, enlace_carpeta] + valores_base + [id_monumento]
                cur.execute("""
                    UPDATE bitacora
                    SET id_monumento = %s, enlace_carpeta = %s, id_mon_sup_intervenidos = %s, id_mon_sup_no_intervenidos = %s,
                        no_intervenidas = %s, total_superiores_intervenidas = %s, poligono = %s, area = %s,
                        tipo_intervencion = %s, id_arqueologo = %s, nombre_arqueologo = %s, formulario = %s,
                        tabla_registro = %s, fotos_costado = %s, fotos_perfil_capa = %s, fotos_codigo = %s,
                        dibujo_planta = %s, dibujo_corte = %s, porcentaje_entregable = %s,
                        observaciones_arqueologia = %s, id_arquitecto = %s, dxf = %s, pdf = %s, observaciones = %s,
                        registro_unico = %s, costados_finales = %s, vuelo_inicial = %s, vuelo_intermedio = %s,
                        vuelo_final = %s, observaciones_fotogrametria = %s, id_enlace = %s, ortofoto_rvt = %s,
                        ortofoto_cost = %s, ortofoto_orto = %s, dpp = %s, dpl = %s, reti = %s, puntos_topograficos = %s,
                        join_enlace = %s, porcentaje_avance = %s, carpeta_completa = %s, observaciones_enlace = %s
                    WHERE id_monumento = %s
                """, tuple(valores_update))
            else:
                try:
                    valores_insert = [id_monumento, enlace_carpeta] + valores_base
                    cur.execute("""
                        INSERT INTO bitacora(
                            id_monumento, enlace_carpeta,
                            id_mon_sup_intervenidos, id_mon_sup_no_intervenidos, no_intervenidas,
                            total_superiores_intervenidas, poligono, area, tipo_intervencion,
                            id_arqueologo, nombre_arqueologo, formulario, tabla_registro, fotos_costado,
                            fotos_perfil_capa, fotos_codigo, dibujo_planta, dibujo_corte, porcentaje_entregable,
                            observaciones_arqueologia, id_arquitecto, dxf, pdf, observaciones,
                            registro_unico, costados_finales, vuelo_inicial, vuelo_intermedio,
                            vuelo_final, observaciones_fotogrametria, id_enlace, ortofoto_rvt,
                            ortofoto_cost, ortofoto_orto, dpp, dpl, reti, puntos_topograficos,
                            join_enlace, porcentaje_avance, carpeta_completa, observaciones_enlace
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, tuple(valores_insert))
                except Exception as e:
                    print(f"Error al insertar los datos: {e}")
                    continue

        conn.commit()
        cur.close()
        conn.close()
        print("Datos importados correctamente desde el archivo Excel.")
        flash("Datos importados correctamente desde el archivo Excel.", "success")
        return None

    except FileNotFoundError:
        print("El archivo Excel no se encontró en la ruta especificada.")
        flash("El archivo Excel no se encontró en la ruta especificada.", "error")
        return None

    except pd.errors.EmptyDataError:
        print("El archivo Excel está vacío.")
        flash("El archivo Excel está vacío.", "error")
        return None

    except pd.errors.ParserError:
        print("Error al analizar el archivo Excel. Asegúrate de que esté en un formato válido.")
        flash("Error al analizar el archivo Excel. Asegúrate de que esté en un formato válido.", "error")
        return None

    except Exception as e:
        print(f"Error al importar el archivo Excel: {e}")
        flash(f"Error al importar el archivo Excel: {e}", "error")
        return None



if __name__ == '__main__':
    # Abre un túnel público en el puerto 5000
    # public_url = ngrok.connect(5000)
    # print(f"\n* App pública disponible en: {public_url}\n")

    # # Inicia la app Flask normalmente
    # app.run(port=5000)
    app.run(debug=True)
