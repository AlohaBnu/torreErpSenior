from asyncio import events
from streamlit.errors import StreamlitAPIException
from streamlit_calendar import calendar as streamlit_calendar
from datetime import date, datetime, time, timedelta
from pages.bd.conexao import select
from typing import Any
import hashlib
import colorsys
import re
import pandas as pd
import plotly.express as px
import pandas as pd
import unicodedata
import streamlit as st

st.set_page_config(
    layout="wide",
    page_title="Relatório de Atividades",
    initial_sidebar_state="expanded"
)

st.title("📊 Relatório de Atividades do Projeto")

# ============================
# FILTROS
# ============================

col1, col2, col3 = st.columns(3)

with col1:
    data_inicio = st.date_input("Data Inicial", value=date.today())

with col2:
    data_fim = st.date_input("Data Final", value=date.today())

with col3:
    id_projeto = st.text_input("ID do Projeto")

# ============================
# BOTÃO DE BUSCA
# ============================

if st.button("🔎 Buscar Dados"):

    if not id_projeto.strip():
        st.error("Informe o ID do Projeto.")
        st.stop()

    data_inicio_dt = datetime.combine(data_inicio, time(0, 0, 0))
    data_fim_dt = datetime.combine(data_fim, time(23, 59, 59))

    query = """
        SELECT
            c.datMarcacao,
            u.nome AS usuario_nome,
            p.idProjeto,
            m.cronograma,
            p.nome AS projeto_nome,
            m.texto AS mensagem_texto,
            (
                SELECT a.atividade
                FROM fast.agenda a
                WHERE a.idProjeto = %s
                  AND a.datInicio >= %s
                  AND a.datFim <= %s
                LIMIT 1
            ) AS Atividade,
            (
                SELECT a.link
                FROM fast.agenda a
                WHERE a.idProjeto = %s
                  AND a.datInicio >= %s
                  AND a.datFim <= %s
                LIMIT 1
            ) AS link,
            (
                SELECT a.atividade
                FROM atividadesprojeto a
                WHERE a.idProjeto = p.idProjeto
                  AND a.idMensagem = m.idMensagem
                  AND a.atividade LIKE '%Outros%'
                LIMIT 1
            ) AS Outros,
            DATEDIFF(CURDATE(), p.datInicio) AS dias_ativos,
            m.idProdutoCronograma,
            (
                (SELECT COUNT(*)
                 FROM mensagem m_sub
                 WHERE m_sub.idProdutoCronograma = m.idProdutoCronograma
                   AND m_sub.quantidadeNivel = 3)
                -
                (SELECT COUNT(*)
                 FROM configuracaocronograma c_sub
                 WHERE c_sub.idProjeto = p.idProjeto)
            ) AS Atividades_a_Concluir
        FROM configuracaocronograma c
        JOIN usuario u ON c.idUsuario = u.idUsuario
        JOIN projeto p ON c.idProjeto = p.idProjeto
        JOIN mensagem m ON c.idMensagem = m.idMensagem
        WHERE c.datMarcacao BETWEEN %s AND %s
          AND p.idProduto = '31'
          AND p.idProjeto = %s
        ORDER BY u.nome, c.datMarcacao
    """

    parametros = (
        id_projeto, data_inicio_dt, data_fim_dt,
        id_projeto, data_inicio_dt, data_fim_dt,
        data_inicio_dt, data_fim_dt,
        id_projeto
    )

    try:
        dados = select(query, parametros)

        if dados:
            st.success(f"{len(dados)} registros encontrados.")
            st.dataframe(dados, use_container_width=True)
        else:
            st.warning("Nenhum registro encontrado para os filtros informados.")

    except Exception as e:
        st.error(f"Erro ao executar consulta: {e}")
