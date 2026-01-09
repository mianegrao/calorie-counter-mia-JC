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
            # Limpeza de colunas temporárias antes de gravar
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
    col1, col2 = st.columns([1, 1.4])
    
    with col1:
        # Se estivermos em modo de edição, o formulário muda
        if st.session_state.edit_mode:
            st.subheader("✏️ Editar Registo")
            alimento_sel = st.session_state.edit_alimento
            st.info(f"A editar: **{alimento_sel}**")
        else:
            st.subheader("Novo Registo")
            opcoes = df_alimentos['ALIMENTO'].unique() if not df_alimentos.empty else []
            alimento_sel = st.selectbox("Pesquisar Alimento:", options=opcoes, index=None)

        if alimento_sel:
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento_sel].iloc[0]
            
            # O valor inicial do slider/number muda se for edição
            default_qtd = st.session_state.edit_qtd if st.session_state.edit_mode else 1.0
            qtd = st.number_input("Quantidade / Coeficiente:", min_value=0.01, value=float(default_qtd), step=0.05, key="input_qtd")
            
            def get_v(names, q):
                for n in names:
                    if n in row and pd.notnull(row[n]): return float(row[n]) * q
                return 0.0

            vals = {"Proteína": get_v(['Proteína', 'Proteina'], qtd), "Hidratos": get_v(['Hidratos'], qtd),
                    "(açúcar)": get_v(['(açúcar)', 'Acucar'], qtd), "Lípidos": get_v(['Lípidos', 'Lipidos'], qtd),
                    "(satur.)": get_v(['(satur.)', 'Saturadas'], qtd), "Fibras": get_v(['Fibras', 'Fibra'], qtd),
                    "Sal": get_v(['Sal'], qtd), "Calorias": get_v(['Calorias', 'Kcal'], qtd)}

            st.write(f"📊 **Resultado:** {vals['Calorias']:.1f} Kcal | {vals['Proteína']:.1f}g Prot")

            if st.session_state.edit_mode:
                c_ed1, c_ed2 = st.columns(2)
                if c_ed1.button("💾 ATUALIZAR REGISTO", type="primary"):
                    df_h = get_data_sheets("Sheet1")
                    idx = st.session_state.edit_index
                    # Atualiza a linha existente
                    for k, v in vals.items():
                        df_h.at[idx, k] = v
                    df_h.at[idx, "Qtd/Coef"] = qtd
                    if safe_update("Sheet1", df_h):
                        st.session_state.edit_mode = False
                        st.cache_data.clear()
                        st.success("Atualizado!")
                        time.sleep(0.5); st.rerun()
                
                if c_ed2.button("❌ Cancelar"):
                    st.session_state.edit_mode = False
                    st.rerun()
            else:
                if st.button("✅ CONFIRMAR REGISTO"):
                    df_h = get_data_sheets("Sheet1")
                    novo_reg = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento_sel, "Qtd/Coef": qtd, **vals}])
                    if safe_update("Sheet1", pd.concat([df_h, novo_reg], ignore_index=True)):
                        st.cache_data.clear(); st.success("Registado!"); time.sleep(0.5); st.rerun()

    with col2:
        st.subheader(f"Resumo: {data_sel}")
        df_h = get_data_sheets("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            dia_mask = (df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)
            dia_df = df_h[dia_mask].copy()
            
            if not dia_df.empty:
                # Criamos uma tabela visual, mas com botões de ação
                for idx, row_dia in dia_df.iterrows():
                    with st.expander(f"🍴 {row_dia['Alimento']} - {row_dia['Calorias']:.0f} Kcal"):
                        col_ex1, col_ex2 = st.columns(2)
                        
                        if col_ex1.button("✏️ Editar", key=f"edit_{idx}"):
                            st.session_state.edit_mode = True
                            st.session_state.edit_index = idx
                            st.session_state.edit_alimento = row_dia['Alimento']
                            st.session_state.edit_qtd = row_dia.get('Qtd/Coef', 1.0)
                            st.rerun()
                            
                        if col_ex2.button("🗑️ Apagar", key=f"del_{idx}"):
                            df_final = df_h.drop(idx)
                            if safe_update("Sheet1", df_final):
                                st.cache_data.clear(); st.success("Apagado!"); st.rerun()
                        
                        st.write(f"Prot: {row_dia['Proteína']:.1f}g | Hid: {row_dia['Hidratos']:.1f}g | Fib: {row_dia['Fibras']:.1f}g")

                st.markdown("---")
                m1, m2, m3 = st.columns(3)
                m1.metric("Kcal Total", f"{dia_df['Calorias'].sum():.0f}")
                m2.metric("Prot Total", f"{dia_df['Proteína'].sum():.1f}g")
                m3.metric("Fibras Total", f"{dia_df['Fibras'].sum():.1f}g")
            else:
                st.info("Sem registos hoje.")
