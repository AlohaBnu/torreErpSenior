import io
import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st
import requests

# -------------------------------------------
# 🧩 CONFIGURAÇÃO GERAL
# -------------------------------------------
st.set_page_config(page_title="Analisador de XML NF-e", page_icon="🧾", layout="wide")
st.title("🧾 Analisador Inteligente de XML de Notas Fiscais")

st.markdown("""
Analise **arquivos XML de NF-e** e visualize:
- 📇 Perfil da empresa (porte, regime tributário, segmento via API da Receita)  
- 💰 Impostos encontrados  
- 🧾 CFOPs utilizados  
- 📋 Detalhes por nota  
""")

# -------------------------------------------
# 📚 Dicionário dos principais impostos
# -------------------------------------------
IMPOSTOS = {
    "ICMS": "Imposto sobre Circulação de Mercadorias e Serviços",
    "ICMS-ST": "ICMS Substituição Tributária",
    "IPI": "Imposto sobre Produtos Industrializados",
    "PIS": "Programa de Integração Social",
    "COFINS": "Contribuição para Financiamento da Seguridade Social",
    "ISSQN": "Imposto Sobre Serviços de Qualquer Natureza",
    "TotTrib": "Valor Total dos Tributos"
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
def get_empresa_info(cnpj):
    """
    Busca dados reais da empresa via API ReceitaWS.
    Retorna porte, regime tributário estimado e segmento (CNAE principal).
    """
    try:
        cnpj = "".join(filter(str.isdigit, str(cnpj)))
        if len(cnpj) != 14:
            return {"porte": "Não identificado", "regime": "Não identificado", "segmento": "Não identificado"}

        url = f"https://www.receitaws.com.br/v1/cnpj/{cnpj}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            dados = response.json()

            porte = dados.get("porte", "Não informado")
            regime = dados.get("opcao_pelo_simples", False)
            regime_texto = "Simples Nacional" if regime else "Lucro Presumido / Real"

            segmento = dados.get("atividade_principal", [{"text": "Não informado"}])[0]["text"]

            return {
                "porte": porte or "Não identificado",
                "regime": regime_texto,
                "segmento": segmento or "Não identificado"
            }
        else:
            return {"porte": "Erro API", "regime": "Erro API", "segmento": "Erro API"}
    except Exception as e:
        return {"porte": "Erro", "regime": "Erro", "segmento": str(e)}

def parse_xml(content: bytes):
    """Lê XML e retorna metadados + valores de impostos + CFOP + dados empresa"""
    root = ET.fromstring(content)
    data = {
        "emitente": None,
        "cnpj": None,
        "numero": None,
        "data": None,
        "CFOPs": set(),
        **{k: 0.0 for k in IMPOSTOS.keys()}
    }

    for e in root.iter():
        tag = localname(e.tag)
        if tag == "xNome":
            data["emitente"] = e.text
        elif tag == "CNPJ":
            data["cnpj"] = e.text
        elif tag == "nNF":
            data["numero"] = e.text
        elif tag in ("dhEmi", "dEmi"):
            data["data"] = e.text
        elif tag == "CFOP":
            data["CFOPs"].add(e.text)

        # impostos
        if tag == "vICMS":
            data["ICMS"] += try_float(e.text)
        elif tag in ("vICMSST", "vICMSSTRet"):
            data["ICMS-ST"] += try_float(e.text)
        elif tag == "vIPI":
            data["IPI"] += try_float(e.text)
        elif tag == "vPIS":
            data["PIS"] += try_float(e.text)
        elif tag == "vCOFINS":
            data["COFINS"] += try_float(e.text)
        elif tag == "vISSQN":
            data["ISSQN"] += try_float(e.text)
        elif tag == "vTotTrib":
            data["TotTrib"] += try_float(e.text)

    data["CFOPs"] = ", ".join(sorted(data["CFOPs"]))

    # 📦 Enriquecimento com dados reais da API ReceitaWS
    empresa_info = get_empresa_info(data["cnpj"])
    data["porte"] = empresa_info["porte"]
    data["regime_tributario"] = empresa_info["regime"]
    data["segmento"] = empresa_info["segmento"]

    return data

# -------------------------------------------
# 📤 Upload dos XMLs
# -------------------------------------------
uploaded_files = st.file_uploader("Envie um ou mais arquivos XML", type="xml", accept_multiple_files=True)

if uploaded_files:
    registros = []
    erros = []

    for f in uploaded_files:
        try:
            dados = parse_xml(f.read())
            dados["arquivo"] = f.name
            registros.append(dados)
        except Exception as e:
            erros.append((f.name, str(e)))

    if erros:
        with st.expander("⚠️ Arquivos com erro de leitura"):
            for nome, msg in erros:
                st.write(f"**{nome}** — {msg}")

    if registros:
        df = pd.DataFrame(registros)

        # -------------------------------------------
        # 1️⃣ Perfil da Empresa
        # -------------------------------------------
        st.subheader("🏢 Perfil das Empresas (Dados Receita)")
        perfil_df = df[["emitente", "cnpj", "porte", "regime_tributario", "segmento"]].astype(str).drop_duplicates()
        st.dataframe(perfil_df, use_container_width=True)

        # -------------------------------------------
        # 2️⃣ Resumo Geral
        # -------------------------------------------
        st.subheader("📊 Resumo Geral")
        col1, col2 = st.columns(2)
        col1.metric("Notas processadas", len(df))
        col2.metric("Impostos identificados", sum(df[imp].sum() > 0 for imp in IMPOSTOS))

        # -------------------------------------------
        # 3️⃣ Impostos encontrados
        # -------------------------------------------
        impostos_encontrados = [imp for imp in IMPOSTOS if df[imp].sum() > 0]
        if impostos_encontrados:
            st.subheader("💰 Impostos Identificados")
            for imp in impostos_encontrados:
                valor_total = df[imp].sum()
                descricao = IMPOSTOS[imp]
                st.markdown(f"""
                <div style='background-color:#F8F9FB;padding:12px;border-radius:10px;margin-bottom:6px;border:1px solid #E5E8EC'>
                    <b>{imp}</b> — {descricao}<br>
                    💵 <b>Total:</b> R$ {valor_total:,.2f}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Nenhum imposto foi identificado.")

        # -------------------------------------------
        # 4️⃣ CFOPs utilizados
        # -------------------------------------------
        st.subheader("🧾 CFOPs Utilizados")
        cfops = []
        for c in df["CFOPs"]:
            if c:
                cfops.extend(c.split(", "))
        if cfops:
            cfop_df = pd.DataFrame(pd.Series(cfops).value_counts().reset_index())
            cfop_df.columns = ["CFOP", "Quantidade"]
            st.dataframe(cfop_df, use_container_width=True)
        else:
            st.info("Nenhum CFOP encontrado.")

        # -------------------------------------------
        # 5️⃣ Detalhes completos
        # -------------------------------------------
        st.subheader("📋 Detalhes por Nota Fiscal")
        st.dataframe(df, use_container_width=True)

        # -------------------------------------------
        # 6️⃣ Download CSV
        # -------------------------------------------
        csv = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "💾 Baixar CSV consolidado",
            csv,
            "analise_xml_notas.csv",
            "text/csv",
        )
else:
    st.info("Envie arquivos XML para começar a análise.")
