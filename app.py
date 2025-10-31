import streamlit as st
import pandas as pd
import plotly.express as px
import mysql.connector as mc
from mysql.connector import Error
import unicodedata

# -------------------------
# CONFIGURAÇÃO DA PÁGINA
# -------------------------
st.set_page_config(page_title="Dashboard Consultores", page_icon="📈", layout="wide")

# -------------------------
# CSS PERSONALIZADO
# -------------------------
st.markdown("""
    <style>
    /* ======= LAYOUT GERAL ======= */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #f7f9fc 0%, #eef2f7 100%);
        color: #2c3e50;
        font-family: 'Segoe UI', Roboto, sans-serif;
    }
    [data-testid="stSidebar"] {
        background: #1f2d3d;
        color: #fff;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #fff;
    }
    .stSelectbox label, .stMultiselect label {
        font-weight: 600 !important;
        color: #fff !important;
    }
    /* ======= TÍTULOS ======= */
    h1, h2, h3 {
        color: #1a202c;
        font-weight: 700;
    }
    /* ======= CARDS DE MÉTRICAS ======= */
    .metric-card {
        background: white;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        padding: 20px;
        text-align: center;
        transition: all 0.2s ease-in-out;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 16px rgba(0,0,0,0.1);
    }
    .metric-label {
        font-size: 0.9rem;
        color: #6b7280;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1f2937;
    }
    /* ======= DATAFRAME ======= */
    .stDataFrame {
        border-radius: 12px !important;
        overflow: hidden !important;
        background-color: white;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    /* ======= BOTÃO ======= */
    div.stButton > button {
        background: linear-gradient(90deg, #2563eb, #3b82f6);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        transition: 0.3s;
    }
    div.stButton > button:hover {
        background: linear-gradient(90deg, #1d4ed8, #2563eb);
        transform: scale(1.02);
    }
    </style>
""", unsafe_allow_html=True)

# -------------------------
# TÍTULO PRINCIPAL
# -------------------------
st.markdown("<h1 style='text-align:center; color:#2563eb;'>📊 Mapa de Consultores</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#6b7280;'>Monitoramento das consultorias, certificações e demandas</p>", unsafe_allow_html=True)
st.markdown("---")

# -------------------------
# CONFIGURAÇÕES DO BANCO
# -------------------------
hostname = 'fastproject.senior.com.br'
user = 'fast'
password = 'kK3F6737IER3d-sf*'
database = 'fast'

# -------------------------
# FUNÇÕES AUXILIARES
# -------------------------
def limpar_texto(x):
    if isinstance(x, str):
        x = unicodedata.normalize('NFKD', x)
        return x.strip()
    return x

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

# -------------------------
# CONSULTAS AO BANCO
# -------------------------
@st.cache_data
def carregar_dados_banco():
    conn = create_connection()
    if not conn:
        return pd.DataFrame()
    try:
        query = """
        SELECT 
            nome AS `Nome`,
            email,
            empresa AS `Empresa`,
            CASE 
                WHEN cep = 0 THEN 'Sim'
                WHEN cep = 1 THEN 'Não Recomendado'
                WHEN cep = 2 THEN 'Sem Histórico'
                ELSE 'N/D'
            END AS `Alocacao`,
            CASE 
                WHEN endereco = 0 THEN 'Consultor Importante'
                WHEN endereco = 1 THEN 'Melhorar Postura ou Conhecimento'
                WHEN endereco = 2 THEN 'Possível Descredenciamento'
                ELSE 'N/D'
            END AS `Perfil`,
            idProduto AS `produtoERP`
        FROM usuario
        WHERE usuario.idGrupoUsuario IN (11, 27, 4)
          AND idProduto = 1
          AND ativo = 1
          AND email LIKE '%@consultorseniorsistemas.com.br%';
        """
        df = pd.read_sql(query, conn)
        conn.close()
        df = df.applymap(limpar_texto)
        return df
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")
        return pd.DataFrame()

@st.cache_data
def buscar_certificacoes_com_trilhas():
    conn = create_connection()
    if not conn:
        return pd.DataFrame()
    try:
        query = """
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
                    ELSE trilha
                END AS trilha_normalizada
            FROM certificacoesusuarios
            WHERE aprovadoTrilha = 'Sim'
              AND codigoTrilha IN (354,355,356,357,360,361,362,363,364,365,366,368,369,370,372,390,395)
        ) AS sub
        GROUP BY email
        ORDER BY ultima_importacao DESC;
        """
        df_cert = pd.read_sql(query, conn)
        conn.close()
        df_cert = df_cert.applymap(limpar_texto)
        return df_cert
    except Exception as e:
        st.error(f"Erro ao buscar certificações: {e}")
        return pd.DataFrame()

@st.cache_data
def buscar_demandas():
    conn = create_connection()
    if not conn:
        return pd.DataFrame()
    try:
        query = """
        SELECT 
            responsavel AS email,
            COUNT(*) AS Total_Demandas
        FROM demandausuario
        WHERE selecionado = 1
        GROUP BY responsavel;
        """
        df_demandas = pd.read_sql(query, conn)
        conn.close()
        df_demandas["email"] = df_demandas["email"].apply(limpar_texto)
        return df_demandas
    except Exception as e:
        st.error(f"Erro ao buscar demandas: {e}")
        return pd.DataFrame()

# -------------------------
# CARREGAMENTO DOS DADOS
# -------------------------
with st.spinner("🔄 Carregando dados..."):
    df = carregar_dados_banco()
    df_cert = buscar_certificacoes_com_trilhas()
    df_demandas = buscar_demandas()

# -------------------------
# MERGE DOS DADOS
# -------------------------
if not df_cert.empty and "email" in df.columns:
    df = df.merge(df_cert, on="email", how="left")
    df["trilhas_aprovadas"] = df["trilhas_aprovadas"].fillna(0).astype(int)
    df["nome_trilhas"] = df["nome_trilhas"].fillna("Nenhuma trilha")
    df = df.rename(columns={"trilhas_aprovadas": "Certificações"})
if not df_demandas.empty and "email" in df.columns:
    df = df.merge(df_demandas, on="email", how="left")
    df["Total_Demandas"] = df["Total_Demandas"].fillna(0).astype(int)

# -------------------------
# SIDEBAR DE FILTROS
# -------------------------
st.sidebar.header("🎯 Filtros")
empresas = sorted(df["Empresa"].dropna().unique())
consultores = sorted(df["Nome"].dropna().unique())
trilhas = sorted(df["nome_trilhas"].dropna().str.split(", ").explode().unique())
alocacoes = sorted(df["Alocacao"].dropna().unique())

empresas_sel = st.sidebar.multiselect(
    "🏢 Consultorias",
    empresas,
    default=[],
    placeholder="Selecione uma ou mais consultorias..."
)

consultores_sel = st.sidebar.multiselect(
    "👤 Consultores",    
    consultores,
    default=[],
    placeholder="Selecione um ou mais consultores..."
)

trilhas_sel = st.sidebar.multiselect(
    "📘 Trilhas", 
    trilhas,
    default=[],
    placeholder="Selecione uma ou mais Trilhas..."
)

aloc_sel = st.sidebar.multiselect(
    "🧩 Alocação", 
    alocacoes,
    default=[],
    placeholder="Selecione um ou mais Perfis..."
)

# -------------------------
# FILTROS APLICADOS
# -------------------------
df_f = df.copy()
if empresas_sel:
    df_f = df_f[df_f["Empresa"].isin(empresas_sel)]
if consultores_sel:
    df_f = df_f[df_f["Nome"].isin(consultores_sel)]
if trilhas_sel:
    df_f = df_f[df_f["nome_trilhas"].apply(lambda x: any(t in str(x) for t in trilhas_sel))]
if aloc_sel:
    df_f = df_f[df_f["Alocacao"].isin(aloc_sel)]

if df_f.empty:
    st.info("🔎 Nenhum resultado encontrado para os filtros selecionados.")
    st.stop()

# -------------------------
# DASHBOARD
# -------------------------
tab1, tab2 = st.tabs(["📊 Consultores", "📚 Trilhas"])

with tab1:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"<div class='metric-card'><div class='metric-label'>Consultores</div><div class='metric-value'>{len(df_f)}</div></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='metric-card'><div class='metric-label'>Certificações Totais</div><div class='metric-value'>{df_f['Certificações'].sum()}</div></div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='metric-card'><div class='metric-label'>Demandas Totais</div><div class='metric-value'>{df_f['Total_Demandas'].sum()}</div></div>", unsafe_allow_html=True)

    st.markdown("### 📋 Detalhamento")
    st.dataframe(df_f[["Nome", "Empresa", "Perfil", "Alocacao", "Certificações", "Total_Demandas"]], use_container_width=True, height=420)

    st.markdown("---")
    st.subheader("📊 Distribuição por Perfil")
    if not df_f.empty:
        df_perf = df_f.groupby("Perfil").size().reset_index(name="Quantidade")
        col1, col2 = st.columns(2)
        with col1:
            fig = px.pie(df_perf, names="Perfil", values="Quantidade", hole=0.4, color_discrete_sequence=px.colors.qualitative.Vivid)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig2 = px.bar(df_perf, x="Perfil", y="Quantidade", text_auto=True, color="Perfil", color_discrete_sequence=px.colors.qualitative.Vivid)
            st.plotly_chart(fig2, use_container_width=True)

with tab2:
    st.subheader("🏅 Trilhas por Consultor")
    st.dataframe(df_f[["Nome", "email", "nome_trilhas", "Certificações"]], use_container_width=True, height=420)

# -------------------------
# BOTÃO ATUALIZAR
# -------------------------
st.markdown("---")
if st.button("🔄 Atualizar dados"):
    st.cache_data.clear()
    st.rerun()
