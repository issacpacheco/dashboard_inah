import psycopg2
import MySQLdb

class Conexion:
    # Conexion a PostgreSQL remota
    def conectar_postgres():
        try:
            con_postgres = psycopg2.connect(
                host="65.99.252.77",
                port="5432",
                user="topografia",
                password="topografia",
                database="tren_maya",
                # dbname="tren_carga"
            )
            return con_postgres
        except psycopg2.Error as e:
            print("Error al conectar a PostgreSQL:", e)
            return None
        
    # Conexion a MySQL local
    def conectar_mysql():
        try:
            con_mysql = MySQLdb.connect(
                host="localhost",
                user="root",
                password="",
                database="tren_carga"
            )
            return con_mysql
        except MySQLdb.Error as e:
            print("Error al conectar a MySQL:", e)
            return None