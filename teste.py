import streamlit as st
import mysql.connector
import pandas as pd

# ---------------------------
# Conexão com o banco
# ---------------------------
def get_connection():
    return mysql.connector.connect(
        host="SEU_HOST",
        user="SEU_USUARIO",
        password="SUA_SENHA",
        database="SEU_BANCO"
    )

# ---------------------------
# Consulta SQL
# ---------------------------
SQL = """
SELECT 
    email,
    COUNT(DISTINCT trilha_normalizada) AS trilhas_aprovadas,
    GROUP_CONCAT(DISTINCT trilha_normalizada ORDER BY trilha_normalizada SEPARATOR ', ') AS nome_trilhas,
    MAX(dataImportacao) AS ultima_importacao
FROM (
    SELECT 
        email,
        dataImportacao,
        CASE
            WHEN trilha LIKE '%Distribui%' THEN 'Distribuicao'
            WHEN trilha LIKE '%Or%ament%' THEN 'Orcamentaria e Projetos'
            WHEN trilha LIKE '%Patrim%' THEN 'Patrimonio'
            WHEN trilha LIKE '%Ch%o%' THEN 'Chao de Fabrica'
            WHEN trilha LIKE '%Faturamento e Outras Sa%das%' THEN 'Faturamento e Outras Saidas'
            WHEN trilha LIKE '%Agroneg%cio%' THEN 'Agronegocio'
            WHEN trilha LIKE '%ERP XT Reforma Tribut%ria%' THEN 'Reforma Tributaria'
            ELSE trilha
        END AS trilha_normalizada
    FROM certificacoesusuarios
    WHERE aprovadoTrilha = 'Sim'
      AND codigoTrilha IN (
           354,355,356,357,360,361,362,363,364,365,
           366,368,369,370,372,390,395,'ERPXTRT'
      )
) AS sub
GROUP BY email
ORDER BY ultima_importacao DESC;
"""

# ---------------------------
# Executar consulta
# ---------------------------
conn = get_connection()
df = pd.read_sql(SQL, conn)
conn.close()

# ---------------------------
# Sidebar – Filtros
# ---------------------------
st.sidebar.header("Filtros")

usuarios = sorted(df["email"].unique())
filtro_usuario = st.sidebar.multiselect("Usuário", usuarios)

df_filtrado = df.copy()

if filtro_usuario:
    df_filtrado = df_filtrado[df_filtrado["email"].isin(filtro_usuario)]

# ---------------------------
# Exibição no Streamlit
# ---------------------------
st.title("📈 Evolução de Certificações por Usuário")

st.dataframe(df_filtrado, use_container_width=True)

# ---------------------------
# Métricas (opcional)
# ---------------------------
col1, col2 = st.columns(2)
col1.metric("Total de Usuários", len(df_filtrado))
col2.metric("Total de Trilhas Concluídas", df_filtrado["trilhas_aprovadas"].sum())
