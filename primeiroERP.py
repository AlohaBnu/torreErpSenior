import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
from urllib.parse import quote
import streamlit as st
import plotly.express as px
import numpy as np
import mysql.connector as mc
from mysql.connector import Error

# ----------------------------
# CONFIGURAÇÕES DO BANCO
# ----------------------------
hostname = '172.31.20.168'
user = 'consulta'
password = 'wH@xQd'
database = 'fast'

# ----------------------------
# FUNÇÃO DE CONEXÃO
# ----------------------------
def create_connection():
    try:
        connection = mc.connect(
            host=hostname,
            database=database,
            user=user,
            password=password,
            auth_plugin='mysql_native_password'
        )
        if connection.is_connected():
            return connection
    except Error as e:
        st.error(f"Erro ao conectar ao MySQL: {e}")
        return None

# ----------------------------
# EXECUTANDO O SELECT
# ----------------------------
def carregar_dados():
    query = """
        SELECT
            p.idProjeto,
            p.nome AS NomeProjeto,
            u.nome as NomeGP,
            c.datMarcacao as DataAtividade,
            p.datInicio as CadastroFast
        FROM projeto p
        JOIN atividadesmetodologiaprojeto c 
            ON p.idprojeto = c.idprojeto
        JOIN usuario u 
            ON c.idUsuario = u.idUsuario
        WHERE c.idAtividadesMetodologia IN (521, 1)
          AND c.tipo = 0
          AND p.nome LIKE '%ERP%'
          AND c.datMarcacao LIKE '%2025%'
        ORDER BY c.datMarcacao DESC;
    """

    conn = create_connection()
    if conn is None:
        return None
    
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()

    colunas = [desc[0] for desc in cursor.description]
    df = pd.DataFrame(rows, columns=colunas)

    cursor.close()
    conn.close()
    
    return df

# ----------------------------
# STREAMLIT
# ----------------------------
st.title("Dashboard – Primeiros Contatos em Projetos ERP")

df = carregar_dados()

if df is None or df.empty:
    st.warning("Nenhum dado retornado.")
else:
    st.subheader("Resultado do SELECT")

    # Converter datas
    df['DataAtividade'] = pd.to_datetime(df['DataAtividade'])
    df['CadastroFast'] = pd.to_datetime(df['CadastroFast'])

    # Calcular diferença entre datas
    df['DiferençaDias'] = (df['DataAtividade'] - df['CadastroFast']).dt.days

    # Mostrar tabela com cálculo
    st.dataframe(df)

    # Métricas
    st.metric("Total de Projetos", df['idProjeto'].nunique())

    tempo_medio = df['DiferençaDias'].mean()
    st.metric(
        "Tempo Médio entre Cadastro FAST e Primeira Marcação",
        f"{tempo_medio:.1f} dias"
    )

    # Gráfico
    fig = px.bar(
        df,
        x='DataAtividade',
        y='idProjeto',
        color='NomeGP',
        title="Quantidade de registros por data"
    )

    st.plotly_chart(fig)
