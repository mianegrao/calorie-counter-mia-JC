import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from datetime import date
from streamlit_gsheets import GSheetsConnection
import json
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

# 1. Configurar IA
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

# 2. Conexão Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Carregar Base de Alimentos (Excel GitHub) - Cache de 1 hora
@st.cache_data(ttl=3600)
def load_food_data():
    try:
        df = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=['ALIMENTO'])
        return df.sort_values(by='ALIMENTO')
    except:
        return pd.DataFrame()

df_alimentos = load_food_data()

# --- FUNÇÃO DE LEITURA COM CACHE (Para evitar Erro 429) ---
@st.cache_data(ttl=120) # Guarda os dados por 2 min para não sobrecarregar a Google
def get_data_cached(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        return df.dropna(how='all') if df is not None else pd.DataFrame()
    except:
        return pd.DataFrame()

# --- NAVEGAÇÃO ---
if "page" not in st.session_state:
    st.session_state.page = "Página Inicial / Registo"

query_params = st.query_params
user_param = query_params.get("user", "Mia")
lista_users = ["Mia", "João Carlos", "Jorge", "Celeste"]
def_idx = lista_users.index(user_param) if user_param in lista_users else 0

st.sidebar.title("🍎 Nutri & Fit Pro")
if st.sidebar.button("⬅️ VOLTAR AO INÍCIO"):
    st.session_state.page = "Página Inicial / Registo"
    st.rerun()

page = st.sidebar.selectbox("Ir para:", 
    ["Página Inicial / Registo", "Estatísticas & Médias", "Registo de Exercício", "Câmara IA"], key="nav_main")
user = st.sidebar.selectbox("Utilizador:", lista_users, index=def_idx)
data_sel = st.sidebar.date_input("Data:", date.today())

# --- PÁGINA 1: REGISTO ---
if page == "Página Inicial / Registo":
    st.header(f"📝 Diário de {user}")
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Novo Registo")
        if not df_alimentos.empty:
            alimento = st.selectbox("Pesquisar Alimento:", options=df_alimentos['ALIMENTO'].unique(), index=None, placeholder="Escreva para procurar...")
            
            if alimento:
                row = df_alimentos[df_alimentos['ALIMENTO'] == alimento].iloc[0]
                qtd = st.number_input("Quantidade:", min_value=0.01, value=1.00, step=0.05)
                
                def get_v(names):
                    for n in names:
                        if n in row: return float(row[n]) * qtd
                    return 0.0

                vals = {"Kcal": get_v(['Calorias', 'Kcal']), "Proteina": get_v(['Proteína', 'Proteina']), "Hidratos": get_v(['Hidratos']), "Lipidos": get_v(['Lípidos', 'Lipidos']), "Acucar": get_v(['(açúcar)', 'Acucar', 'Açúcar']), "Fibras": get_v(['Fibras']), "Sal": get_v(['Sal'])}
                st.info(f"✨ {vals['Kcal']:.1f} kcal | {vals['Proteina']:.1f}g Proteína")

                if st.button("CONFIRMAR E GRAVAR"):
                    try:
                        with st.spinner("A guardar..."):
                            nova_linha = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento, **{k: round(v, 2) for k, v in vals.items()}}])
                            # Aqui limpamos a cache para forçar a leitura dos dados novos após gravar
                            st.cache_data.clear() 
                            df_atual = conn.read(worksheet="Sheet1", ttl=0)
                            df_final = pd.concat([df_atual, nova_linha], ignore_index=True)
                            conn.update(data=df_final)
                            st.success("Gravado!")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error("A Google está sobrecarregada. Aguarde 30 segundos e tente de novo.")

    with col2:
        st.subheader(f"Resumo de {data_sel}")
        df_h = get_data_cached("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            dia_df = df_h[(df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)].copy()
            if not dia_df.empty:
                display_df = dia_df[["Alimento", "Kcal", "Proteina", "Hidratos", "Lipidos", "Acucar", "Fibras", "Sal"]].rename(columns={"Proteina": "Proteína", "Lipidos": "Lípidos", "Acucar": "Açúcar"})
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Energia", f"{dia_df['Kcal'].sum():.0f} kcal")
                c2.metric("Proteína", f"{dia_df['Proteina'].sum():.1f}g")
                c3.metric("Açúcar", f"{dia_df['Acucar'].sum():.1f}g")

                if st.button("🗑️ Apagar último"):
                    st.cache_data.clear()
                    df_res = df_h.drop(dia_df.index[-1])
                    conn.update(data=df_res)
                    st.rerun()

# (Restante do código: Estatísticas, Exercício e Câmara usam get_data_cached)
