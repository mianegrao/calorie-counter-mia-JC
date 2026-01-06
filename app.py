import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from datetime import date
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

# 1. Configurar IA
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

# 2. Conexão Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Carregar Base de Alimentos
@st.cache_data(ttl=600)
def load_food_data():
    try:
        df = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

df_alimentos = load_food_data()

# --- LÓGICA DE UTILIZADOR VIA URL ---
query_params = st.query_params
user_param = query_params.get("user", "Mia")
lista_users = ["Mia", "João Carlos", "Jorge", "Celeste"]
def_idx = lista_users.index(user_param) if user_param in lista_users else 0

# --- NAVEGAÇÃO LATERAL ---
st.sidebar.title("🍎 Nutri & Fit Pro")

# Botão de Retroceder rápido na Sidebar
if st.sidebar.button("⬅️ VOLTAR AO INÍCIO"):
    st.session_state.page = "Página Inicial / Registo"
    st.rerun()

if "page" not in st.session_state:
    st.session_state.page = "Página Inicial / Registo"

page = st.sidebar.selectbox("Ir para:", 
    ["Página Inicial / Registo", "Estatísticas & Médias", "Registo de Exercício", "Câmara IA"],
    key="nav_select", index=["Página Inicial / Registo", "Estatísticas & Médias", "Registo de Exercício", "Câmara IA"].index(st.session_state.page))

user = st.sidebar.selectbox("Utilizador:", lista_users, index=def_idx)
data_sel = st.sidebar.date_input("Data:", date.today())

def get_data(worksheet_name="Sheet1"):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        return df.dropna(how='all') if df is not None else pd.DataFrame()
    except: return pd.DataFrame()

# --- PÁGINA 1: REGISTO E TOTAIS ---
if page == "Página Inicial / Registo":
    st.header(f"📝 Diário de {user}")
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Novo Registo")
        if not df_alimentos.empty:
            alimento = st.selectbox("Escolher Alimento:", df_alimentos['ALIMENTO'].unique())
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento].iloc[0]
            qtd = st.number_input("Quantidade (Coeficiente):", min_value=0.01, value=1.00, step=0.05)
            
            def get_v(names):
                for n in names:
                    if n in row: return float(row[n]) * qtd
                return 0.0

            vals = {
                "Kcal": get_v(['Calorias', 'Kcal']),
                "Proteina": get_v(['Proteína', 'Proteina']),
                "Hidratos": get_v(['Hidratos']),
                "Lipidos": get_v(['Lípidos', 'Lipidos']),
                "Acucar": get_v(['(açúcar)', 'Acucar', 'Açúcar']),
                "Fibras": get_v(['Fibras']),
                "Sal": get_v(['Sal'])
            }
            st.info(f"Cálculo: {vals['Kcal']:.1f} kcal | {vals['Proteina']:.1f}g Prot")

            if st.button("CONFIRMAR E GRAVAR"):
                nova_linha = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento, **{k: round(v, 2) for k, v in vals.items()}}])
                df_f = pd.concat([get_data("Sheet1"), nova_linha], ignore_index=True)
                conn.update(data=df_f)
                st.success("Gravado!")
                st.rerun()

    with col2:
        st.subheader(f"Totais de {data_sel}")
        df_h = get_data("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            dia_df = df_h[(df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)]
            if not dia_df.empty:
                # MOSTRAR TODAS AS COLUNAS (Macros e Açúcar)
                st.dataframe(dia_df[["Alimento", "Kcal", "Proteina", "Hidratos", "Lipidos", "Acucar", "Fibras", "Sal"]], use_container_width=True)
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Energia", f"{dia_df['Kcal'].sum():.0f} kcal")
                m2.metric("Proteína", f"{dia_df['Proteina'].sum():.1f}g")
                m3.metric("Hidratos", f"{dia_df['Hidratos'].sum():.1f}g")
                m4.metric("Lípidos", f"{dia_df['Lipidos'].sum():.1f}g")
                
                m5, m6, m7 = st.columns(3)
                m5.metric("Açúcar", f"{dia_df['Acucar'].sum():.1f}g")
                m6.metric("Fibras", f"{dia_df['Fibras'].sum():.1f}g")
                m7.metric("Sal", f"{dia_df['Sal'].sum():.2f}g")

                if st.button("🗑️ Apagar último"):
                    conn.update(data=df_h.drop(dia_df.index[-1]))
                    st.rerun()

# --- PÁGINA 2: ESTATÍSTICAS ---
elif page == "Estatísticas & Médias":
    st.header("📊 Estatísticas")
    if st.button("⬅️ Voltar"): st.session_state.page = "Página Inicial / Registo"; st.rerun()
    # (Restante código de estatísticas mantido...)

# --- PÁGINA 3: EXERCÍCIO ---
elif page == "Registo de Exercício":
    st.header("🏃 Exercício")
    if st.button("⬅️ Voltar"): st.session_state.page = "Página Inicial / Registo"; st.rerun()
    modalidades = ["Corrida", "Treino de Força", "Remo", "Biking", "Caminhada", "Yoga", "Pilates", "Escadas", "Treino Funcional", "HIIT"]
    tipo = st.selectbox("Modalidade:", modalidades)
    tempo = st.number_input("Duração (min):", min_value=1, value=45)
    if st.button("GRAVAR TREINO"):
        novo_t = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Modalidade": tipo, "Duracao": tempo}])
        df_ex = get_data("Exercicio")
        conn.update(worksheet="Exercicio", data=pd.concat([df_ex, novo_t], ignore_index=True) if not df_ex.empty else novo_t)
        st.success("Treino guardado!")

# --- PÁGINA 4: CÂMARA IA ---
elif page == "Câmara IA":
    st.header("📸 Câmara IA")
    if st.button("⬅️ Voltar"): st.session_state.page = "Página Inicial / Registo"; st.rerun()
    foto = st.camera_input("Foto do rótulo")
    if foto:
        img = Image.open(foto)
        with st.spinner("IA a analisar..."):
            res = model.generate_content(["Extrai os valores por 100g de: Calorias, Proteína, Hidratos, Açúcar, Lípidos, Fibras e Sal. Formata como uma tabela.", img])
            st.markdown(res.text)
