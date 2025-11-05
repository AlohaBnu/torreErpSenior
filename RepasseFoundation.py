
import streamlit as st
from datetime import date
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, KeepTogether
from reportlab.lib import colors
from PIL import Image as PILImage
import mysql.connector as mc
import pytz
from mysql.connector import Error
import os
import pandas as pd
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt
import pyarrow as pa

# ============================================
# CONFIGURAÇÕES INICIAIS
# ============================================
st.set_page_config(page_title="Documento de Repasse - Foundation", page_icon="📄", layout="centered")

st.title("📄 Documento de Repasse - Foundation")
st.write("Preencha as informações abaixo para gerar automaticamente o documento de repasse em formato PDF.")

USER_DB_FAST = os.environ.get('USER_DB_FAST')
PASS_DB_FAST = os.environ.get('PASS_DB_FAST')

# ============================================
# CONEXÃO COM O BANCO DE DADOS
# ============================================
hostname = 'fastproject.senior.com.br'
user = 'consulta'
password = 'wH@xQd'
database = 'fast'

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
        st.error(f"❌ Erro ao conectar ao MySQL: {e}")
        return None

connection = create_connection()

# ============================================
# BUSCA DE PROJETOS NO BANCO
# ============================================
projetos = []
usuarios = []

if connection:
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Consulta de projetos
        query_projetos = """
            SELECT idProjeto, nome
            FROM projeto
            WHERE statusprojeto = 0 
              AND idProduto = 1 
              AND idProdutoCronograma IN (38, 89)
            ORDER BY idProjeto ASC
        """
        cursor.execute(query_projetos)
        resultados = cursor.fetchall()
        projetos = [f"{row['nome']}" for row in resultados]

        # Consulta de usuários
        query_usuarios = """
            SELECT idusuario,nome 
            FROM usuario 
            WHERE ativo = 1
              AND idProduto in(1,2)
              AND tipoAcesso IN (2,4,1) 
            ORDER BY nome ASC
        """
        cursor.execute(query_usuarios)
        resultados = cursor.fetchall()
        usuarios = [f"{row['nome']}" for row in resultados]

        cursor.close()

    except Error as e:
        st.error(f"Erro ao buscar dados: {e}")
    finally:
        connection.close()
        

# ============================================
# CAMPO DE SELEÇÃO DE PROJETO
# ============================================
col1, col2 = st.columns(2)

with col1:
    if projetos and len(projetos) > 0:
        projeto = st.selectbox(
            "Selecione o Projeto",
            options=projetos,
            index=None,  # não seleciona nada por padrão
            placeholder="Selecione o Projeto"
        )
    else:
        projeto = st.text_input(
            "Nome do Projeto",
            placeholder="Ex: Selecione o Projeto (não encontrado no banco)"
        )

with col2:
    consultor = st.text_input(
        "Responsável",
        placeholder="Ex: Nome do responsável"
    )


col3, col4, col5 = st.columns(3)
with col3:
    if usuarios:
        usuarios = st.selectbox(
        "Selecione o Gerente de Projetos",
        options=usuarios,
        index=None,
        placeholder="Nome do responsável"
    )
              
with col4:
    data_repass = st.date_input("Data do Repasse", value=date.today())
with col5:
    data_repassFoundation = st.date_input("Apresentação Foundation", value=date.today())

st.markdown("---")


# ============================================
# PERGUNTAS FIXAS
# ============================================
st.subheader("Atividades Realizadas e Evidências")

perguntas = [
    "1. Dados de acesso utilizados?",    
    "2. Quantidade de Empresas duplicadas?",
    "3. Quantidade de Filiais duplicadas",
    "4. Empresas que serão realizadas o Rollout",
    "5. Usuários Cadastrados no SGU",
    "6. Cadastro dos Processos Agendados",
    "7. Cadastro de Contas Internas (Banco/Agencia/Conta)",
    "8. Notas Emitidas",
    "9. Configuração de emails (Recebimento/Envio)",
    "10. Recebimento de Notas eDocs",
    "11. Plataforma (Analytics/BOT)",
    "12. Participantes da Agenda de Apresentação",
    "13. Observações",
]

respostas = []
todas_imagens = []

for i, pergunta in enumerate(perguntas):
    st.markdown(f"### {pergunta}")
    resposta = st.text_area(f"Resposta - {pergunta}", placeholder="Digite sua resposta aqui...", key=f"resposta_{i}")
    imagens = st.file_uploader(
        f"Anexos (você pode selecionar várias imagens) - {pergunta}",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key=f"imagens_{i}"
    )
    respostas.append(resposta)
    todas_imagens.append(imagens)
    st.markdown("---")

# ============================================
# GERAÇÃO DO DOCUMENTO PDF
# ============================================
if st.button("Gerar Documento PDF"):
    if not projeto or not consultor:
        st.warning("Por favor, preencha todos os campos antes de gerar o documento.")
    else:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=60,
            bottomMargin=40
        )
        styles = getSampleStyleSheet()

        # Estilos personalizados
        title_style = ParagraphStyle(
            name="TitleStyle", fontSize=18, leading=22,
            alignment=TA_CENTER, spaceAfter=20,
            textColor=colors.HexColor("#1a3d7c")
        )
        header_style = ParagraphStyle(
            name="HeaderStyle", fontSize=12, leading=15,
            spaceAfter=10, textColor=colors.HexColor("#07500a")
        )
        question_style = ParagraphStyle(
            name="QuestionStyle", fontSize=11, leading=14,
            textColor=colors.HexColor("#1a3d7c"), spaceAfter=4
        )
        answer_style = ParagraphStyle(
            name="AnswerStyle", fontSize=10, leading=14,
            alignment=TA_JUSTIFY, textColor=colors.black,
            leftIndent=15, spaceAfter=10
        )
        note_style = ParagraphStyle(
            name="NoteStyle", fontSize=11, leading=16,
            alignment=TA_JUSTIFY, textColor=colors.black
        )
        italic_style = ParagraphStyle(
            name="ItalicStyle", fontSize=9, leading=12,
            alignment=TA_CENTER, textColor=colors.grey, italic=True
        )

        story = []

        # Cabeçalho
        story.append(Paragraph("Documento de Repasse - Foundation", title_style))
        story.append(Spacer(1, 12))

        info = [
            f"Projeto: {projeto}",
            f"Consultor Responsável: {consultor}",
            f"Gerente de Projeto: {usuarios}",
            f"Data do Repasse: {data_repass.strftime('%d/%m/%Y')}",
            f"Apresentação Foundation: {data_repassFoundation.strftime('%d/%m/%Y')}",
        ]
        for item in info:
            story.append(Paragraph(item, header_style))
        story.append(Spacer(1, 20))

        story.append(Paragraph("Atividades Realizadas", title_style))
        story.append(Spacer(1, 11))

        # Adiciona perguntas, respostas e imagens
        for pergunta, resposta, imagens in zip(perguntas, respostas, todas_imagens):
            story.append(Paragraph(pergunta, question_style))
            story.append(Paragraph(resposta if resposta else "—", answer_style))
            
           # Garante que quebras de linha sejam renderizadas no PDF
            resposta_formatada = resposta.replace("\n", "<br/>") if resposta else "—"
            story.append(Paragraph(resposta_formatada, answer_style))

            if imagens:
                for img in imagens:
                    image_data = BytesIO(img.read())
                    pil_img = PILImage.open(image_data)

                    # Define tamanho máximo
                    max_width = 400
                    max_height = 250

                    # Mantém proporção
                    ratio = min(max_width / pil_img.width, max_height / pil_img.height)
                    new_width = int(pil_img.width * ratio)
                    new_height = int(pil_img.height * ratio)

                    image_data.seek(0)
                    reportlab_image = Image(image_data, width=new_width, height=new_height)
                    story.append(reportlab_image)
                    story.append(Spacer(1, 8))

            story.append(Spacer(1, 10))

        # Texto final
        texto = (
            "Todas as atividades do Foundation estão contempladas dentro da DEAP.<br/>"
            "O Foundation garante a configuração inicial.<br/>"
            "Neste momento não está parametrizado com o negócio do cliente."
        )

        story.append(KeepTogether([
            Paragraph("Observação Importante", header_style),
            Paragraph(texto, note_style),
            Spacer(1, 10),
            Paragraph("Documento gerado automaticamente via Foundation Dashboard.", italic_style)
        ]))

        # Gera PDF
        doc.build(story)
        buffer.seek(0)

        nome_arquivo = f"Repasse_{projeto.replace(' ', '_')}_{data_repass}.pdf"

        st.success("✅ Documento PDF gerado com sucesso!")
        st.download_button(
            label="📥 Baixar PDF",
            data=buffer,
            file_name=nome_arquivo,
            mime="application/pdf"
        )
