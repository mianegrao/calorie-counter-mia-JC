import streamlit as st
import pandas as pd
from datetime import date

# Configuração da página para parecer uma App de telemóvel
st.set_page_config(page_title="My Nutrition App", layout="centered")

# --- CARREGAR DADOS ---
@st.cache_data
def load_data():
    # Carrega a sua lista de alimentos do Excel (convertido para CSV ou lido diretamente)
    df = pd.read_csv("alimentos.csv") 
    return df

df_alimentos = load_data()

# --- INTERFACE ---
st.title("🍎 Nutrition Tracker")

user = st.sidebar.selectbox("Quem está a usar?", ["Selecione", "Eu", "João Carlos"])

if user != "Selecione":
    st.header(f"Olá, {user}!")
    
    tab1, tab2, tab3 = st.tabs(["Registo Diário", "Adicionar Novo", "Histórico"])

    with tab1:
        st.subheader("O que comeu hoje?")
        alimento_escolhido = st.selectbox("Selecione o Alimento", df_alimentos['Alimento/Marca'].unique())
        
        # Obter dados do alimento selecionado
        dados_alimento = df_alimentos[df_alimentos['Alimento/Marca'] == alimento_escolhido].iloc[0]
        
        peso = st.number_input("Quantidade (g ou ml)", min_value=1, value=100)
        
        if st.button("Registar Refeição"):
            # Cálculo proporcional
            fator = peso / 100
            nova_entrada = {
                "Data": date.today(),
                "Alimento": alimento_escolhido,
                "Kcal": dados_alimento['Energia (kcal)'] * fator,
                "Proteína": dados_alimento['Proteínas (g)'] * fator,
                "Lípidos": dados_alimento['Lípidos (g)'] * fator,
                "Açúcares": dados_alimento['Açúcares (g)'] * fator,
                "Sal": dados_alimento['Sal (g)'] * fator
            }
            st.success(f"Registado: {alimento_escolhido} ({peso}g)")
            # Aqui o código guardaria num ficheiro CSV de histórico

    with tab2:
        st.subheader("📸 Adicionar por Foto")
        foto = st.camera_input("Tire foto ao rótulo nutricional")
        if foto:
            st.info("O Gemini está a analisar a imagem... (Função de IA integrada)")
            # Aqui entra a chamada à API do Gemini para ler o rótulo

    with tab3:
        st.subheader("Resumo do Dia")
        # Exemplo de visualização de totais
        col1, col2, col3 = st.columns(3)
        col1.metric("Calorias", "1540 kcal")
        col2.metric("Proteína", "85g")
        col3.metric("Gordura", "45g")