from bd.conexao import select, execute
import streamlit as st
from streamlit_calendar import calendar as streamlit_calendar
from datetime import date, datetime, time, timedelta
from typing import Any
import hashlib
import colorsys
import re
import unicodedata

st.set_page_config(layout="wide")
st.title("Agendas ERP")

def registrar_log(idagenda, usuario, acao, detalhe=""):
    try:
        sql = """
        INSERT INTO agenda2_logs (idagenda, usuario, acao, detalhe, datahora)
        VALUES (%s, %s, %s, %s, NOW())
        """
        execute(sql, (idagenda, usuario, acao, detalhe))
    except Exception as e:
        st.error(f"Erro ao registrar log: {e}")

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
# ----------------------
# UTIL: verificar se a coluna existe na tabela (para compatibilidade)
# ----------------------
def has_column(table: str, column: str) -> bool:
    """
    Retorna True se a coluna existir na tabela (MySQL INFORMATION_SCHEMA).
    Ajuste se seu banco for diferente.
    """
    try:
        q = """
            SELECT COUNT(*) as qtd
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = %s
              AND column_name = %s
        """
        res = select(q, (table, column))
        if res and isinstance(res, list):
            return int(res[0].get('qtd', res[0].get('QTD', 0))) > 0
        return False
    except Exception:
        # Se a consulta falhar, assume False para segurança
        return False

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
@st.dialog("Detalhes da Agenda", width="large")
def abrirAgenda(agenda):
    st.markdown("""
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    """, unsafe_allow_html=True)
    
    # LOG: usuário abriu CARD de detalhes
    usuario_log = st.session_state.get("usuario_logado", "idusuario_desconhecido")
    registrar_log(
        idagenda=agenda.get("id") or agenda.get("extendedProps", {}).get("idAgenda"),
        usuario=usuario_log,
        acao="ABRIU_CARD_DETALHES",
    detalhe="Acessou o card de detalhes da agenda"
)
# --- LOG VISÍVEL NO MODAL ---
    st.markdown(
    f"""
    <div style='background:#eef; padding:10px; border-left:4px solid #446; margin-bottom:15px; border-radius:4px;'>
        <b>📘 Log:</b> Modal aberto às {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
    </div>
    """,
    unsafe_allow_html=True
    )
   
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
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("✏️ Editar"):
            st.session_state["editar_evento"] = agenda
            st.session_state["abrir_edicao"] = True
            st.rerun()
    with col2:
        if st.button("❌ Cancelar"):
            try:
                idagenda = agenda.get("id", agenda.get("extendedProps", {}).get("idAgenda"))
                if not idagenda:
                    idagenda = agenda.get("extendedProps", {}).get("idAgenda")

                delete_query = "UPDATE agenda2 set status = 2 WHERE idAgenda = %s"
                execute(delete_query, (idagenda,))

                st.session_state['reload_calendar'] = True
                st.rerun()  # recarrega a página imediatamente
            except Exception as e:
                st.error(f"Erro ao excluir: {e}")

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

@st.dialog("Criar nova agenda", width="large")
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
        
        usuario = """select * from usuario where email = %s"""
        dados_usuario = select(usuario, (demanda_usuario.strip(),))
        
        if dados_usuario:
            usuario_id = dados_usuario[0].get("idUsuario") or dados_usuario[0].get("idusuario")
        else:
            st.error("Consultor não encontrado no sistema.")
            return

        datInicio = datetime.combine(data_inputi, hora_inicio)
        datFim = datetime.combine(data_inputf, hora_fim)

        # conflito: seleciona registros conflitantes, ignorando o próprio registro quando edição
        sql_conflito = """
            SELECT idAgenda, idUsuario, datInicio, datFim,nomeProjeto as projeto
            FROM agenda2
            WHERE idUsuario = %s
              AND (
                    (datInicio <= %s AND datFim > %s)
                    OR
                    (datInicio < %s AND datFim >= %s)
                    OR
                    (datInicio >= %s AND datFim <= %s)
                  )
        """
        params = (usuario_id, datFim, datInicio, datFim, datInicio, datInicio, datFim)
        conflitos = select(sql_conflito, params) or []
        # se for edição, remover self da lista de conflitos
        if is_edit and existing_idagenda:
            conflitos = [c for c in conflitos if int(c.get('idAgenda') or c.get('idagenda') or 0) != int(existing_idagenda)]
            
        fmt = lambda d: d.strftime("%d/%m/%Y %H:%M")
        if conflitos:
            st.error("⚠️ Conflito detectado: o consultor já possui agenda nesse intervalo.")
            for c in conflitos:
                projeto = c.get("nomeProjeto", "") or c.get("projeto", "") or ""
                st.write(f" - {fmt(c['datInicio'])} → {fmt(c['datFim'])} | Projeto: {projeto}")
            return

        # VALIDAR HORAS DE AGENDA COM HORAS DA DEMANDA
        # calcular duração da nova agenda
        duracao_nova = datFim - datInicio
        horas_nova = duracao_nova.total_seconds() / 3600

        # buscar horas existentes no banco para essa demanda
        sql_soma_horas = """
            SELECT 
                SUM(TIME_TO_SEC(datFim) - TIME_TO_SEC(datInicio)) AS total_segundos
            FROM agenda2
            WHERE idDemanda = %s
        """
        resultado = select(sql_soma_horas, (demanda_id.strip(),))
        total_seg_existentes = resultado[0]["total_segundos"] or 0
        horas_existentes = total_seg_existentes / 3600

        # somatória final
        horas_totais = float(horas_existentes) + float(horas_nova)

        # validação
        if pacote_demanda != "Fechado Entrega":
            if horas_totais > horas_demanda:
                st.error(
                    f"⚠️ A soma das horas já cadastradas ({horas_existentes:.2f}) "
                    f"+ as horas desta agenda ({horas_nova:.2f}) "
                    f"ultrapassa o limite da Demanda ({horas_demanda:.2f})."
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
                # UPDATE incluindo idDemanda
                update_query = """
                    UPDATE agenda2
                    SET idUsuario=%s, nomeProjeto=%s, datInicio=%s, datFim=%s, atividade=%s, obsAgenda=%s, idDemanda=%s
                    WHERE idAgenda=%s
                """
                execute(update_query, (
                    usuario_id, demanda_projeto_para_salvar, datInicio, datFim, atividade_para_salvar, observacao_para_salvar, id_demanda_para_salvar, existing_idagenda
                ))
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

                while dia_atual <= dia_fim:

                    # pega o número do dia da semana (0=segunda ...)
                    dia_semana = dia_atual.weekday()

                    # verifica se checkbox correspondente está marcado
                    if dias_permitidos.get(dia_semana, False):

                        inicio_do_dia = datetime.combine(dia_atual, hora_inicio)
                        fim_do_dia = datetime.combine(dia_atual, hora_fim)

                        insert_query = """
                            INSERT INTO agenda2
                                (idUsuario, nomeProjeto, datInicio, datFim, atividade, obsAgenda, status, datCadastro, idDemanda)
                            VALUES
                                (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                        """

                        execute(insert_query, (
                            usuario_id,
                            demanda_projeto_para_salvar,
                            inicio_do_dia,
                            fim_do_dia,
                            atividade_para_salvar,
                            observacao_para_salvar,
                            1,
                            id_demanda_para_salvar
                        ))

                    # próximo dia
                    dia_atual += timedelta(days=1)
                
            st.success("Agendamento criado com sucesso!")

            st.session_state['reload_calendar'] = True
            
            for key in ["demanda_id", "datInicio", "datFim", "atividade", "observacao"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()


        except Exception as e:
            st.error(f"Erro ao salvar no banco: {e}")
            return

# abrir modal de edição fora de qualquer outro modal
if st.session_state.get("abrir_edicao"):
    agenda = st.session_state.get("editar_evento")
    if agenda:
        abrirNovoModal_edicao(agenda)
    st.session_state["abrir_edicao"] = False
# -------------------------------
# MAIN: calendário, filtros e eventos (mantive seus filtros)
# -------------------------------
def main():
    # garante reload flag
    if "reload_calendar" not in st.session_state:
        st.session_state['reload_calendar'] = False

    # CSS para evitar overflow (mantive seu trecho)
    st.markdown(
        """
        <style>
        .css-1aumxhk {
            overflow: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

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
    "expandRows": True,        # Permite aumentar a altura do mês
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
        "right": "dayGridMonth"
    },

    "slotMinTime": "08:00:00",
    "slotMaxTime": "18:00:00",
    "initialView": "dayGridMonth",
    "height": "auto"
}


    # buscar dados com sua query completa
    api_data = buscar_dados_api()
    
    # Filtro original de responsáveis
    if api_data is not None:
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
                        bgColor, border_color = empresa_to_color(registro.get('modeloEquipe') or registro.get('cargo') or registro.get('usuario'))
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
                    font-size:85%;
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
            
            # Cliques em eventos
            if calendar_widget.get("callback") == "eventClick":
                # abrir modal com dados do evento
                ev = calendar_widget["eventClick"]["event"]
                abrirAgenda(ev)

            # Clique no dia → abrir modal de novo agendamento (passando a data)
            if calendar_widget.get("callback") == "dateClick":
                date_str = calendar_widget["dateClick"]["date"]  # espera ISO date string
                try:
                    data_click = datetime.fromisoformat(date_str).date()
                except Exception:
                    data_click = datetime.strptime(date_str.split("T")[0], "%Y-%m-%d").date()
                abrirNovoModal(data_clicada=data_click)

            # Se salvou (flag) → recarrega a página para atualizar eventos
            if st.session_state.get('reload_calendar'):
                st.session_state['reload_calendar'] = False
                st.rerun()

        else:
            st.title("Sem agendas para mostrar")    
    
            
if __name__ == "__main__":
    main()
