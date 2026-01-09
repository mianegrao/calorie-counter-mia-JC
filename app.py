import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import date
from streamlit_gsheets import GSheetsConnection
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

conn = st.connection("gsheets", type=GSheetsConnection)

# --- ESTADO DA SESSÃO (Para Edição) ---
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
            if "Qtd/Coef" not in df_to_save.columns:
                df_to_save["Qtd/Coef"] = 1.0
            conn.update(worksheet=worksheet, data=df_to_save)
            return True
        except Exception as e:
            if i < max_retries - 1:
                time.sleep(2)
                continue
            else: raise e
    return False

@st.cache_data(ttl=60)
def get_data_sheets(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df is None or df.empty: return pd.DataFrame()
        df = df.dropna(how='all').reset_index(drop=True)
        mapeamento = {'Proteina': 'Proteína', 'Acucar': '(açúcar)', 'Açúcar': '(açúcar)', 
                      'Lipidos': 'Lípidos', 'Saturadas': '(satur.)', 'Fibra': 'Fibras', 'Kcal': 'Calorias'}
        return df.rename(columns=mapeamento)
    except:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_combined_food_data():
    try:
        df_excel = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        df_excel.columns = df_excel.columns.str.strip()
        df_excel = df_excel.dropna(subset=['ALIMENTO']).reset_index(drop=True)
    except:
        df_excel = pd.DataFrame()
    df_sheets = get_data_sheets("Novos_Alimentos")
    df_combined = pd.concat([df_excel, df_sheets], axis=0, ignore_index=True)
    df_combined = df_combined.loc[:, ~df_combined.columns.duplicated()]
    return df_combined.drop_duplicates(subset=['ALIMENTO'], keep='last').sort_values(by='ALIMENTO')

df_alimentos = load_combined_food_data()

# --- INTERFACE ---
user = st.sidebar.selectbox("Utilizador:", ["Mia", "João Carlos", "Jorge", "Celeste"])
data_sel = st.sidebar.date_input("Data:", date.today())
page = st.sidebar.selectbox("Ir para:", ["Diário / Registo", "Estatísticas", "Exercício", "Câmara IA"])

if page == "Diário / Registo":
    st.header(f"📝 Diário de {user}")
    col_form, col_resumo = st.columns([1, 2.5])
    
    with col_form:
        # ÁREA DE REGISTO / EDIÇÃO
        if st.session_state.edit_mode:
            st.subheader("✏️ Editar")
            alimento_sel = st.session_state.edit_alimento
            st.warning(f"A alterar: **{alimento_sel}**")
        else:
            st.subheader("Novo Registo")
            opcoes = df_alimentos['ALIMENTO'].unique() if not df_alimentos.empty else []
            alimento_sel = st.selectbox("Alimento:", options=opcoes, index=None, placeholder="Escolha um alimento...")

        if alimento_sel:
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento_sel].iloc[0]
            default_qtd = st.session_state.edit_qtd if st.session_state.edit_mode else 1.0
            qtd = st.number_input("Qtd / Coeficiente:", min_value=0.01, value=float(default_qtd), step=0.05)
            
            def get_v(names, q):
                for n in names:
                    if n in row and pd.notnull(row[n]): return float(row[n]) * q
                return 0.0

            vals = {"Proteína": get_v(['Proteína', 'Proteina'], qtd), "Hidratos": get_v(['Hidratos'], qtd),
                    "(açúcar)": get_v(['(açúcar)', 'Acucar'], qtd), "Lípidos": get_v(['Lípidos', 'Lipidos'], qtd),
                    "(satur.)": get_v(['(satur.)', 'Saturadas'], qtd), "Fibras": get_v(['Fibras', 'Fibra'], qtd),
                    "Sal": get_v(['Sal'], qtd), "Calorias": get_v(['Calorias', 'Kcal'], qtd)}

            st.write(f"👉 **{vals['Calorias']:.0f} Kcal | {vals['Proteína']:.1f}g Prot**")

            if st.session_state.edit_mode:
                if st.button("💾 ATUALIZAR", type="primary", use_container_width=True):
                    df_h = get_data_sheets("Sheet1")
                    idx = st.session_state.edit_index
                    for k, v in vals.items(): df_h.at[idx, k] = v
                    df_h.at[idx, "Qtd/Coef"] = qtd
                    if safe_update("Sheet1", df_h):
                        st.session_state.edit_mode = False
                        st.cache_data.clear()
                        st.rerun()
                if st.button("Cancelar", use_container_width=True):
                    st.session_state.edit_mode = False
                    st.rerun()
            else:
                if st.button("✅ CONFIRMAR", type="primary", use_container_width=True):
                    df_h = get_data_sheets("Sheet1")
                    novo_reg = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento_sel, "Qtd/Coef": qtd, **vals}])
                    if safe_update("Sheet1", pd.concat([df_h, novo_reg], ignore_index=True)):
                        st.cache_data.clear()
                        st.rerun()

    with col_resumo:
        # TABELA DE REGISTOS COM ÍCONES ANTES DO NOME
        st.subheader(f"Resumo do Dia")
        df_h = get_data_sheets("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            dia_mask = (df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)
            dia_df = df_h[dia_mask].copy()
            
            if not dia_df.empty:
                # Cabeçalho da Tabela Customizada
                h_cols = st.columns([0.2, 0.2, 1.2, 0.5, 0.5, 0.5, 0.5])
                h_cols[2].write("**Alimento**")
                h_cols[3].write("**Kcal**")
                h_cols[4].write("**Prot.**")
                h_cols[5].write("**Hid.**")
                h_cols[6].write("**Fib.**")
                st.divider()

                # Linhas da Tabela
                for idx, row_dia in dia_df.iterrows():
                    r_cols = st.columns([0.2, 0.2, 1.2, 0.5, 0.5, 0.5, 0.5])
                    
                    # Ícone Editar (Lápis)
                    if r_cols[0].button("✏️", key=f"ed_{idx}", help="Editar"):
                        st.session_state.edit_mode = True
                        st.session_state.edit_index = idx
                        st.session_state.edit_alimento = row_dia['Alimento']
                        st.session_state.edit_qtd = row_dia.get('Qtd/Coef', 1.0)
                        st.rerun()
                    
                    # Ícone Apagar (Lixo)
                    if r_cols[1].button("🗑️", key=f"del_{idx}", help="Apagar"):
                        df_final = df_h.drop(idx)
                        if safe_update("Sheet1", df_final):
                            st.cache_data.clear()
                            st.rerun()
                    
                    # Dados nutricionais
                    r_cols[2].write(row_dia['Alimento'])
                    r_cols[3].write(f"{row_dia['Calorias']:.0f}")
                    r_cols[4].write(f"{row_dia['Proteína']:.1f}g")
                    r_cols[5].write(f"{row_dia['Hidratos']:.1f}g")
                    r_cols[6].write(f"{row_dia['Fibras']:.1f}g")

                # Totais no final
                st.divider()
                m_cols = st.columns([1.6, 0.5, 0.5, 0.5, 0.5])
                m_cols[0].write("**TOTAIS:**")
                m_cols[1].write(f"**{dia_df['Calorias'].sum():.0f}**")
                m_cols[2].write(f"**{dia_df['Proteína'].sum():.1f}g**")
                m_cols[3].write(f"**{dia_df['Hidratos'].sum():.1f}g**")
                m_cols[4].write(f"**{dia_df['Fibras'].sum():.1f}g**")
            else:
                st.info("Ainda não registou alimentos hoje.")
