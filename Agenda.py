import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def conectar():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# 🔽 SELECT DOS PROJETOS ERP
def buscar_projetos():
    conn = conectar()
    cursor = conn.cursor(dictionary=True)

    sql = """
    select idProjeto,nome 
    from projeto 
    where idProduto = 1 
    and idProdutoCronograma = 38 
    and nome like '%ERP%'
    """

    cursor.execute(sql)
    dados = cursor.fetchall()

    conn.close()
    return dados

# 🔽 INSERT NA ATIVIDADE DO PROJETO
def inserir_feed(idProjeto, resumo):
    conn = conectar()
    cursor = conn.cursor()

    sql = """
    INSERT INTO atividadesprojeto
    (
        idProjeto,
        datAtividade,
        desAtividade
    )
    VALUES
    (
        %s,
        NOW(),
        %s
    )
    """

    cursor.execute(sql, (idProjeto, resumo))
    conn.commit()
    conn.close()
