from asyncio import events
import streamlit as st
from streamlit.errors import StreamlitAPIException
from streamlit_calendar import calendar as streamlit_calendar
from datetime import date, datetime, time, timedelta
from typing import Any
import hashlib
import colorsys
import re
import unicodedata

st.set_page_config(
    layout="wide",
    page_title="Dashboard",
    initial_sidebar_state="expanded"
)

HORA_INICIO_EXPEDIENTE = time(8, 0)
HORA_FIM_EXPEDIENTE = time(18, 0)  # limite máximo contado

HORA_ALMOCO_INICIO = time(12, 0)
HORA_ALMOCO_FIM = time(13, 0)

def carregar_log(idAgenda):
    try:
        sql = f"""
            SELECT 
                usuario,
                acao,
                detalhe,
                DATE_FORMAT(datahora, '%d/%m/%Y %H:%i:%s') as datahora
            FROM agenda2_logs
            WHERE idagenda = {int(idAgenda)}
            ORDER BY datahora DESC
        """
        logs = select(sql)

        if not logs:
            return ""

        html = ""
        for log in logs:
            html += f"""
            <div style="margin-bottom:8px;">
                <b>👤 Usuário:</b> {log['usuario']}<br>
                <b>📝 Detalhe:</b> {log['detalhe']}<br>
                <b>🕒 Data:</b> {log['datahora']}
            </div>
            <hr style="margin:6px 0;">
            """
        return html
    except Exception as e:
        return f"<span style='color:red;'>Erro ao carregar logs: {e}</span>"
    
def registrar_log(idagenda, acao, detalhe=""):
    nome_usuario = st.session_state.get("nome_usuario")
    try:
        sql = """
        INSERT INTO agenda2_logs (idagenda, usuario, acao, detalhe, datahora)
        VALUES (%s, %s, %s, %s, NOW())
        """
        execute(sql, (idagenda, nome_usuario, acao, detalhe))
    except Exception as e:
        st.error(f"Erro ao registrar log: {e}")


def calcular_horas_com_almoco(dat_inicio: datetime, dat_fim: datetime) -> float:
    """
    Regra:
    - Dias úteis (seg-sex)
    - Conta somente das 08:00 às 18:00
    - Desconta almoço (12:00 às 13:00)
    - Máximo de 9h por dia
    - Se período for multi-dia, replica o horário em cada dia
    """

    if dat_fim <= dat_inicio:
        return 0.0

    total_segundos = 0
    dia_atual = dat_inicio.date()
    ultimo_dia = dat_fim.date()

    hora_inicio_original = dat_inicio.time()
    hora_fim_original = dat_fim.time()

    while dia_atual <= ultimo_dia:

        # apenas dias úteis
        if dia_atual.weekday() < 5:

            # se for o primeiro dia ou último dia, usa as horas reais
            # se for dia intermediário, usa o horário original informado
            if dia_atual == dat_inicio.date():
                inicio = datetime.combine(dia_atual, hora_inicio_original)
                fim = datetime.combine(dia_atual, hora_fim_original)
            else:
                inicio = datetime.combine(dia_atual, hora_inicio_original)
                fim = datetime.combine(dia_atual, hora_fim_original)

            # aplica limite de expediente
            inicio_expediente = datetime.combine(dia_atual, time(8, 0))
            fim_expediente = datetime.combine(dia_atual, time(18, 0))

            inicio = max(inicio, inicio_expediente)
            fim = min(fim, fim_expediente)

            if inicio < fim:
                segundos_dia = (fim - inicio).total_seconds()

                # almoço
                almoco_inicio = datetime.combine(dia_atual, time(12, 0))
                almoco_fim = datetime.combine(dia_atual, time(13, 0))

                inicio_overlap = max(inicio, almoco_inicio)
                fim_overlap = min(fim, almoco_fim)

                if inicio_overlap < fim_overlap:
                    segundos_dia -= (fim_overlap - inicio_overlap).total_seconds()

                # máximo de 9h por dia
                total_segundos += min(segundos_dia, 9 * 3600)

        dia_atual += timedelta(days=1)

    return round(total_segundos / 3600, 2)


# ----------------------
# UTIL: limpar texto vindo do SQL (remove emojis / setas / controles)
# ----------------------
def limpar_sql_texto(txt: str) -> str:
    """
    Limpa texto vindo do banco:
      - remove emojis e pictogramas (vários ranges unicode)
      - remove caracteres de controle invisíveis
      - mantém acentos e pontuação
      - normaliza espaços
    """
    if not txt:
        return ""
    try:
        # garante string
        if not isinstance(txt, str):
            txt = str(txt)
    except Exception:
        txt = ""

    # Normalização Unicode básica (NFC)
    txt = unicodedata.normalize("NFC", txt)

    # Regex para remover emojis / dingbats / pictograms (várias faixas comuns)
    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001F5FF"  # símbolos e pictogramas
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F680-\U0001F6FF"  # transportes e símbolos
        "\U0001F1E6-\U0001F1FF"  # bandeiras
        "\U00002700-\U000027BF"  # dingbats
        "\U00002600-\U000026FF"  # símbolos diversos
        "\U00002B00-\U00002BFF"  # setas, outros símbolos
        "\U00002300-\U000023FF"  # misc technical
        "\U0000FE0F"             # variation selector (remove)
        "]+",
        flags=re.UNICODE
    )

    txt = emoji_pattern.sub("", txt)

    # Remove caracteres de controle invisíveis (0x00-0x1F, 0x7F)
    txt = re.sub(r"[\x00-\x1F\x7F]", "", txt)

    # Remove caracteres isolados de formatação Unicode (ex.: OBJECT REPLACEMENT, etc.)
    # (isso já é parcialmente coberto acima, mas mantemos como precaução)
    txt = re.sub(r"[\uFFFD]", "", txt)

    # Substitui múltiplos espaços / quebras por um único espaço ou por quebra adequada
    # Preserva quebras de linha (se necessário). Aqui vamos transformar múltiplas quebras em uma.
    txt = re.sub(r"\r\n?", "\n", txt)           # normaliza quebra de linha
    txt = re.sub(r"\n{2,}", "\n\n", txt)        # limita múltiplas quebras
    txt = re.sub(r"[ \t]{2,}", " ", txt)        # múltiplos espaços -> 1 espaço
    # Trim
    txt = txt.strip()
    return txt

 
# ----------------------
# UTIL: gerar cor a partir do nome da empresa (HSL suave convertido para HEX)
# ----------------------
def empresa_to_color(nome: str):
    if not nome:
        nome = "default"
    # hue baseado no hash do nome
    h = int(hashlib.md5(nome.encode("utf-8")).hexdigest(), 16) % 360
    # ---------- COR 1: fundo (clara) ----------
    s1 = 65
    l1 = 90
    r1, g1, b1 = colorsys.hls_to_rgb(h / 360.0, l1 / 100.0, s1 / 100.0)
    bg_color = "#{:02x}{:02x}{:02x}".format(int(r1*255), int(g1*255), int(b1*255))

    # ---------- COR 2: borda (mais forte) ----------
    s2 = min(100, s1 + 20)    # aumenta saturação
    l2 = max(0, l1 - 30)      # diminui luminosidade → mais escuro
    r2, g2, b2 = colorsys.hls_to_rgb(h / 360.0, l2 / 100.0, s2 / 100.0)
    border_color = "#{:02x}{:02x}{:02x}".format(int(r2*255), int(g2*255), int(b2*255))

    return bg_color, border_color


def to_date_ddmmaa(value):
    """Converte valor vindo do SQL e devolve tuple (date, string dd/mm/aaaa)."""
    # 1) Converte para date
    if isinstance(value, date) and not isinstance(value, datetime):
        d = value
    elif isinstance(value, datetime):
        d = value.date()
    elif isinstance(value, str):
        try:
            d = datetime.fromisoformat(value.replace("Z","")).date()
        except:
            try:
                d = datetime.strptime(value, "%Y-%m-%d").date()
            except:
                try:
                    d = datetime.strptime(value, "%d/%m/%Y").date()
                except:
                    d = date.today()
    else:
        d = date.today()

    # 2) Formato dd/mm/aaaa
    return d, d.strftime("%d/%m/%Y")

# -------------------------------
# BUSCAR DADOS (mantive sua query original) — agora com idDemanda e limpeza
# -------------------------------


def buscar_dados_api():
    query = """select
                a.idAgenda as idagenda,
                a.idUsuario as idUsuario,
                u.nome as usuario,
                DATE_FORMAT(a.datInicio, "%d/%m/%Y %H:%i") as inicio,
                DATE_FORMAT(a.datFim, "%d/%m/%Y %H:%i") as fim,
                a.datInicio as datInicio,
                a.datFim as datFim,
                a.atividade as atividade,
                a.obsAgenda as obsagenda,
                a.status as statusAgenda,
                u.idProduto as sistema,
                u.ativo as usuarioAtivo,
                u.tipoAcesso as tipoUsuario,
                a.datCadastro as datCadastro,
                u.modeloEquipe as modeloEquipe,
                u.cargo as cargo,
                a.nomeProjeto as nomeProjeto,
                a.idDemanda as idDemanda,
                d.conhecimento as modulos, 
                d.descricao as escopo,
                d.escopo as pacote,
                d.atendimento as atendimento,
                u2.nome as solicitante,
                d.previsaoFim as previsaoFim,
                DATE_FORMAT(previsaoInicio, '%d/%m/%Y') as previsaoInicio,
                DATE_FORMAT(previsaoFim, '%d/%m/%Y') as previsaoFim,
                d.horas as horas
            from agenda2 a
            left join usuario u on a.idUsuario = u.idUsuario
            left join demanda d on a.idDemanda = d.idDemanda
            left join usuario u2 on d.idUsuario = u2.idUsuario
            where a.status IN (1,2)
            """
    dados = select(query)
    if not dados:
        return None

    # Aplica limpeza nos campos textuais que costumam trazer caracteres "estranhos"
    campos_para_limpar = ['modulos', 'escopo', 'obsagenda', 'atividade', 'nomeProjeto', 'solicitante']
    for row in dados:
        for campo in campos_para_limpar:
            # alguns rows podem não ter a chave, então usamos get e só sobrescrevemos se existir
            if campo in row:
                row[campo] = limpar_sql_texto(row.get(campo, "") or "")
        # Também garante que idDemanda venha como string limpa (ou vazia)
        if 'idDemanda' in row:
            row['idDemanda'] = str(row.get('idDemanda')) if row.get('idDemanda') is not None else ""
    return dados

# -------------------------------
# MODAL: Exibir evento com opções Editar / Excluir (exibe idDemanda)
# -------------------------------
@st.dialog("Detalhes da Agenda", width="medium")
def abrirAgenda(agenda):
    st.markdown("""
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Agenda", "Logs"])

    with tab1:   
        color = "#D0FFF3"
        st.markdown(f"""
            <div style="border:solid 1px #000; padding:10px; color: #000; background-color: {color}">
            <div class="row"><div class="col"><h3>🏛️ Projeto: {agenda['extendedProps'].get('projeto', '')}</h3></div><div class="col"><h3>🧑‍💼 Reponsável: {agenda['extendedProps'].get('usuario', '')}</h3></div></div>
            <div style="border: 1px solid #ccc; padding:10px; margin-top:10px; margin-bottom:10px;">
            <small>📅 Agenda</small>
            <div class="row">
            <div class="col"><b>Início:</b> {agenda['extendedProps']['inicio']}</div>
            <div class="col"><b>Fim:</b> {agenda['extendedProps']['fim']}</div>
            </div>
            <div class="row"><div class="col"><b>Atividade:</b> {agenda['extendedProps'].get('atividade','')}</div>
            <div class="col"><b>Observação:</b> {agenda['extendedProps'].get('obs','')}</div></div>
            </div>
            <div style="border: 1px solid #ccc; padding:10px; margin-top:10px; margin-bottom:10px;">
            <small>✅ Demanda</small>
            <div class="row">
            <div class="col"><b>Nº Demanda:</b> {agenda['extendedProps'].get('idDemanda','')}</div>
            <div class="row">
            <div class="col"><b>Previsão Início:</b> {agenda['extendedProps'].get('previsaoInicio','')}</div>
            <div class="col"><b>Previsão Fim:</b> {agenda['extendedProps'].get('previsaoFim','')}</div>
            <div class="col"><b>Horas:</b> {agenda['extendedProps']['horas']}</div>
            </div>
            <div class="row">
            <div class="col"><b>Solicitante:</b> {agenda['extendedProps'].get('solicitante','')}</div>
            <div class="col"><b>Atendimento:</b> {agenda['extendedProps'].get('atendimento','')}</div>
            </div>
            <div class="row">
            <div class="col"><b>Conhecimento:</b> {agenda['extendedProps'].get('modulos','')}</div>
            </div>
            </div>
            </div>
        """, unsafe_allow_html=True)

        # botoes editar / excluir
        col1, col2 = st.columns(2, gap="small", vertical_alignment="bottom", width=260)

        with col1:
            if st.button("✏️ Editar"):
                st.session_state["abrir_modal"] = False
                st.session_state["abrir_modal_edicao"] = True
                st.session_state["editar_evento"] = agenda
                st.rerun()

        with col2:
            if st.button("❌Cancelar Agenda"):
                try:
                    idagenda = agenda.get("id") or agenda.get("extendedProps", {}).get("idAgenda")

                    if not idagenda:
                        st.error("ID da agenda não encontrado.")
                    else:
                        delete_query = "UPDATE agenda2 SET status = 2 WHERE idAgenda = %s"
                        execute(delete_query, (idagenda,))
                        registrar_log(idagenda, "Cancelamento de Agenda", detalhe="Agenda cancelada")

                    # 🔑 LIMPA ESTADOS ANTES DO RERUN
                    st.session_state["abrir_modal"] = False
                    st.session_state["evento_selecionado"] = None
                    st.rerun()

                except Exception as e:
                    st.error(f"Erro ao cancelar: {e}")

    with tab2:
        st.write("Aqui serão exibidos os logs de ações relacionadas a esta agenda.")
        
        logs_html = carregar_log(
            agenda.get("id") or agenda.get("extendedProps", {}).get("idAgenda")
        )

        st.markdown(
            f"""
            <div style='background:#eef; padding:10px; border-left:4px solid #446; border-radius:4px;'>
                {logs_html if logs_html else "📭 Nenhum log disponível."}
            </div>
            """,
            unsafe_allow_html=True
        )


        



# -------------------------------
# MODAL: Criar novo agendamento (usado também para edição)
# -------------------------------
def abrirNovoModal_edicao(agenda):
    """
    Abre modal de edição preenchida com dados do evento (agenda).
    A agenda vem no formato do eventClick do calendário.
    """
    # Extrai dados necessários
    ext = agenda.get("extendedProps", {})
    # tentamos obter o idAgenda do evento
    hoje_idagenda = agenda.get("id") or ext.get("idAgenda") or ext.get("idAgenda")
    # buscar dados atuais diretamente do banco para garantir consistência
    if hoje_idagenda:
        q = "SELECT * FROM agenda2 WHERE idAgenda = %s"
        rec = select(q, (hoje_idagenda,))
        if rec and len(rec) > 0:
            rec = rec[0]
            # converte datInicio datFim para datetime se necessário
            try:
                datInicio = rec['datInicio']
                datFim = rec['datFim']
            except Exception:
                datInicio = datetime.fromisoformat(rec['datInicio'])
                datFim = datetime.fromisoformat(rec['datFim'])
            abrirNovoModal(data_clicada=datInicio.date(), is_edit=True, existing=rec)
            return
    # fallback: tenta usar os dados do evento
    try:
        dt_start = datetime.fromisoformat(agenda['start'])
        abrirNovoModal(data_clicada=dt_start.date(), is_edit=True, existing=None, event_payload=agenda)
    except Exception:
        abrirNovoModal(data_clicada=None, is_edit=True, existing=None, event_payload=agenda)


def recarregar():
    st.session_state['abrir_modal'] = False


# VALIDAR HORAS DE AGENDA COM HORAS DA DEMANDA
def verificar_conflito(usuario_id, inicio, fim, ignore_id=0):
    sql = """
        SELECT idAgenda, datInicio, datFim, nomeProjeto
        FROM agenda2
        WHERE idUsuario = %s
          AND status <> 2
          AND (
                (datInicio <= %s AND datFim > %s)
                OR
                (datInicio < %s AND datFim > %s)
                OR
                (datInicio >= %s AND datFim <= %s)
              )
          AND idAgenda <> %s
    """
    return select(sql, (usuario_id, fim, inicio, fim, inicio, inicio, fim, ignore_id)) or []

# @st.dialog("Criar nova agenda", width="medium", on_dismiss=recarregar)
@st.dialog("Criar nova agenda", width="medium")
def abrirNovoModal(data_clicada=None, is_edit=False, existing=None, event_payload=None):
    """
    data_clicada: date
    is_edit: True se for edição
    existing: registro da agenda2 quando edição (dict) - opcional
    event_payload: dados do evento vindo do calendar quando não houver existing
    """

    query_projetos = """
        SELECT idProjeto, nome, idFilial, idUsuarioCadastro
        FROM projeto
        WHERE idProduto = 1
          AND statusprojeto = 0
        ORDER BY nome
    """
    projetos_lista = select(query_projetos) or []

    projeto_placeholder = -1
    projetos_opcoes = {projeto_placeholder: "Selecione um projeto"}
    projetos_opcoes.update({
        p['idProjeto']: p['nome'] for p in projetos_lista
    })

    # ---------- VALORES INICIAIS (para edição ou criação) ----------
    initial_proj = projeto_placeholder
    #initial_user = consultor_placeholder
    initial_date = data_clicada if data_clicada else date.today()
    final_date = data_clicada if data_clicada else date.today()
    initial_hora_inicio = time(8, 0)
    initial_hora_fim = time(17, 0)
    initial_atividade = ""
    initial_obs = ""
    existing_idagenda = None
    initial_demanda_id = ""

    # se for edição e existing vem preenchido, usa esses valores
    if is_edit and existing:
        existing_idagenda = existing.get('idAgenda') or existing.get('idagenda') or existing.get('id')
        initial_user = existing.get('idUsuario') or existing.get('idusuario') or initial_user
        initial_proj = existing.get('idProjeto') or existing.get('idprojeto') or initial_proj
        initial_demanda_id = str(existing.get('idDemanda')) if existing.get('idDemanda') else ""
        try:
            di = existing.get('datInicio')
            df = existing.get('datFim')
            if isinstance(di, str):
                di = datetime.fromisoformat(di)
            if isinstance(df, str):
                df = datetime.fromisoformat(df)
            initial_date = di.date()
            final_date = df.date()  
            initial_hora_inicio = di.time()
            initial_hora_fim = df.time()
        except Exception:
            pass
        initial_atividade = existing.get('atividade') or ""
        initial_obs = existing.get('obsAgenda') or existing.get('obsagenda') or ""

    # se for edição via event_payload (sem existing), tenta extrair
    if is_edit and existing is None and event_payload:
        existing_idagenda = event_payload.get('id') or event_payload.get('extendedProps', {}).get('idAgenda')
        # tenta inferir proprietário/projeto a partir do payload
        # note: o payload normalmente não tem idUsuario/idProjeto; isso é fallback

    # ---------- CAMPOS DO FORMULÁRIO ----------
    # INPUT PARA BUSCAR DEMANDA (OBRIGATÓRIO)
    demanda_projeto = ""
    demanda_usuario = ""
    pacote_demanda = ""
    
    col1, col2 = st.columns(2)
    with col1:
        # preenche com o id existente quando for edição
        demanda_id = st.text_input("ID da Demanda *", value=initial_demanda_id)
    with col2:
        if not demanda_id.strip():
            st.warning("Preencha o ID da Demanda para continuar.")

        # Buscar demanda
        if demanda_id.strip():
            q_demanda = """select d.idDemanda, d.nomePWA, d2.responsavel, DATE_FORMAT(previsaoInicio, '%d/%m/%Y') as previsaoInicio , DATE_FORMAT(previsaoFim, '%d/%m/%Y') as previsaoFim, d.horas, d.atendimento, d.escopo as pacote,u.nome as solicitante from demanda d left join demandausuario d2 on d.idDemanda = d2.idDemanda and d2.selecionado = 1 left join usuario u on u.idUsuario = d.idUsuario where d.iddemanda = %s"""
            res_demanda = select(q_demanda, (demanda_id.strip(),))
            
            if res_demanda:
                # aplica limpeza também à resposta da demanda (caso contenha caracteres)
                demanda_projeto = limpar_sql_texto(res_demanda[0].get("nomePWA", ""))
                demanda_usuario = limpar_sql_texto(res_demanda[0].get("responsavel", ""))
                solicitante_demanda = limpar_sql_texto(res_demanda[0].get("solicitante", ""))
                previsao_inicio = res_demanda[0].get("previsaoInicio", "")
                previsao_fim = res_demanda[0].get("previsaoFim", "")
                horas_demanda = res_demanda[0].get("horas", "")
                atendimento_demanda = res_demanda[0].get("atendimento", "")
                pacote_demanda = res_demanda[0].get("pacote", "")
                st.markdown(
                        f"""
                        <div style="background-color:#d4edda; padding:10px; border-radius:5px; color:#155724;">
                            <b>ID Demanda:</b> {res_demanda[0].get("idDemanda", "")} </br>
                            <b>Solicitante:</b> {solicitante_demanda} </br>
                            <b>Previsão:</b> {previsao_inicio} - {previsao_fim}</br>
                            <b>Qtd Horas:</b> {horas_demanda} | <b>Atendimento:</b> {atendimento_demanda}</br>
                            <b>Pacote:</b> {pacote_demanda}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            else:
                st.error("Nenhuma demanda encontrada com esse ID.")
                demanda_projeto = ""
                demanda_usuario = ""
                
    # ---------------------------------------------
    # CAMPOS APENAS VISUAIS (NÃO EDITÁVEIS)
    # ---------------------------------------------
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Projeto", value=demanda_projeto, disabled=True)
    with col2:
        if pacote_demanda == "Fechado Entrega":
            query_consultores = """
                SELECT idusuario, nome, empresa, email
                FROM usuario
                WHERE idProduto = 1
                AND email LIKE '%consultorseniorsistemas.com.br%'
                AND ativo = 1
                AND empresa IS NOT NULL
                AND nome NOT LIKE '%Canal%'
                ORDER BY empresa, nome
            """
            consultores_lista = select(query_consultores) or []

            consultor_placeholder = -1  # ✔ definido antes

            consultores_opcoes = {
                consultor_placeholder: "Selecione um consultor"
            }

            consultores_opcoes.update({
                c['email']: f"{c['nome']} ({c.get('empresa','')})"
                for c in consultores_lista
            })

            demanda_usuario = st.selectbox(
                "Consultor",
                options=list(consultores_opcoes.keys()),
                format_func=lambda x: consultores_opcoes[x]
            )

        else:
            st.text_input("Consultor", value=demanda_usuario, disabled=True)
    # Aqui continuam os outros campos do formulário normalmente...
    col1, col2, col3,col4 = st.columns(4)
    with col1:
        data_inputi = st.date_input("Data Início", value=initial_date, format="DD/MM/YYYY")
    with col2:
        hora_inicio = st.time_input("Hora início", value=initial_hora_inicio)
    with col3:
        data_inputf = st.date_input("Data Final", value=final_date, format="DD/MM/YYYY")
    with col4:
        hora_fim = st.time_input("Hora Final", value=initial_hora_fim)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        seg = st.checkbox("Seg", value=True)
    with col2:
        ter = st.checkbox("Ter", value=True)             
    with col3:
        qua = st.checkbox("Qua", value=True)             
    with col4:
        qui = st.checkbox("Qui", value=True)             
    with col5:
        sex = st.checkbox("Sex", value=True)   
        
    col1, col2 = st.columns(2)
    with col1:
        atividade = st.text_input("Atividade", value=initial_atividade)
    with col2:
        observacao = st.text_input("Observação", value=initial_obs)   

    # ---------- AÇÃO SALVAR (create ou update) ----------
    if st.button("Salvar"):
        # validações
        if not demanda_id.strip():
            st.error("Informe uma demanda!")
            return
        
        if hora_fim <= hora_inicio:
            st.error("Hora fim deve ser maior que hora início.")
            return
        
        # ---------- VALIDAÇÃO DATA DO AGENDAMENTO x DEMANDA ----------
        try:
            # previsao_inicio e previsao_fim já vêm do select da demanda
            if previsao_inicio and previsao_fim:
                previsao_inicio_dt = datetime.strptime(previsao_inicio, "%d/%m/%Y").date()
                previsao_fim_dt = datetime.strptime(previsao_fim, "%d/%m/%Y").date()

                if (
                    data_inputi < previsao_inicio_dt
                    or data_inputf > previsao_fim_dt
                ):
                    st.error(
                        f"""
                        ❌ **Agendamento inválido**

                        A data do agendamento está fora do período da demanda.

                        📌 **Período da Demanda:**  
                        {previsao_inicio_dt.strftime('%d/%m/%Y')} até {previsao_fim_dt.strftime('%d/%m/%Y')}

                        📅 **Agendamento informado:**  
                        {data_inputi.strftime('%d/%m/%Y')} até {data_inputf.strftime('%d/%m/%Y')}
                        """
                    )
                    return
        except Exception as e:
            st.error(f"Erro ao validar datas da demanda: {e}")
            return
        
        
        usuario = """select * from usuario where email = %s"""
        dados_usuario = select(usuario, (demanda_usuario.strip(),))
        
        if dados_usuario:
            usuario_id = dados_usuario[0].get("idUsuario") or dados_usuario[0].get("idusuario")
        else:
            st.error("Consultor não encontrado no sistema.")
            return

        datInicio = datetime.combine(data_inputi, hora_inicio)
        datFim = datetime.combine(data_inputf, hora_fim)

        # calcular duração da nova agenda
        horas_nova = calcular_horas_com_almoco(datInicio, datFim)
        
        # buscar horas existentes no banco para essa demanda
        sql_horas_existentes = """
        SELECT datInicio, datFim
         FROM agenda2
        WHERE idDemanda = %s
        AND status <> 2
        """
        agendas_existentes = select(sql_horas_existentes, (demanda_id.strip(),)) or []

        horas_existentes = 0.0
        for a in agendas_existentes:
            horas_existentes += calcular_horas_com_almoco(
        a["datInicio"],
        a["datFim"]
        )
            
        horas_nova = calcular_horas_com_almoco(datInicio, datFim)
             
        # somatória final
        horas_totais = float(horas_existentes) + float(horas_nova)
        
        def horas_decimal_para_hhmm(horas: float) -> str:
            h = int(horas)
            m = int(round((horas - h) * 60))
            return f"{h}:{m:02d}"

        # validação
        if pacote_demanda != "Fechado Entrega":
            if horas_totais > horas_demanda:
                st.error(
                    f"⚠️ A soma das horas já cadastradas ({horas_decimal_para_hhmm(horas_existentes)}) "
                    f"+ as horas desta agenda ({horas_decimal_para_hhmm(horas_nova)}) "
                    f"ultrapassa o limite da Demanda ({horas_decimal_para_hhmm(horas_demanda)})."
                )
                return

        # montar INSERT ou UPDATE dependendo de is_edit
        try:
            # garantir que idDemanda seja int ou None
            id_demanda_para_salvar = demanda_id.strip() if demanda_id.strip() else None

            # limpar campo atividade/observação antes de salvar (evita caracteres indesejados)
            atividade_para_salvar = limpar_sql_texto(atividade or "")
            if atividade_para_salvar == "":
                st.error("A atividade não pode ficar vazia.")
                return 
            
            observacao_para_salvar = limpar_sql_texto(observacao or "")
            demanda_projeto_para_salvar = limpar_sql_texto(demanda_projeto or "")

            if is_edit and existing_idagenda:
                fmt = lambda d: d.strftime("%d/%m/%Y %H:%M")

                conflitos = verificar_conflito(usuario_id, datInicio, datFim, existing_idagenda)
                if conflitos:
                    st.error("⚠️ Conflito detectado: o consultor já possui agenda nesse intervalo.")
                    for c in conflitos:
                        projeto = c.get("nomeProjeto", "") or c.get("projeto", "") or ""
                        st.write(
                            f" - {fmt(c['datInicio'])} → {fmt(c['datFim'])} | Projeto: {projeto}"
                        )
                    return
                
                
                # UPDATE incluindo idDemanda
                update_query = """
                    UPDATE agenda2
                    SET idUsuario=%s, nomeProjeto=%s, datInicio=%s, datFim=%s, atividade=%s, obsAgenda=%s, idDemanda=%s
                    WHERE idAgenda=%s
                """
                execute(update_query, (
                    usuario_id, demanda_projeto_para_salvar, datInicio, datFim, atividade_para_salvar, observacao_para_salvar, id_demanda_para_salvar, existing_idagenda
                ))

                registrar_log(existing_idagenda, "Alteração de Agenda", detalhe="Agenda alterada.")
                st.success("Agendamento atualizado com sucesso!")
            else:
                # horários originais
                hora_inicio = datInicio.time()
                hora_fim = datFim.time()

                # datas sem horário
                dia_inicio = datInicio.date()
                dia_fim = datFim.date()

                dia_atual = dia_inicio

                # mapeia checkbox → número do dia da semana
                dias_permitidos = {
                    0: seg,  # segunda
                    1: ter,  # terça
                    2: qua,  # quarta
                    3: qui,  # quinta
                    4: sex   # sexta
                }
                conflitos_por_dia = []
                dias_validos = []  # dias sem conflito

                fmt = lambda d: d.strftime("%d/%m/%Y %H:%M")

                while dia_atual <= dia_fim:
                    dia_semana = dia_atual.weekday()

                    if dias_permitidos.get(dia_semana, False):

                        inicio_do_dia = datetime.combine(dia_atual, hora_inicio)
                        fim_do_dia = datetime.combine(dia_atual, hora_fim)

                        conflitos = verificar_conflito(usuario_id, inicio_do_dia, fim_do_dia)

                        if conflitos:
                            conflitos_por_dia.append({
                                "data": dia_atual,
                                "inicio": inicio_do_dia,
                                "fim": fim_do_dia,
                                "conflitos": conflitos
                            })
                        else:
                            dias_validos.append({
                                "inicio": inicio_do_dia,
                                "fim": fim_do_dia
                            })

                    dia_atual += timedelta(days=1)

                
                if conflitos_por_dia:
                    fmt = lambda d: d.strftime("%d/%m/%Y %H:%M")

                    st.error("⚠️ Conflitos detectados nas seguintes datas:")

                    for item in conflitos_por_dia:
                        st.write(f"📅 {item['data'].strftime('%d/%m/%Y')}")
                        for c in item["conflitos"]:
                            projeto = c.get("nomeProjeto", "") or c.get("projeto", "") or ""
                            st.write(
                                f" - {fmt(c['datInicio'])} → {fmt(c['datFim'])} | Projeto: {projeto}"
                            )

                    return  # 🚫 não cria nenhuma agenda

                for d in dias_validos:
                    insert_query = """ INSERT INTO agenda2 (idUsuario, nomeProjeto, datInicio, datFim, atividade, obsAgenda, status, datCadastro, idDemanda) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s) """
                    execute(insert_query, (
                        usuario_id,
                        demanda_projeto_para_salvar,
                        d["inicio"],
                        d["fim"],
                        atividade_para_salvar,
                        observacao_para_salvar,
                        1,
                        id_demanda_para_salvar
                    ))

                st.success("Agendamento criado com sucesso!")

                
            st.success("Agendamento criado com sucesso!")
            for key in ["demanda_id", "datInicio", "datFim", "atividade", "observacao"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

        except Exception as e:
            st.error(f"Erro ao salvar no banco: {e}")
            return

def main():
    # -------------------------------
    # USUARIO LOGADO: Buscar usuario que foi passado em Dashboards.py
    # -------------------------------
    # Captura o parâmetro da URL
    params = st.query_params
    usuario_url = params.get("idResponsavel")

    # Se ainda não estiver salvo na sessão, salva
    if "idResponsavel" not in st.session_state and usuario_url:
        if isinstance(usuario_url, list):
            usuario_url = usuario_url[0]
        st.session_state["idResponsavel"] = usuario_url

    # Recupera da sessão
    usuario = st.session_state.get("idResponsavel")
    resultado = select(
        "SELECT nome FROM usuario WHERE idUsuario = %s",
        (usuario,)
    )
    nome_usuario = resultado[0]['nome'] if resultado else 0
    st.session_state['nome_usuario'] = nome_usuario
    #----------------------------------------------------------------------

    st.title("📅 Agenda de Consultores ERP")
    # CSS para evitar overflow (mantive seu trecho)
    st.markdown(
        """
        <style>
        .css-1aumxhk {
            overflow: hidden;
        }
        /* Permite o popover do +mais ultrapassar o calendário */
        .fc-daygrid-day-frame,
        .fc-daygrid-day-events,
        .fc-scroller {
            overflow: visible !important;
        }

        /* Garante que o popover fique acima de tudo */
        .fc-more-popover {
            z-index: 9999 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    MAX_CARACTERES_TITULO = 20

    def limitar_texto(texto, limite=20):
        if texto and len(texto) > limite:
            return texto[:limite] + "…"
        return texto
    
  
    calendar_options = {
        "themeSystem": "bootstrap5",
        "timeZone": "local",
        "locale": "pt-br",
        "editable": False,
        "eventStartEditable": False,
        "eventDurationEditable": False,
        "selectable": True,
        "weekends": True,

        # NOVOS AJUSTES PARA MUITOS EVENTOS
        "dayMaxEventRows": 3,      # Limita quantos aparecem na célula
        "expandRows": False,        # Permite aumentar a altura do mês
        "eventDisplay": "block",   # Evita sobreposição ou eventos "apertados"
        "moreLinkContent": "mais +",  # Texto para o link "more"

        "buttonText": {
            "today": 'Hoje',
            "month": 'Mês',
            "week": 'Semana',
            "day": 'Dia',
            "list": 'Lista'
        },

        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": ""
        },

        "slotMinTime": "08:00:00",
        "slotMaxTime": "18:00:00",
        "initialView": "dayGridMonth",
        "height": "auto"
    }
    
    
    
    # inicializa variáveis de sessão
    if 'abrir_modal' not in st.session_state:
        st.session_state['abrir_modal'] = True
        # abrirAgenda(st.session_state.get('evento_selecionado', {}))
    else:
        st.session_state['abrir_modal'] = False
    
    
    if st.session_state.get('abrir_modal_edicao', False):
        abrirNovoModal_edicao(st.session_state.get('editar_evento', {}))
        st.session_state['abrir_modal_edicao'] = False
        
    # buscar dados com sua query completa
    api_data = buscar_dados_api()
    
    # Filtro original de responsáveis
    if api_data is not None and nome_usuario != 0:
        st.write(f"""Bem vindo, {nome_usuario}!""")
        

        
        # Filtros - consultores e empresas ( mesma query sua )
        query_consultores = """
            SELECT idusuario, nome, empresa
            FROM usuario
            WHERE email LIKE '%consultorseniorsistemas.com.br%'
            AND ativo = 1
            AND empresa IS NOT NULL
            AND nome NOT LIKE '%Canal%'
            ORDER BY empresa, nome
        """
        consultores = select(query_consultores) or []

        lista_empresas = sorted(list(set([c['empresa'] for c in consultores if c.get('empresa')])))
        lista_empresas.insert(0, "Todas")

        lista_consultores = sorted(list(set([c['nome'] for c in consultores if c.get('nome')])))
        lista_consultores.insert(0, "Todos")
        
        # ----- NOVO: lista de solicitantes -----
        lista_solicitantes = sorted(list(set([
        registro.get('solicitante')
        for registro in api_data
        if registro.get('solicitante')
        ])))
        lista_solicitantes.insert(0, "Todos")
        
        responsaveis = sorted(list(set([registro['usuario'] for registro in api_data])))
        responsaveis.insert(0, "Todos")
        defaultResponsavel = "Todos"
        # ajustado para 4 colunas incluindo o filtro de projeto
        col1,col2,col3,col4 = st.columns(4)

        with col1:
            empresa_sel = st.multiselect("Consultoria", lista_empresas, default=["Todas"])
#        with col2:
 #           consultor_sel = st.multiselect("Filtrar por consultor", lista_consultores, default=["Todos"])
        with col2:            
            responsavel_selecionado = st.multiselect("Responsável (Consultor)", responsaveis, default=[defaultResponsavel])   
        with col3:
            solicitante_sel = st.multiselect("Solicitante da Demanda(Gerente de Projetos)",lista_solicitantes,default=["Todos"])
            
        # ----- NOVO: lista de projetos extraída dos dados da agenda -----
        lista_projetos = sorted(list(set([
            registro.get('nomeProjeto') for registro in api_data if registro.get('nomeProjeto')
        ])))
        lista_projetos.insert(0, "Todos")

        with col4:
            projeto_selecionado = st.multiselect("Projeto", lista_projetos, default=["Todos"])
            
        st.sidebar.subheader("Filtros")

        filtro_status = st.sidebar.radio(
        "Status da Agenda",
        ("Ativas", "Canceladas", "Todas"),
        horizontal=True
        )
        
        # Lista de eventos para o calendário
        eventos = []
        for registro in api_data:
            # aplica filtro por projeto antes de montar o evento
            if "Todos" not in projeto_selecionado:
                # tratar None ou string vazia
                nome_proj = registro.get('nomeProjeto') or ""
                if nome_proj not in projeto_selecionado:
                    continue


            # --- APLICAR FILTRO DE STATUS (Ativas / Canceladas / Todas)
            status_val = registro.get('statusAgenda') or registro.get('status') or 0
            try:
                status_int = int(status_val)
            except Exception:
                status_int = 0
            if filtro_status == "Ativas" and status_int != 1:
                continue
            if filtro_status == "Canceladas" and status_int != 2:
                continue
            # trata datetimes (assume que datInicio/datFim já são datetime)
            try:
                data_inicio_dt = registro['datInicio']
                data_fim_dt = registro['datFim']
            except Exception:
                # se os dados vierem como string, tenta parse
                try:
                    data_inicio_dt = datetime.fromisoformat(registro['datInicio'])
                    data_fim_dt = datetime.fromisoformat(registro['datFim'])
                except Exception:
                    # se falhar, ignora este registro
                    continue

            data_inicial_dt = data_inicio_dt.date()
            data_final_dt = data_fim_dt.date()
            
            hora_inicial = data_inicio_dt.time()
            hora_final = data_fim_dt.time()
            
            
            if (
                ("Todos" in responsavel_selecionado or registro['usuario'] in responsavel_selecionado)
                and ("Todas" in empresa_sel or registro.get('modeloEquipe') in empresa_sel)
                #and ("Todos" in consultor_sel or registro['usuario'] in consultor_sel)#
                and ("Todos" in solicitante_sel or registro.get('solicitante') in solicitante_sel)
            ):
                # caso span de dias, quebra em eventos por dia (como você fazia)
                for i in range((data_final_dt - data_inicial_dt).days + 1):
                    data_atual = data_inicial_dt + timedelta(days=i)
                    start = f"{data_atual.strftime('%Y-%m-%d')}T{hora_inicial.strftime('%H:%M:%S')}"
                    end = f"{data_atual.strftime('%Y-%m-%d')}T{hora_final.strftime('%H:%M:%S')}"
                    # cores por empresa, mas se cancelada usar vermelho
                    if status_int == 2:
                        bgColor = '#ffe6e6'  # fundo vermelho claro
                        border_color = '#ff6666'  # borda vermelha
                    else:
                        bgColor, border_color = empresa_to_color(registro.get('nomeProjeto') or registro.get('modeloEquipe'))
                    projeto = (registro.get('nomeProjeto') or '').replace("Gestão Empresarial - ERP-", "")
                    
                    eventos.append({
                        "id": registro.get('idagenda') or registro.get('idAgenda') or registro.get('idAgenda'),
                        "allDay": True,
                        "title": (hora_inicial.strftime('%H:%M')) + " - " + hora_final.strftime('%H:%M') + " / " + registro['usuario'] + " / " + projeto ,
                        "start": start,
                        "end": end,
                        "resourceId": registro['idUsuario'],
                        "backgroundColor": bgColor,
                        "borderColor": border_color,
                        "extendedProps": {
                            "idAgenda": registro.get('idagenda') or registro.get('idAgenda'),
                            "usuario": registro['usuario'], #quem cadastrou agenda
                            "projeto": registro.get('nomeProjeto', ''), #
                            "idDemanda": registro.get('idDemanda', ''), #
                            "solicitante": registro.get('solicitante', ''),
                            "atividade": registro.get('atividade', ''),
                            "obs": registro.get('obsagenda', ''),
                            "start": start,
                            "end": end,
                            "modulos": registro.get('modulos', ''),
                            "escopo": registro.get('escopo', ''),
                            "inicio": registro.get('inicio', ''),
                            "fim": registro.get('fim', ''),
                            "atendimento": registro.get('atendimento', ''),
                            "previsaoInicio": registro.get('previsaoInicio', ''),
                            "previsaoFim": registro.get('previsaoFim', ''),
                            "horas": registro.get('horas', ''),
                            "statusAgenda": status_int
                        }
                    })

        if eventos:
            st.markdown("""
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/admin-lte@3.1/dist/css/adminlte.min.css">
                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.6.0/css/all.min.css" integrity="sha512-Kc323vGBEqzTmouAECnVceyQqyqdsSiqLQISBL29aUW4U/M7pSPA/gEUZQqv1cwx4OnYxTxve5UMg5GT6L4JJg==" crossorigin="anonymous" referrerpolicy="no-referrer" />
            """, unsafe_allow_html=True)
            
            calendar_widget = streamlit_calendar(
                events=eventos,
                options=calendar_options,
                custom_css="""
                .fc-event-title {
                    font-weight: normal;
                }
                .fc-h-event .fc-event-main{
                    color:#000;
                    font-size:80%;
                }
                .fc-event-title,
                .fc-event-time,
                .fc-event-main {
                    white-space: normal !important;
                }
                .fc-event {
                    margin-bottom: 2px !important;
                    margin-right: 6px !important;
                    margin-left: 6px !important;
                }
                """)
            
            
            
            with st.expander("❓ Perguntas Frequentes sobre a Agenda"):
                st.markdown(FAQ_MD)
            
            # Cliques em eventos
            if calendar_widget.get("callback") == "eventClick":
                st.session_state['abrir_modal'] = True
                # abrir modal com dados do evento
                ev = calendar_widget["eventClick"]["event"]
                if st.session_state.get('abrir_modal', False):
                    abrirAgenda(ev)

            # Clique no dia → abrir modal de novo agendamento (passando a data)
            if calendar_widget.get("callback") == "dateClick":
                date_str = calendar_widget["dateClick"]["date"]  # espera ISO date string
                try:
                    data_click = datetime.fromisoformat(date_str).date()
                except Exception:
                    data_click = datetime.strptime(date_str.split("T")[0], "%Y-%m-%d").date()
                
                abrirNovoModal(data_clicada=data_click)


        else:
            st.title("Sem agendas para mostrar")    
    else:
        st.title("Usuário sem permissão para acessar agenda!")    
    
# =========================
# MÉTRICAS – TOTAL GERAL
# =========================

def buscar_metricas_agenda():
    query = """
        SELECT
            COUNT(DISTINCT idAgenda)    AS qtd_agendas,
            COUNT(DISTINCT idUsuario)   AS qtd_consultores,
            COUNT(DISTINCT nomeProjeto) AS qtd_projetos
        FROM agenda2
        WHERE status = 1
    """
    return select(query)


# -------------------------
#        MÉTRICAS
# -------------------------

metricas = buscar_metricas_agenda()

# CSS dos cards
st.markdown(
    """
    <style>
    .metric-card {
        padding: 20px;
        border-radius: 16px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .metric-title {
        font-size: 16px;
        opacity: 0.9;
    }
    .metric-value {
        font-size: 36px;
        font-weight: bold;
        margin-top: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

if metricas and len(metricas) > 0:
    m = metricas[0]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #4facfe, #00f2fe);">
                <div class="metric-title">📅 Total de Agendas</div>
                <div class="metric-value">{m.get("qtd_agendas", 0)}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #43e97b, #38f9d7);">
                <div class="metric-title">🧑‍💼 Total de Consultores</div>
                <div class="metric-value">{m.get("qtd_consultores", 0)}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #fa709a, #fee140);">
                <div class="metric-title">🏛️ Total de Projetos</div>
                <div class="metric-value">{m.get("qtd_projetos", 0)}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

else:
    st.warning("Nenhuma métrica encontrada.")
 

 
FAQ_MD = """
### 🎯 Objetivo da ferramenta
Esta ferramenta é destinada **exclusivamente ao controle interno**! Ela **não substitui** a confirmação da disponibilidade real dos consultores, nem a validação da atuação nos períodos desejados.

---

### 🔄 Alterações em agendamentos
Sempre que houver mudança nos dias agendados — seja por solicitação do cliente ou da consultoria — a atualização **deve ser realizada diretamente na ferramenta**, garantindo que as informações reflitam a **atuação real do consultor**.

---

### 📋 Informações utilizadas no agendamento
Para o correto registro das agendas, são consideradas as seguintes informações:
- Número do **card**
- Data de **início** e **término**
- Quantidade de **horas** (para demandas por hora)
- **Consultor** vinculado
- **Gerente de Projetos (GP)** responsável

---

### 🔐 Permissões de acesso
A criação e alteração de agendamentos são permitidas **exclusivamente** para:
- **GP responsável pelo projeto**
- **Time de Alocação**

---

### 🚫 Regras e restrições
Para garantir a consistência das informações, aplicam-se as seguintes regras:
- Não é permitido registrar agendas **sem vínculo com um card**
- Não é possível agendar dias ou horas **além do quantitativo definido no card**
- **Finais de semana** não são contabilizados
- O **período de almoço** não é contabilizado  
  ⏰ Das **12:00 às 13:00**

---

### 💼 Vínculo do consultor
O vínculo do consultor ocorre de acordo com o tipo de demanda:
- **Pacote financeiro:** consultor definido diretamente na agenda
- **Demandas por hora:** consultor atribuído automaticamente conforme o card

---

### 🔍 Filtros disponíveis
É possível filtrar as agendas pelos seguintes critérios:
- Projeto
- Gerente de Projetos (GP)
- Consultor
- Consultoria
"""
         
if __name__ == "__main__":
    main()
