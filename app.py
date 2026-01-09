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

# --- FUNÇÕES DE SUPORTE ---

def safe_update(worksheet, data, max_retries=3):
    for i in range(max_retries):
        try:
            # Remove colunas auxiliares antes de enviar para o Sheets
            cols_to_drop = ["Sel.", "Qtd/Coef"]
            df_to_save = data.drop(columns=[c for c in cols_to_drop if c in data.columns])
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
        st.subheader("Novo Registo")
        opcoes = df_alimentos['ALIMENTO'].unique() if not df_alimentos.empty else []
        alimento_sel = st.selectbox("Pesquisar Alimento:", options=opcoes, index=None)

        if alimento_sel:
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento_sel].iloc[0]
            qtd = st.number_input("Quantidade / Coeficiente:", min_value=0.01, value=1.00, step=0.05)
            
            # Cálculo dos valores
            def get_v(names, q):
                for n in names:
                    if n in row and pd.notnull(row[n]): return float(row[n]) * q
                return 0.0

            vals = {"Proteína": get_v(['Proteína', 'Proteina'], qtd), "Hidratos": get_v(['Hidratos'], qtd),
                    "(açúcar)": get_v(['(açúcar)', 'Acucar'], qtd), "Lípidos": get_v(['Lípidos', 'Lipidos'], qtd),
                    "(satur.)": get_v(['(satur.)', 'Saturadas'], qtd), "Fibras": get_v(['Fibras', 'Fibra'], qtd),
                    "Sal": get_v(['Sal'], qtd), "Calorias": get_v(['Calorias', 'Kcal'], qtd)}

            st.info(f"A registar: {vals['Calorias']:.1f} Kcal | {vals['Proteína']:.1f}g Prot")

            if st.button("✅ CONFIRMAR REGISTO"):
                df_h = get_data_sheets("Sheet1")
                # Guardamos também o coeficiente para podermos editar depois
                novo_reg = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento_sel, "Qtd/Coef": qtd, **vals}])
                safe_update("Sheet1", pd.concat([df_h, novo_reg], ignore_index=True))
                st.cache_data.clear(); st.success("Registado!"); time.sleep(0.5); st.rerun()

    with col2:
        st.subheader(f"Resumo: {data_sel}")
        df_h = get_data_sheets("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            dia_mask = (df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)
            dia_df = df_h[dia_mask].copy()
            
            if not dia_df.empty:
                # Se a coluna Qtd/Coef não existir em registos antigos, assume 1.0
                if "Qtd/Coef" not in dia_df.columns: dia_df["Qtd/Coef"] = 1.0
                
                dia_df.insert(0, "Sel.", False)
                # Tabela de visualização com o Coeficiente editável
                cols_view = ["Sel.", "Alimento", "Qtd/Coef", "Calorias", "Proteína", "Hidratos", "Fibras"]
                
                edited_df = st.data_editor(
                    dia_df[cols_view], 
                    hide_index=False, 
                    use_container_width=True,
                    column_config={
                        "Alimento": st.column_config.Column(disabled=True),
                        "Calorias": st.column_config.Column(disabled=True),
                        "Proteína": st.column_config.Column(disabled=True),
                        "Hidratos": st.column_config.Column(disabled=True),
                        "Fibras": st.column_config.Column(disabled=True),
                        "Qtd/Coef": st.column_config.NumberColumn(format="%.2f", min_value=0.01)
                    }
                )

                c_b1, c_b2 = st.columns(2)
                
                if c_b1.button("🗑️ Apagar Selecionados"):
                    ids_to_drop = edited_df[edited_df["Sel."] == True].index
                    df_final = df_h.drop(ids_to_drop)
                    if safe_update("Sheet1", df_final):
                        st.cache_data.clear(); st.success("Eliminado!"); st.rerun()

                if c_b2.button("💾 Recalcular e Guardar"):
                    # Lógica para recalcular tudo com base no novo coeficiente
                    for idx in edited_df.index:
                        novo_coef = edited_df.at[idx, "Qtd/Coef"]
                        velho_coef = dia_df.at[idx, "Qtd/Coef"]
                        
                        if novo_coef != velho_coef:
                            # Encontrar o alimento na base original para saber os valores por unidade
                            nome_ali = dia_df.at[idx, "Alimento"]
                            base_ali = df_alimentos[df_alimentos['ALIMENTO'] == nome_ali].iloc[0]
                            
                            # Atualizar todos os macros no DataFrame original (df_h)
                            df_h.at[idx, "Qtd/Coef"] = novo_coef
                            df_h.at[idx, "Proteína"] = round(float(base_ali.get('Proteína', base_ali.get('Proteina', 0))) * novo_coef, 2)
                            df_h.at[idx, "Hidratos"] = round(float(base_ali.get('Hidratos', 0)) * novo_coef, 2)
                            df_h.at[idx, "(açúcar)"] = round(float(base_ali.get('(açúcar)', base_ali.get('Acucar', 0))) * novo_coef, 2)
                            df_h.at[idx, "Lípidos"] = round(float(base_ali.get('Lípidos', base_ali.get('Lipidos', 0))) * novo_coef, 2)
                            df_h.at[idx, "Fibras"] = round(float(base_ali.get('Fibras', base_ali.get('Fibra', 0))) * novo_coef, 2)
                            df_h.at[idx, "Calorias"] = round(float(base_ali.get('Calorias', base_ali.get('Kcal', 0))) * novo_coef, 2)
                    
                    if safe_update("Sheet1", df_h):
                        st.cache_data.clear(); st.success("Valores atualizados!"); st.rerun()
                
                st.markdown("---")
                m1, m2, m3 = st.columns(3)
                m1.metric("Kcal Total", f"{dia_df['Calorias'].sum():.0f}")
                m2.metric("Prot Total", f"{dia_df['Proteína'].sum():.1f}g")
                m3.metric("Fibras Total", f"{dia_df['Fibras'].sum():.1f}g")
