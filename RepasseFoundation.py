import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
import os

# Carrega chave
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="Portal de Inteligência do Projeto", layout="wide")

st.title("🤖 Inteligência de Agenda Técnica")
st.markdown("Envie a transcrição da reunião")

# ---------------- RESUMO ----------------

uploaded_file = st.file_uploader("Envie o .txt da reunião", type=["txt"])
texto_manual = st.text_area("OU cole aqui", height=300)

def gerar_resumo(transcricao):

    prompt = f"""
Você é especialista em implantação de ERP.

Leia a transcrição abaixo e gere:

- Resumo Executivo
- Principais Assuntos Tratados
- Pontos de Negócio
- Oportunidades de Venda
- Expectativas do Cliente
- Riscos
- Próximos Passos

Transcrição:
{transcricao}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":"Você analisa reuniões de projetos ERP"},
            {"role":"user","content":prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content

if st.button("🚀 Gerar Resumo"):

    if uploaded_file:
        transcricao = uploaded_file.read().decode("utf-8")
    else:
        transcricao = texto_manual

    if transcricao.strip() == "":
        st.warning("Envie ou cole uma transcrição")
    else:
        with st.spinner("Analisando reunião..."):
            resumo = gerar_resumo(transcricao)

        st.success("Resumo gerado!")
        st.markdown(resumo)

# ---------------- CHATBOT ----------------

st.markdown("""
<style>
.chat-box {
    position: fixed;
    bottom: 90px;
    right: 20px;
    width: 350px;
    height: 450px;
    background: white;
    border-radius: 10px;
    padding: 10px;
    box-shadow: 0px 0px 10px gray;
    z-index: 9999;
}
</style>
""", unsafe_allow_html=True)

if "chat_open" not in st.session_state:
    st.session_state.chat_open = False

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if st.button("💬 Chat do Projeto"):
    st.session_state.chat_open = not st.session_state.chat_open

def perguntar(pergunta):

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":"Você responde perguntas sobre reuniões de implantação ERP"},
            {"role":"user","content":pergunta}
        ],
        temperature=0.3
    )

    return response.choices[0].message.content

if st.session_state.chat_open:

    st.markdown('<div class="chat-box">', unsafe_allow_html=True)

    pergunta = st.text_input("Pergunte sobre o projeto")

    if st.button("Enviar Pergunta"):

        resposta = perguntar(pergunta)

        st.session_state.chat_history.append(("Você", pergunta))
        st.session_state.chat_history.append(("IA", resposta))

    for autor, msg in st.session_state.chat_history:
        st.write(f"**{autor}:** {msg}")

    st.markdown('</div>', unsafe_allow_html=True)