import pandas as pd
from datetime import date,datetime
from sqlalchemy import create_engine
from urllib.parse import quote
import streamlit as st
import plotly.express as px
import matplotlib.pyplot as plt
import numpy as np
import os
import mysql.connector as mc
import pytz

USER_DB_FAST = os.environ.get('USER_DB_FAST')
PASS_DB_FAST = os.environ.get('PASS_DB_FAST')

hostname = '172.31.20.168'
# user = USER_DB_FAST
# password = PASS_DB_FAST
user = 'consulta'
password = 'wH@xQd'

database = 'fast'

connection = mc.connect(
    host=hostname,
    database=database,
    user=user,
    password=password
)

st.set_page_config(layout="wide")
st.header('Farejador Base ERP')

# --- Função para exibir métricas clicáveis ---
def metric_card_clickable(title, value, icon, var_name):
    button_label = f"{icon} {title}: {value}"
    clicked = st.button(button_label, key=f"btn_{var_name}")
    return clicked


# --- Função para buscar o log da variável ---
def get_log_variavel(var_name, ids_str):
    query_log = f"""
        SELECT 
            data,
            valor,
            descricaoVariavel,
            codemp,
            codfil,
            titulo
        FROM dadosimplantacao
        WHERE variavel = '{var_name}'
        AND idProjeto IN ({ids_str})
        ORDER BY data DESC
    """
    return pd.read_sql(query_log, con=connection)



# --- Consulta para pegar id e nome do projeto ---
query_ids = """
    SELECT DISTINCT d.idProjeto, p.nome AS nomeProjeto
    FROM dadosimplantacao d
    JOIN projeto p ON d.idProjeto = p.idProjeto
"""
ids_df = pd.read_sql(query_ids, con=connection)

# Criar dicionário {nome: id} para usar no filtro
opcoes_projetos = dict(zip(ids_df['nomeProjeto'], ids_df['idProjeto']))


#Buscar quantidade de empresas e filiais#
query_empresas = """SELECT 
    COUNT(DISTINCT codemp) AS qtd_empresas_codemp,
    COUNT(DISTINCT codfil) AS qtd_empresas_codfil
    FROM dadosimplantacao
    WHERE idProjeto IN ({ids_str})
"""



# --- Filtro multiselect na sidebar com nomes de projeto ---
projetos_nomes_selecionados = st.sidebar.multiselect(
    "Selecione os Projetos",
    options=opcoes_projetos.keys(),
    default=[]
)

# Adicione isso ao início do seu script para um estilo global melhor
st.markdown("""
    <style>
    .metric-box {
        border: 1px solid #e6e6e6;
        border-radius: 16px;
        padding: 14px;
        background-color: #fdfdfd;
        text-align: center;
        box-shadow: 2px 2px 12px rgba(0,0,0,0.04);
        height: 110px;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        animation: fadeIn 0.5s ease-in-out;
    }

    .metric-box:hover {
        transform: scale(1.03);
        box-shadow: 4px 4px 14px rgba(0,0,0,0.08);
    }

    .metric-title {
        font-size: 20px;
        color: #333;
        margin-bottom: 6px;
    }

    .metric-value {
        font-size: 18px;
        font-weight: bold;
        color: #111;
    }

    @keyframes fadeIn {
        0% { opacity: 0; transform: translateY(10px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    </style>
""", unsafe_allow_html=True)

def metric_card(title, value, icon=""):
    st.markdown(
        f"""
        <div class="metric-box">
            <div class="metric-title">{icon} {title}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Pegar os ids correspondentes aos nomes selecionados
projetos_selecionados = [opcoes_projetos[nome] for nome in projetos_nomes_selecionados]

# --- Consulta principal, filtrando pelo(s) projeto(s) selecionado(s) ---
if projetos_selecionados:
    # Transformar a lista em string para uso no IN da query
    ids_str = ', '.join(map(str, projetos_selecionados))

    query = f"""
        SELECT 
    d.idProjeto,
    p.nome AS NomeProjeto,
    d.titulo,
    d.variavel,
    d.valor,
    d.data,
    d.cnpj,
    d.descricaoVariavel,
    d.codemp,
    d.codfil,
    MAX(d.titulo) AS MaxTitulo,
    SUM(d.valor) AS SomaValor,
    MAX(d.data) AS UltimaData,
    MAX(d.cnpj) AS MaxCNPJ,
    MAX(d.descricaoVariavel) AS MaxDescricaoVariavel
    FROM dadosimplantacao d
    JOIN projeto p ON d.idProjeto = p.idProjeto
    WHERE d.idProjeto IN ({ids_str})
    GROUP BY 
    d.idProjeto,
    p.nome,
    d.variavel
    """
    df = pd.read_sql(query, con=connection)

    # Renomear colunas conforme seu padrão
    df = df.rename(columns={
        'idProjeto': 'ID Projeto',
        'titulo': 'Nome',
        'variavel': 'Processos',
        'valor': 'Valores',
        'data': 'Data',
        'cnpj': 'CNPJ',
        'descricaoVariavel': 'Rotina',
        'codemp': 'Empresa',
        'codfil': 'Filial',
        'NomeProjeto': 'Projeto'
    })

    # Conversões e limpeza dos dados
    df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
    df = df.dropna(subset=['Data'])
    df['mes_ano'] = df['Data'].dt.to_period('M').astype(str)
    df['Valores_num'] = pd.to_numeric(df['Valores'], errors='coerce')
    
        # Filtrar apenas as variáveis que queremos
    variaveis_interesse = [
        "qtde-clientes",
        "qtde-fornecedores",
        "qtde-transportadora",
        "qtde-representantes",
        "qtde-produtos",
        "qtde-tabela-preco",
        "qtde-usuarios-sgu",
        "sup-ordem-compra", 
        "sup-contrato-compra",
        "sup-nota-entrada",                                     
        "sup-nota-rec-eletronico",
        "mer-pedidos",
        "mer-qtde-contrato-venda", 
        "mer-total-notas",
        "fin-titulos-cr",
        "fin-titulos-cp"
    ]

    df_filtrado = df[df["Processos"].isin(variaveis_interesse)]
    

    # Pegar o último valor (mais recente) para cada variável
    ultimos_valores = (
        df_filtrado.sort_values(by="Data", ascending=False)
        .drop_duplicates(subset="Processos", keep="first")
    )

    # Usar os valores numéricos
    metricas = dict(zip(ultimos_valores["Processos"], ultimos_valores["Valores"]))
    
    
    st.markdown("---")
    st.markdown("<h4 style='text-align: center;'>📊 Informações Gerais</h4>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1: metric_card("Empresas", df['Empresa'].nunique(), "🏢")
    with col2: metric_card("Filiais", df['Filial'].nunique(), "🏬")
    
    st.markdown("---")
    st.markdown("<h4 style='text-align: center;'>📆 Período dos Dados</h4>", unsafe_allow_html=True)
    col4, col5, col6,col7 = st.columns(4)
    with col4: metric_card("Período (início)", df['Data'].min().strftime('%d/%m/%Y'), "🗓️")
    with col5: metric_card("Período (fim)", df['Data'].max().strftime('%d/%m/%Y'), "🗓️")
    with col6: metric_card("Dias entre os Cadastros", df['Data'].dt.date.nunique(), "📅")
    with col7: metric_card("Total de Registros", len(df), "📊")
    
    st.markdown("---")
    st.markdown("<h4 style='text-align: center;'>👥 Cadastro Gerais</h4>", unsafe_allow_html=True)
    col9, col10, col11,col12,col13,col14,col15 = st.columns(7)
    with col9: metric_card("Clientes", metricas.get("qtde-clientes", 0), "👥")
    with col10: metric_card("Fornecedores", metricas.get("qtde-fornecedores", 0), "🏪")
    with col11: metric_card("Transportadoras", metricas.get("qtde-transportadora", 0), "🚚")
    with col12: metric_card("Representantes", metricas.get("qtde-representantes", 0), "🧑‍💼")   
    with col13: metric_card("Produtos", metricas.get("qtde-produtos", 0), "📦")
    with col14: metric_card("Tabela de Preço", metricas.get("qtde-tabela-preco", 0), "💰")
    with col15: metric_card("Usuários SGU", metricas.get("qtde-usuarios-sgu", 0), "🧑‍💻")
    
    st.markdown("---")
    st.markdown("<h4 style='text-align: center;'>📦 Suprimentos</h4>", unsafe_allow_html=True)
    col17,col18,col19, col20 = st.columns(4)
    with col17: metric_card("Ordem de Compra", metricas.get("sup-ordem-compra", 0), "🛒")
    with col18: metric_card("Contrato de Compra", metricas.get("sup-contrato-compra", 0), "📜")
    with col19: metric_card("Notas Fiscais de Entrada", metricas.get("sup-nota-entrada", 0), "🧾")
    with col20: metric_card("Notas Rec. Eletrônico", metricas.get("sup-nota-rec-eletronico", 0), "📥")
    
       
    st.markdown("---")
    st.markdown("<h4 style='text-align: center;'>📦 Suprimentos</h4>", unsafe_allow_html=True)
    col17, col18, col19, col20 = st.columns(4)

    with col17:
        if metric_card_clickable("Ordem de Compra", metricas.get("sup-ordem-compra", 0), "🛒", "sup-ordem-compra"):
            df_log = get_log_variavel("sup-ordem-compra", ids_str)
        with st.modal("Histórico — Ordem de Compra"):
            st.dataframe(df_log)

    with col18:
        if metric_card_clickable("Contrato de Compra", metricas.get("sup-contrato-compra", 0), "📜", "sup-contrato-compra"):
                df_log = get_log_variavel("sup-contrato-compra", ids_str)
        with st.modal("Histórico — Contrato de Compra"):
            st.dataframe(df_log)

    with col19:
        if metric_card_clickable("Notas de Entrada", metricas.get("sup-nota-entrada", 0), "🧾", "sup-nota-entrada"):
            df_log = get_log_variavel("sup-nota-entrada", ids_str)
        with st.modal("Histórico — NF Entrada"):
            st.dataframe(df_log)

    with col20:
        if metric_card_clickable("Notas Rec. Eletrônico", metricas.get("sup-nota-rec-eletronico", 0), "📥", "sup-nota-rec-eletronico"):
            df_log = get_log_variavel("sup-nota-rec-eletronico", ids_str)
        with st.modal("Histórico — Rec. Eletrônico"):
            st.dataframe(df_log)

    
    
    st.markdown("---")
    st.markdown("<h4 style='text-align: center;'>💼 Financeiro</h4>", unsafe_allow_html=True)
    col24, col25 = st.columns(2)
    with col24: metric_card("Contas a Receber - Titulos", metricas.get("fin-titulos-cr", 0), "💰")
    with col25: metric_card("Contas a Pagar - Titulos", metricas.get("fin-titulos-cp", 0), "💸")
    
    
    st.markdown("---")  

    # Converter a coluna de data para datetime
    df["Data"] = pd.to_datetime(df["Data"])


    # =================== Gráfico de evolução por mês ===================
    evolucao_cadastros = df.groupby('mes_ano').size().reset_index(name='Quantidade')
    fig = px.line(
        evolucao_cadastros,
        x='mes_ano',
        y='Quantidade',
        title='📈 Evolução de Cadastros por Mês',
        markers=True
    )
    fig.update_layout(xaxis_title='Mês/Ano', yaxis_title='Nº de Registros')
    with st.expander("📊 Evolução de Cadastros por Mês", expanded=True):
        st.plotly_chart(fig, use_container_width=True)
    
        # Mostrar mensagem informativa
    st.write(f"Mostrando dados para {len(projetos_selecionados)} projeto(s) selecionado(s).")

    # Ordenar DataFrame pela maior data primeiro
    df = df.sort_values(by="Data", ascending=False)

    # Tabela dentro de um expander
    with st.expander("🔍 Visualizar todos os registros filtrados", expanded=True):
        st.dataframe(df)
    

else:
    st.warning("Selecione pelo menos um projeto para visualizar os dados.")