import streamlit as st
import mysql.connector as mc
from openai import OpenAI
import tempfile
import pandas as pd

st.set_page_config(page_title="Resumo Inteligente de Agenda", layout="wide")

# ============================================================
# BANCO
# ============================================================
DB_CONFIG = {
    "host": "172.31.20.168",
    "user": "consulta",
    "password": "wH@xQd",
    "database": "fast",
}

def get_connection():
    return mc.connect(**DB_CONFIG)

# ============================================================
# OPENAI
# ============================================================
client = OpenAI(api_key="SUA_API_KEY_AQUI")

# ============================================================
# BUSCAR PROJETOS ERP
# ============================================================
def buscar_projetos():

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    sql = """
    SELECT idProjeto,nome 
    FROM projeto 
    WHERE idProduto = 1 
    AND idProdutoCronograma = 38 
    AND nome LIKE '%ERP%'
    """

    cursor.execute(sql)
    dados = cursor.fetchall()

    conn.close()
    return dados

# ============================================================
# BUSCAR ATIVIDADES COM JOIN
# ============================================================
def buscar_atividades(idProjeto):

    conn = get_connection()

    sql = """
    SELECT 
        p.nome,
        ap.datAtividade,
        ap.atividade
    FROM projeto p
    INNER JOIN atividadesprojeto ap 
        ON ap.idProjeto = p.idProjeto
    WHERE 
        p.idProduto = 1 
        AND p.idProdutoCronograma = 38 
        AND p.nome LIKE '%ERP%'
        AND p.idProjeto = %s
    ORDER BY 
        ap.datAtividade DESC
    """

    df = pd.read_sql(sql, conn, params=(idProjeto,))
    conn.close()
    return df

# ============================================================
# INSERT
# ============================================================
def inserir_atividade(idProjeto, resumo):

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    INSERT INTO atividadesprojeto
    (
        idProjeto,
        datAtividade,
        atividade
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

# ============================================================
# TRANSCRIÇÃO
# ============================================================
def transcrever_audio(caminho):

    with open(caminho, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=f
        )

    return transcript.text

# ============================================================
# RESUMO IA
# ============================================================
def gerar_resumo(transcricao):

    prompt = f"""
Você está analisando a transcrição de uma agenda técnica de implantação de ERP.

Leia e retorne um resumo estruturado no seguinte formato:

📅 Agenda Técnica

Resumo Geral:
Momento do Cliente:
Situação Comercial:
Expectativas:
Riscos:
Próximos Passos:

Transcrição:
{transcricao}
"""

    resposta = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role":"system","content":"Especialista em implantação ERP"},
            {"role":"user","content":prompt}
        ]
    )

    return resposta.choices[0].message.content

# ============================================================
# TELA
# ============================================================

st.title("📅 IA - Resumo Automático de Agenda ERP")

projetos = buscar_projetos()
mapa = {p["nome"]: p["idProjeto"] for p in projetos}

projeto_nome = st.selectbox(
    "Selecione o Projeto ERP",
    mapa.keys()
)

idProjeto = mapa[projeto_nome]

arquivo = st.file_uploader(
    "Envie o Áudio (.mp3/.wav) ou Transcrição (.txt)",
    type=["mp3","wav","txt"]
)

if arquivo:

    if st.button("🧠 Gerar Resumo"):

        with st.spinner("Processando reunião com IA..."):

            if arquivo.type == "text/plain":
                transcricao = arquivo.read().decode("utf-8")

            else:
                temp = tempfile.NamedTemporaryFile(delete=False)
                temp.write(arquivo.read())
                caminho = temp.name
                transcricao = transcrever_audio(caminho)

            resumo = gerar_resumo(transcricao)

        st.subheader("📌 Resumo Gerado")
        st.text_area("", resumo, height=350)

        if st.button("📥 Publicar no Feed do Projeto"):
            inserir_atividade(idProjeto, resumo)
            st.success("Resumo publicado!")

# ============================================================
# HISTÓRICO DAS ATIVIDADES (JOIN)
# ============================================================

st.subheader("📜 Histórico de Atividades do Projeto")

df = buscar_atividades(idProjeto)

st.dataframe(df, use_container_width=True)
