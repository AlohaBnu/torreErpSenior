import streamlit as st
import pandas as pd

st.set_page_config(page_title="Meu App Streamlit", layout="wide")

st.title("🚀 Meu Primeiro App Streamlit")
st.write("Olá! Este app está rodando no Streamlit Cloud 😄")

data = pd.DataFrame({
    "Nome": ["Ana", "Bruno", "Carlos"],
    "Idade": [23, 35, 29],
    "Cidade": ["Florianópolis", "Curitiba", "São Paulo"]
})

st.dataframe(data)