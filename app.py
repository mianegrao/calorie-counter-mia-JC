import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import date
from streamlit_gsheets import GSheetsConnection
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

# CSS para tornar os botões de ação pequenos e alinhados
st.markdown("""
    <style>
    div[data-testid="stColumn"] button {
        padding: 2px 10px;
        height: 28px;
        min-height: 28px;
        width: auto;
        font-size: 14px;
        border-radius: 5px;
    }
    div[data-testid="stVerticalBlock"] > div {
        gap: 0rem;
    }
    </style>
    """, unsafe_allow_html=True)

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

conn = st.connection("gsheets", type=GSheetsConnection)

# --- ESTADO DA SESSÃO ---
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
    st.session_state.edit_index = None
    st.session_state.edit_alimento = None
    st.session_state.edit_qtd = 1.0

# --- FUNÇÕES DE SUPORTE ---
def safe_update(worksheet, data, max_retries=3):
    for i in range(max_retries):
        try:
            df_to_save = data.copy()
            if "Qtd/Coef" not in df_to_save.columns: df_to_save["Qtd/Coef"] = 1.0
            conn.update(worksheet=worksheet, data=df_to_save)
            return True
        except:
            if i < max_retries - 1: time.sleep(1)
            else: return False
    return False

@st.cache_data(ttl=60)
def get_data_sheets(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df is None or df.empty: return pd.DataFrame()
        df = df.dropna(how='all').reset_index(drop=True)
        mapeamento = {'Proteina': 'Proteína', 'Acucar': '(açúcar)', 'Açúcar': '(açúcar)', 'Lipidos': 'Lípidos', 'Saturadas': '(satur.)', 'Fibra': 'Fibras', 'Kcal': 'Calorias'}
        return df.rename(columns=mapeamento)
    except: return pd.DataFrame()

@st.cache_data(ttl=600)
def load_combined_food_data():
    try:
        df_excel = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        df_excel.columns = df_excel.columns.str.strip()
    except: df_excel = pd.DataFrame()
    df_sheets = get_data_sheets("Novos_Alimentos")
    df_combined = pd.concat([df_excel, df_sheets], axis=0, ignore_index=True)
    return df_combined.drop_duplicates(subset=['ALIMENTO'], keep='last').sort_values(by='ALIMENTO')

df_alimentos = load_combined_food_data()

# --- INTERFACE ---
user = st.sidebar.selectbox("Utilizador:", ["Mia", "João Carlos", "Jorge", "Celeste"])
data_sel = st.sidebar.date_input("Data:", date.today())
page = st.sidebar.selectbox("Ir para:", ["Diário / Registo", "Estatísticas", "Exercício", "Câmara IA"])

if page == "Diário / Registo":
    st.header(f"📝 Diário de {user}")
    col_form, col_resumo = st.columns([1, 2.8])
    
    with col_form:
        if st.session_state.edit_mode:
            st.subheader("✏️ Editar")
            alimento_sel = st.session_state.edit_alimento
            st.warning(f"A alterar: **{alimento_sel}**")
        else:
            st.subheader("Novo Registo")
            opcoes = df_alimentos['ALIMENTO'].unique() if not df_alimentos.empty else []
            alimento_sel = st.selectbox("Alimento:", options=opcoes, index=None)

        if alimento_sel:
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento_sel].iloc[0]
            def_q = st.session_state.edit_qtd if st.session_state.edit_mode else 1.0
            qtd = st.number_input("Coeficiente:", min_value=0.01, value=float(def_q), step=0.05)
            
            def get_v(names, q):
                for n in names:
                    if n in row and pd.notnull(row[n]): return float(row[n]) * q
                return 0.0

            vals = {"Proteína": get_v(['Proteína', 'Proteina'], qtd), "Hidratos": get_v(['Hidratos'], qtd),
                    "(açúcar)": get_v(['(açúcar)', 'Acucar'], qtd), "Lípidos": get_v(['Lípidos', 'Lipidos'], qtd),
                    "Fibras": get_v(['Fibras', 'Fibra'], qtd), "Calorias": get_v(['Calorias', 'Kcal'], qtd)}

            st.markdown(f"**{vals['Calorias']:.0f} Kcal | {vals['Proteína']:.1f}g Prot**")

            if st.session_state.edit_mode:
                if st.button("💾 ATUALIZAR", type="primary", use_container_width=True):
                    df_h = get_data_sheets("Sheet1")
                    for k, v in vals.items(): df_h.at[st.session_state.edit_index, k] = v
                    df_h.at[st.session_state.edit_index, "Qtd/Coef"] = qtd
                    if safe_update("Sheet1", df_h):
                        st.session_state.edit_mode = False
                        st.cache_data.clear(); st.rerun()
                if st.button("Cancelar", use_container_width=True):
                    st.session_state.edit_mode = False; st.rerun()
            else:
                if st.button("✅ CONFIRMAR", type="primary", use_container_width=True):
                    df_h = get_data_sheets("Sheet1")
                    novo = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento_sel, "Qtd/Coef": qtd, **vals}])
                    if safe_update("Sheet1", pd.concat([df_h, novo], ignore_index=True)):
                        st.cache_data.clear(); st.rerun()

    with col_resumo:
        st.subheader(f"Resumo do Dia")
        df_h = get_data_sheets("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            dia_df = df_h[(df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)].copy()
            
            if not dia_df.empty:
                # Cabeçalho ultra compacto
                c = st.columns([0.15, 0.15, 1, 0.4, 0.4, 0.4, 0.4])
                cols_labels = ["", "", "**Alimento**", "**Kcal**", "**Prot**", "**Hid**", "**Fib**"]
                for i, label in enumerate(cols_labels): c[i].markdown(label)
                st.markdown("---")

                for idx, row_dia in dia_df.iterrows():
                    r = st.columns([0.15, 0.15, 1, 0.4, 0.4, 0.4, 0.4])
                    
                    if r[0].button("✏️", key=f"e_{idx}"):
                        st.session_state.edit_mode, st.session_state.edit_index = True, idx
                        st.session_state.edit_alimento = row_dia['Alimento']
                        st.session_state.edit_qtd = row_dia.get('Qtd/Coef', 1.0)
                        st.rerun()
                    
                    if r[1].button("🗑️", key=f"d_{idx}"):
                        if safe_update("Sheet1", df_h.drop(idx)):
                            st.cache_data.clear(); st.rerun()
                    
                    r[2].write(row_dia['Alimento'])
                    r[3].write(f"{row_dia['Calorias']:.0f}")
                    r[4].write(f"{row_dia['Proteína']:.1f}g")
                    r[5].write(f"{row_dia['Hidratos']:.1f}g")
                    r[6].write(f"{row_dia['Fibras']:.1f}g")

                st.markdown("---")
                t = st.columns([1.3, 0.4, 0.4, 0.4, 0.4])
                t[0].write("**TOTAL**")
                t[1].write(f"**{dia_df['Calorias'].sum():.0f}**")
                t[2].write(f"**{dia_df['Proteína'].sum():.1f}g**")
                t[3].write(f"**{dia_df['Hidratos'].sum():.1f}g**")
                t[4].write(f"**{dia_df['Fibras'].sum():.1f}g**")
            else:
                st.info("Sem registos hoje.")
