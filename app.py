import streamlit as st
from pages.bd.conexao import select, execute

st.write(select())
st.write(execute())