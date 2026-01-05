{\rtf1\ansi\ansicpg1252\cocoartf2761
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx566\tx1133\tx1700\tx2267\tx2834\tx3401\tx3968\tx4535\tx5102\tx5669\tx6236\tx6803\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import streamlit as st\
import pandas as pd\
from datetime import date\
\
# Configura\'e7\'e3o da p\'e1gina para parecer uma App de telem\'f3vel\
st.set_page_config(page_title="My Nutrition App", layout="centered")\
\
# --- CARREGAR DADOS ---\
@st.cache_data\
def load_data():\
    # Carrega a sua lista de alimentos do Excel (convertido para CSV ou lido diretamente)\
    df = pd.read_csv("alimentos.csv") \
    return df\
\
df_alimentos = load_data()\
\
# --- INTERFACE ---\
st.title("\uc0\u55356 \u57166  Nutrition Tracker")\
\
user = st.sidebar.selectbox("Quem est\'e1 a usar?", ["Selecione", "Eu", "Jo\'e3o Carlos"])\
\
if user != "Selecione":\
    st.header(f"Ol\'e1, \{user\}!")\
    \
    tab1, tab2, tab3 = st.tabs(["Registo Di\'e1rio", "Adicionar Novo", "Hist\'f3rico"])\
\
    with tab1:\
        st.subheader("O que comeu hoje?")\
        alimento_escolhido = st.selectbox("Selecione o Alimento", df_alimentos['Alimento/Marca'].unique())\
        \
        # Obter dados do alimento selecionado\
        dados_alimento = df_alimentos[df_alimentos['Alimento/Marca'] == alimento_escolhido].iloc[0]\
        \
        peso = st.number_input("Quantidade (g ou ml)", min_value=1, value=100)\
        \
        if st.button("Registar Refei\'e7\'e3o"):\
            # C\'e1lculo proporcional\
            fator = peso / 100\
            nova_entrada = \{\
                "Data": date.today(),\
                "Alimento": alimento_escolhido,\
                "Kcal": dados_alimento['Energia (kcal)'] * fator,\
                "Prote\'edna": dados_alimento['Prote\'ednas (g)'] * fator,\
                "L\'edpidos": dados_alimento['L\'edpidos (g)'] * fator,\
                "A\'e7\'facares": dados_alimento['A\'e7\'facares (g)'] * fator,\
                "Sal": dados_alimento['Sal (g)'] * fator\
            \}\
            st.success(f"Registado: \{alimento_escolhido\} (\{peso\}g)")\
            # Aqui o c\'f3digo guardaria num ficheiro CSV de hist\'f3rico\
\
    with tab2:\
        st.subheader("\uc0\u55357 \u56568  Adicionar por Foto")\
        foto = st.camera_input("Tire foto ao r\'f3tulo nutricional")\
        if foto:\
            st.info("O Gemini est\'e1 a analisar a imagem... (Fun\'e7\'e3o de IA integrada)")\
            # Aqui entra a chamada \'e0 API do Gemini para ler o r\'f3tulo\
\
    with tab3:\
        st.subheader("Resumo do Dia")\
        # Exemplo de visualiza\'e7\'e3o de totais\
        col1, col2, col3 = st.columns(3)\
        col1.metric("Calorias", "1540 kcal")\
        col2.metric("Prote\'edna", "85g")\
        col3.metric("Gordura", "45g")}