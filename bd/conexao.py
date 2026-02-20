import mysql.connector
from mysql.connector import Error
from pages.bd.conexao import select


# Configurações do MySQL
db_config = {
    "host": "172.31.20.168",
    "port": 3306,
    "database": "fast",
    "user": "fast",
    "password": "kK3F6737IER3d-sf*"
}

# Criar conexão com MySQL
def get_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except Error as e:
        print("Erro ao conectar ao MySQL:", e)
        return None

# SELECT com parâmetros
def select(query, params=None):
    conn = get_connection()
    if conn is None:
        return []

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params)
        results = cursor.fetchall()
        return results
    except Error as e:
        print("Erro no SELECT:", e)
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# INSERT / UPDATE / DELETE
def execute(query, params=None):
    conn = get_connection()
    if conn is None:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return True
    except Error as e:
        print("Erro no execute:", e)
        return False
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
