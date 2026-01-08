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

# 3. Carregar Base de Alimentos (Excel GitHub)
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

# --- FUNÇÃO DE LEITURA COM CACHE ---
@st.cache_data(ttl=120)
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
        
        # Opções da lista + opção de adicionar novo
        opcoes_alimentos = list(df_alimentos['ALIMENTO'].unique())
        
        alimento_sel = st.selectbox(
            "Pesquisar Alimento:", 
            options=opcoes_alimentos, 
            index=None, 
            placeholder="Escreva para procurar...",
            help="Se não encontrar, use o botão abaixo para adicionar."
        )

        # Botão para expandir formulário de novo alimento
        add_novo = st.checkbox("➕ Não encontrei? Adicionar novo alimento à base")

        if add_novo:
            st.markdown("---")
            st.info("Preencha os dados (por 100g ou dose) para guardar no Back Desk.")
            with st.form("form_novo_alimento"):
                n_nome = st.text_input("Nome do Alimento:")
                c_kcal, c_prot = st.columns(2)
                n_kcal = c_kcal.number_input("Kcal", min_value=0.0, step=1.0)
                n_prot = c_prot.number_input("Proteína (g)", min_value=0.0, step=0.1)
                
                c_hid, c_lip = st.columns(2)
                n_hid = c_hid.number_input("Hidratos (g)", min_value=0.0, step=0.1)
                n_lip = c_lip.number_input("Lípidos (g)", min_value=0.0, step=0.1)
                
                c_acu, c_fib = st.columns(2)
                n_acu = c_acu.number_input("Açúcar (g)", min_value=0.0, step=0.1)
                n_fib = c_fib.number_input("Fibras (g)", min_value=0.0, step=0.1)
                
                n_sal = st.number_input("Sal (g)", min_value=0.0, step=0.01)
                
                if st.form_submit_button("💾 GUARDAR NO BACK DESK E REGISTAR"):
                    if n_nome:
                        try:
                            # 1. Gravar na aba de Novos Alimentos
                            novo_alimento_df = pd.DataFrame([{
                                "Alimento": n_nome, "Kcal": n_kcal, "Proteina": n_prot, 
                                "Hidratos": n_hid, "Lipidos": n_lip, "Acucar": n_acu, 
                                "Fibras": n_fib, "Sal": n_sal
                            }])
                            df_novos_base = get_data_cached("Novos_Alimentos")
                            conn.update(worksheet="Novos_Alimentos", data=pd.concat([df_novos_base, novo_alimento_df], ignore_index=True))
                            
                            # 2. Registar no diário de hoje
                            nova_linha_diario = pd.DataFrame([{
                                "Data": str(data_sel), "Utilizador": user, "Alimento": n_nome,
                                "Kcal": n_kcal, "Proteina": n_prot, "Hidratos": n_hid, 
                                "Lipidos": n_lip, "Acucar": n_acu, "Fibras": n_fib, "Sal": n_sal
                            }])
                            st.cache_data.clear()
                            df_diario_base = conn.read(worksheet="Sheet1", ttl=0)
                            conn.update(worksheet="Sheet1", data=pd.concat([df_diario_base, nova_linha_diario], ignore_index=True))
                            
                            st.success(f"✅ {n_nome} guardado e registado!")
                            time.sleep(1)
                            st.rerun()
                        except:
                            st.error("Erro ao comunicar com o Sheets. Verifique a aba 'Novos_Alimentos'.")
                    else:
                        st.warning("Por favor, dê um nome ao alimento
