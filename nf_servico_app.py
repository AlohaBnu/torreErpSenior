import io
import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st
import requests

# -------------------------------------------
# 🧩 CONFIGURAÇÃO GERAL
# -------------------------------------------
st.set_page_config(page_title="Analisador de XML NFS-e", page_icon="🧾", layout="wide")
st.title("🧾 Analisador Inteligente de XML de Notas Fiscais de Serviço (NFS-e)")

st.markdown("""
Analise **arquivos XML de NFS-e** e visualize:
- 🏢 Prestador e Tomador identificados corretamente  
- 🌆 Município tomador (via IBGE)  
- 💰 Impostos (ISS, PIS, COFINS, IR, CSLL, INSS etc.)  
- 🧾 Tipos de serviço (LC 116/2003)  
- 📋 Detalhes completos das notas  
""")

# -------------------------------------------
# 📘 Dicionário LC 116/2003 - Códigos de Serviço
# -------------------------------------------
CODIGOS_SERVICO = {
    "7.02": "Execução de obras de construção civil, hidráulica ou elétrica",
    "7.05": "Demolição",
    "8.02": "Execução de desenho, pintura e escultura",
    "10.05": "Assessoria e consultoria em informática",
    "13.03": "Hospedagem de sites e serviços de internet",
    "14.01": "Administração de bens e negócios de terceiros",
    "17.09": "Serviços de tradução, interpretação e digitação",
    "20.01": "Serviços de limpeza e conservação",
    "25.01": "Ensino regular pré-escolar, fundamental, médio e superior",
    "28.01": "Serviços de diversão, lazer, entretenimento e congêneres",
    "99.99": "Outros serviços não especificados"
}

# -------------------------------------------
# 📚 Dicionário de impostos de serviço
# -------------------------------------------
IMPOSTOS = {
    "vISS": "ISSQN",
    "vPIS": "PIS",
    "vCOFINS": "COFINS",
    "vIR": "IRRF",
    "vCSLL": "CSLL",
    "vINSS": "INSS",
}

# -------------------------------------------
# 🔍 Funções auxiliares
# -------------------------------------------
def localname(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag

def try_float(s):
    try:
        if s is None:
            return 0.0
        s = str(s).replace(",", ".").strip()
        return float(s) if s else 0.0
    except:
        return 0.0

@st.cache_data(show_spinner=False)
def get_municipio_nome(codigo_ibge):
    """Converte código IBGE em nome do município (via API IBGE)."""
    try:
        if not codigo_ibge:
            return "Não identificado"
        codigo_ibge = str(int(codigo_ibge))
        url = f"https://servicodados.ibge.gov.br/api/v1/localidades/municipios/{codigo_ibge}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            nome = data["nome"]
            uf = data["microrregiao"]["mesorregiao"]["UF"]["sigla"]
            return f"{nome}/{uf}"
    except Exception:
        pass
    return "Não identificado"

# -------------------------------------------
# 🧠 Função principal de leitura
# -------------------------------------------
def parse_nfse_xml(content: bytes):
    """Lê XML de NFS-e e retorna dados principais."""
    root = ET.fromstring(content)
    parent_map = {c: p for p in root.iter() for c in p}

    data = {
        "numero_nota": None,
        "data_emissao": None,
        "nome_prestador": None,
        "nome_tomador": None,
        "codigo_servico": None,
        "descricao_servico": None,
        "codigo_municipio_tomador": None,
        "municipio_tomador": None,
        **{v: 0.0 for v in IMPOSTOS.values()},
    }

    prestador_name_tags = {
        "RazaoSocialPrestador", "NomePrestador", "xNomePrestador",
        "RazaoSocial", "xNome", "NomePrestadorServico", "Nome", "NomeEmpresarial"
    }
    tomador_name_tags = {
        "RazaoSocialTomador", "NomeTomador", "xNomeTomador",
        "RazaoSocial", "xNome", "NomeTomadorServico", "Nome", "NomeEmpresarial"
    }

    def ancestor_contains(elem, keyword):
        node = parent_map.get(elem)
        while node is not None:
            if keyword.lower() in localname(node.tag).lower():
                return True
            node = parent_map.get(node)
        return False

    for elem in root.iter():
        tag = localname(elem.tag)
        text = elem.text.strip() if elem.text else ""

        # --- Nomes ---
        if tag in prestador_name_tags:
            if ancestor_contains(elem, "prestador"):
                if not data["nome_prestador"]:
                    data["nome_prestador"] = text
                continue
        if tag in tomador_name_tags:
            if ancestor_contains(elem, "tomador"):
                if not data["nome_tomador"]:
                    data["nome_tomador"] = text
                continue

        # --- Municipio tomador ---
        if tag in ("CodigoMunicipioTomador", "cMun", "CodigoMunicipio"):
            data["codigo_municipio_tomador"] = text
            data["municipio_tomador"] = get_municipio_nome(text)
            continue

        # --- Dados da nota ---
        if tag in ("Numero", "nNFSe", "NumeroNfse"):
            data["numero_nota"] = text
            continue
        if tag in ("DataEmissao", "dEmi", "DataHoraEmissao"):
            data["data_emissao"] = text
            continue
        if tag in ("ItemListaServico", "CodigoServico"):
            data["codigo_servico"] = text
            data["descricao_servico"] = CODIGOS_SERVICO.get(text, "Não identificado")
            continue
        if tag in ("Discriminacao", "DescricaoServico", "Descricao"):
            if not data["descricao_servico"] or data["descricao_servico"] == "Não identificado":
                data["descricao_servico"] = text
            continue

        # --- Impostos ---
        if tag in ("ValorIss", "vISSQN", "vISS"):
            data["ISSQN"] += try_float(text)
            continue
        if tag in ("ValorPis", "vPIS"):
            data["PIS"] += try_float(text)
            continue
        if tag in ("ValorCofins", "vCOFINS"):
            data["COFINS"] += try_float(text)
            continue
        if tag in ("ValorIr", "vIR"):
            data["IRRF"] += try_float(text)
            continue
        if tag in ("ValorCsll", "vCSLL"):
            data["CSLL"] += try_float(text)
            continue
        if tag in ("ValorInss", "vINSS"):
            data["INSS"] += try_float(text)
            continue

    # Fallbacks de nome se não achou nas tags diretas
    if not data["nome_prestador"]:
        for elem in root.iter():
            if ancestor_contains(elem, "prestador"):
                data["nome_prestador"] = elem.text.strip() if elem.text else ""
                break
    if not data["nome_tomador"]:
        for elem in root.iter():
            if ancestor_contains(elem, "tomador"):
                data["nome_tomador"] = elem.text.strip() if elem.text else ""
                break

    return data

# -------------------------------------------
# 📤 Upload dos XMLs
# -------------------------------------------
uploaded_files = st.file_uploader("Envie um ou mais arquivos XML de NFS-e", type="xml", accept_multiple_files=True)

if uploaded_files:
    registros = []
    erros = []

    for f in uploaded_files:
        try:
            dados = parse_nfse_xml(f.read())
            dados["arquivo"] = f.name
            registros.append(dados)
        except Exception as e:
            erros.append((f.name, str(e)))

    if erros:
        with st.expander("⚠️ Arquivos com erro de leitura"):
            for nome, msg in erros:
                st.write(f"**{nome}** — {msg}")

    if registros:
        df = pd.DataFrame(registros).drop_duplicates()

        # -------------------------------------------
        # 1️⃣ Prestadores e Tomadores
        # -------------------------------------------
        st.subheader("🏢 Prestadores e Tomadores Identificados")
        st.dataframe(df[["nome_prestador", "nome_tomador"]].drop_duplicates(), use_container_width=True)

        # -------------------------------------------
        # 2️⃣ Métricas Gerais
        # -------------------------------------------
        st.subheader("📊 Resumo das Notas")
        col1, col2, col3 = st.columns(3)
        col1.metric("Notas Processadas", len(df))
        col2.metric("Municípios Tomadores Distintos", df["municipio_tomador"].nunique())
        col3.metric("Prestadores Identificados", df["nome_prestador"].nunique())

        # -------------------------------------------
        # 3️⃣ Impostos
        # -------------------------------------------
        st.subheader("💰 Totais de Impostos Retidos")
        for imp in IMPOSTOS.values():
            total = df[imp].sum()
            if total > 0:
                st.markdown(f"""
                <div style='background-color:#F8F9FB;padding:12px;border-radius:10px;margin-bottom:6px;border:1px solid #E5E8EC'>
                    <b>{imp}</b><br>
                    💵 <b>Total:</b> R$ {total:,.2f}
                </div>
                """, unsafe_allow_html=True)

        # -------------------------------------------
        # 4️⃣ Tipos de Serviço
        # -------------------------------------------
        st.subheader("🧾 Tipos de Serviço")
        servicos = df.groupby(["codigo_servico", "descricao_servico"]).size().reset_index(name="Quantidade")
        st.dataframe(servicos, use_container_width=True)

        # -------------------------------------------
        # 5️⃣ Detalhes
        # -------------------------------------------
        st.subheader("📋 Detalhes das Notas")
        st.dataframe(df, use_container_width=True)

        # -------------------------------------------
        # 6️⃣ Download CSV
        # -------------------------------------------
        csv = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button("💾 Baixar CSV consolidado", csv, "analise_nfse.csv", "text/csv")

else:
    st.info("Envie arquivos XML de NFS-e para começar a análise.")
