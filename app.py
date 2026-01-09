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

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE SUPORTE ---

def safe_update(worksheet, data, max_retries=3):
    for i in range(max_retries):
        try:
            # Garante que não enviamos a coluna de seleção para o Sheets
            if "Sel." in data.columns:
                data = data.drop(columns=["Sel."])
            conn.update(worksheet=worksheet, data=data)
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
    col1, col2 = st.columns([1, 1.3])
    
    with col1:
        st.subheader("Novo Registo")
        opcoes = df_alimentos['ALIMENTO'].unique() if not df_alimentos.empty else []
        alimento_sel = st.selectbox("Pesquisar Alimento:", options=opcoes, index=None)

        if st.checkbox("➕ Adicionar novo alimento à base"):
            n_nome = st.text_input("Nome (ALIMENTO):")
            c_p1, c_p2 = st.columns(2)
            n_prot = c_p1.number_input("Proteína (g)", 0.0)
            n_hid = c_p2.number_input("Hidratos (g)", 0.0)
            n_acu = st.number_input("(açúcar) (g)", 0.0)
            if st.button("💾 GUARDAR NA BASE PERMANENTE"):
                if n_nome:
                    novo = pd.DataFrame([{"ALIMENTO": n_nome, "Proteína": n_prot, "Hidratos": n_hid, "(açúcar)": n_acu, "Calorias": 0.0}])
                    df_n = get_data_sheets("Novos_Alimentos")
                    safe_update("Novos_Alimentos", pd.concat([df_n, novo], ignore_index=True))
                    st.cache_data.clear(); st.success("Guardado!"); st.rerun()

        elif alimento_sel:
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento_sel].iloc[0]
            qtd = st.number_input("Quantidade / Coeficiente:", min_value=0.01, value=1.00, step=0.05)
            
            def get_v(names):
                for n in names:
                    if n in row and pd.notnull(row[n]): return float(row[n]) * qtd
                return 0.0

            vals = {"Proteína": get_v(['Proteína', 'Proteina']), "Hidratos": get_v(['Hidratos']),
                    "(açúcar)": get_v(['(açúcar)', 'Acucar']), "Lípidos": get_v(['Lípidos', 'Lipidos']),
                    "(satur.)": get_v(['(satur.)', 'Saturadas']), "Fibras": get_v(['Fibras', 'Fibra']),
                    "Sal": get_v(['Sal']), "Calorias": get_v(['Calorias', 'Kcal'])}

            st.info(f"A registar: {vals['Calorias']:.1f} Kcal | {vals['Proteína']:.1f}g Prot")

            if st.button("✅ CONFIRMAR REGISTO"):
                df_h = get_data_sheets("Sheet1")
                novo_reg = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento_sel, **vals}])
                safe_update("Sheet1", pd.concat([df_h, novo_reg], ignore_index=True))
                st.cache_data.clear(); st.success("Registado!"); time.sleep(0.5); st.rerun()

    with col2:
        st.subheader(f"Resumo: {data_sel}")
        df_h = get_data_sheets("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            # Filtramos os dados mas mantemos o índice original para poder apagar/editar
            dia_mask = (df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)
            dia_df = df_h[dia_mask].copy()
            
            if not dia_df.empty:
                dia_df.insert(0, "Sel.", False)
                cols_n = ["Alimento", "Calorias", "Proteína", "Hidratos", "(açúcar)", "Lípidos", "Fibras"]
                
                # Editor permite alterar Alimento e valores diretamente
                edited_df = st.data_editor(dia_df[["Sel."] + cols_n], hide_index=False, use_container_width=True)

                c_b1, c_b2 = st.columns(2)
                
                if c_b1.button("🗑️ Apagar Selecionados"):
                    # Filtra os índices que foram marcados com o Checkbox "Sel."
                    ids_to_drop = edited_df[edited_df["Sel."] == True].index
                    df_final = df_h.drop(ids_to_drop)
                    if safe_update("Sheet1", df_final):
                        st.cache_data.clear(); st.success("Eliminado!"); st.rerun()

                if c_b2.button("💾 Guardar Alterações"):
                    # Atualiza os dados originais com o que foi escrito no editor
                    df_h.update(edited_df.drop(columns=["Sel."]))
                    if safe_update("Sheet1", df_h):
                        st.cache_data.clear(); st.success("Alterações guardadas!"); st.rerun()
                
                st.markdown("---")
                m1, m2, m3 = st.columns(3)
                m1.metric("Kcal", f"{dia_df['Calorias'].sum():.0f}")
                m2.metric("Prot", f"{dia_df['Proteína'].sum():.1f}g")
                m3.metric("Fibras", f"{dia_df['Fibras'].sum():.1f}g")
            else:
                st.info("Sem registos hoje.")
