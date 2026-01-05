import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from datetime import date
import os

# Configuração da Página
st.set_page_config(page_title="Nutri Control Mia & JC", page_icon="🍎")

# 1. Configurar Gemini (IA)
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("Chave API não configurada nos Secrets do Streamlit!")

# 2. Funções de Dados
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        cols = ['Proteína', 'Hidratos', '(açúcar)', 'Lípidos', 'Fibras', 'Sal', 'Calorias']
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Erro ao ler alimentos.xlsx: {e}")
        return pd.DataFrame()

def guardar_registo(utilizador, alimento, kcal, prot, hid, gord, data_sel):
    novo_dado = pd.DataFrame([{
        "Data": data_sel,
        "Utilizador": utilizador,
        "Alimento": alimento,
        "Kcal": kcal,
        "Proteína": prot,
        "Hidratos": hid,
        "Gordura": gord
    }])
    # Nota: O Streamlit Cloud tem limitações a escrever ficheiros no GitHub diretamente.
    # Para uso imediato, vamos usar o estado da sessão (session_state).
    if 'historico' not in st.session_state:
        st.session_state.historico = pd.DataFrame()
    st.session_state.historico = pd.concat([st.session_state.historico, novo_dado], ignore_index=True)

# Interface
st.title("🍎 Nutri Control")
user = st.sidebar.radio("Utilizador:", ["Mia", "João Carlos"])
data_escolhida = st.sidebar.date_input("Selecionar Dia:", date.today())

df_alimentos = load_data()

# --- ABAS ---
tab1, tab2, tab3 = st.tabs(["📝 Registar", "📸 Foto/IA", "📅 Histórico"])

with tab1:
    if not df_alimentos.empty:
        alimento_nome = st.selectbox("Escolha o alimento:", df_alimentos['ALIMENTO'].unique())
        row = df_alimentos[df_alimentos['ALIMENTO'] == alimento_nome].iloc[0]
        
        qtd = st.number_input("Quantidade (g ou ml):", min_value=1.0, value=100.0)
        fator = qtd / 100
        
        c1, c2, c3 = st.columns(3)
        v_kcal = row['Calorias'] * fator
        v_prot = row['Proteína'] * fator
        v_hid = row['Hidratos'] * fator
        v_gord = row['Lípidos'] * fator
        
        c1.metric("Energia", f"{v_kcal:.1f} kcal")
        c2.metric("Proteína", f"{v_prot:.1f} g")
        c3.metric("Hidratos", f"{v_hid:.1f} g")
        
        if st.button("Confirmar Registo"):
            guardar_registo(user, alimento_nome, v_kcal, v_prot, v_hid, v_gord, data_escolhida)
            st.success(f"Registo guardado para o dia {data_escolhida}!")

with tab2:
    st.subheader("Adicionar por Foto (Gemini)")
    foto = st.camera_input("Tire foto ao rótulo")
    if foto:
        img = Image.open(foto)
        with st.spinner("A analisar..."):
            prompt = "Extrai os valores nutricionais por 100g desta imagem: Calorias, Proteína, Hidratos, Lípidos. Responde de forma curta."
            response = model.generate_content([prompt, img])
            st.write(response.text)
            st.info("Dica: Use estes valores para adicionar um novo item ao seu Excel no computador.")

with tab3:
    st.subheader(f"Registo de {user}")
    if 'historico' in st.session_state and not st.session_state.historico.empty:
        hist = st.session_state.historico
        # Filtrar por utilizador e data
        filtro = hist[(hist['Utilizador'] == user) & (hist['Data'] == data_escolhida)]
        if not filtro.empty:
            st.dataframe(filtro)
            st.metric("Total Calorias do Dia", f"{filtro['Kcal'].sum():.1f} kcal")
        else:
            st.write("Sem registos para este dia.")
    else:
        st.write("O histórico está vazio.")
