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
from mysql.connector import Error
import os

# ============================================
# CONFIGURAÇÕES INICIAIS
# ============================================
st.set_page_config(page_title="Documento de Repasse - Foundation", page_icon="📄", layout="centered")

st.title("📄 Documento de Repasse - Foundation")
st.write("Preencha as informações abaixo para gerar automaticamente o documento de repasse em formato PDF.")

# ============================================
# CONEXÃO COM O BANCO DE DADOS
# ============================================
hostname = 'fastproject.senior.com.br'
user = os.environ.get('USER_DB_FAST', 'consulta')
password = os.environ.get('PASS_DB_FAST', 'wH@xQd')
database = 'fast'

@st.cache_data(ttl=300)
def carregar_dados():
    """Busca projetos e usuários do banco de dados e armazena em cache por 5 minutos."""
    try:
        connection = mc.connect(
            host=hostname,
            database=database,
            user=user,
            password=password,
            auth_plugin='mysql_native_password'
        )
        cursor = connection.cursor(dictionary=True)

        # Consulta de projetos
        cursor.execute("""
            SELECT idProjeto, nome
            FROM projeto
            WHERE statusprojeto = 0 
              AND idProduto = 1 
              AND idProdutoCronograma IN (38, 89)
            ORDER BY idProjeto ASC
        """)
        projetos = [row["nome"] for row in cursor.fetchall()]

        # Consulta de usuários
        cursor.execute("""
            SELECT idusuario, nome
            FROM usuario
            WHERE ativo = 1
              AND idProduto IN (1,2)
              AND tipoAcesso IN (2,4,1)
            ORDER BY nome ASC
        """)
        usuarios = [row["nome"] for row in cursor.fetchall()]

        cursor.close()
        connection.close()
        return projetos, usuarios
    except Error as e:
        st.error(f"❌ Erro ao buscar dados: {e}")
        return [], []

projetos, usuarios = carregar_dados()

# ============================================
# CAMPOS DE SELEÇÃO
# ============================================
col1, col2 = st.columns(2)

with col1:
    if projetos:
        projeto = st.selectbox(
            "Selecione o Projeto",
            options=projetos,
            index=None,
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
    gerente = st.selectbox(
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
    resposta = st.text_area(
        f"Resposta - {pergunta}",
        placeholder="Digite sua resposta aqui...",
        key=f"resposta_{i}"
    )
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
    if not projeto or not consultor or not gerente:
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
            f"Gerente de Projeto: {gerente}",
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
            resposta_formatada = resposta.replace("\n", "<br/>") if resposta else "—"
            story.append(Paragraph(resposta_formatada, answer_style))

            if imagens:
                for img in imagens:
                    image_data = BytesIO(img.read())
                    pil_img = PILImage.open(image_data)

                    # Redimensiona mantendo proporção
                    max_width = 400
                    max_height = 250
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
