import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from datetime import date, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

# 1. Configurar IA
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

# 2. Conexão Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Carregar Base de Alimentos (GitHub)
@st.cache_data(ttl=600)
def load_food_data():
    try:
        df = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        df.columns = df.columns.str.strip() # Remove espaços extra nos nomes das colunas
        return df
    except:
        return pd.DataFrame()

df_alimentos = load_food_data()

# --- NAVEGAÇÃO LATERAL (Menu de Páginas) ---
st.sidebar.title("🍎 Nutri & Fit Pro")
page = st.sidebar.selectbox("Ir para:", 
    ["Página Inicial / Registo", "Estatísticas & Médias", "Registo de Exercício", "Câmara IA"])

user = st.sidebar.selectbox("Utilizador:", ["Mia", "João Carlos", "Jorge", "Celeste"])
data_sel = st.sidebar.date_input("Data de referência:", date.today())

# --- PÁGINA 1: REGISTO E TOTAIS DO DIA ---
if page == "Página Inicial / Registo":
    st.header(f"📝 Diário de {user}")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Novo Registo")
        if not df_alimentos.empty:
            alimento = st.selectbox("Escolher Alimento:", df_alimentos['ALIMENTO'].unique())
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento].iloc[0]
            
            qtd = st.number_input("Quantidade (Coeficiente/Doses):", min_value=0.01, value=1.00, step=0.05)
            
            # Função para ler valor do excel independentemente de acentos
            def get_v(names):
                for n in names:
                    if n in row: return float(row[n]) * qtd
                return 0.0

            vals = {
                "Kcal": get_v(['Calorias', 'Kcal']),
                "Proteina": get_v(['Proteína', 'Proteina']),
                "Hidratos": get_v(['Hidratos']),
                "Lipidos": get_v(['Lípidos', 'Lipidos']),
                "Acucar": get_v(['(açúcar)', 'Acucar']),
                "Fibras": get_v(['Fibras']),
                "Sal": get_v(['Sal'])
            }

            st.write(f"**A adicionar:** {vals['Kcal']:.1f} kcal | {vals['Proteina']:.1f}g Prot")

            if st.button("CONFIRMAR E GRAVAR"):
                try:
                    nova_linha = pd.DataFrame([{
                        "Data": str(data_sel), "Utilizador": user, "Alimento": alimento,
                        **{k: round(v, 2) for k, v in vals.items()}
                    }])
                    df_atual = conn.read(ttl=0).dropna(how='all')
                    df_final = pd.concat([df_atual, nova_linha], ignore_index=True)
                    conn.update(data=df_final)
                    st.success("Gravado com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao gravar: {e}")

    with col2:
        st.subheader(f"Totais de {data_sel}")
        try:
            df_hist = conn.read(ttl=0).dropna(how='all')
            if not df_hist.empty:
                df_hist['Data'] = df_hist['Data'].astype(str)
                dia_df = df_hist[(df_hist['Data'] == str(data_sel)) & (df_hist['Utilizador'] == user)]
                
                if not dia_df.empty:
                    st.dataframe(dia_df[["Alimento", "Kcal", "Proteina", "Hidratos", "Lipidos"]], use_container_width=True)
                    
                    # Soma de todos os macronutrientes
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Energia", f"{dia_df['Kcal'].sum():.0f} kcal")
                    m2.metric("Proteína", f"{dia_df['Proteina'].sum():.1f}g")
                    m3.metric("Hidratos", f"{dia_df['Hidratos'].sum():.1f}g")
                    m4.metric("Lípidos", f"{dia_df['Lipidos'].sum():.1f}g")

                    if st.button("🗑️ Apagar último registo"):
                        df_final = df
