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

# --- ESTADO DA SESSÃO ---
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
    st.session_state.edit_index = None
    st.session_state.edit_alimento = None
    st.session_state.edit_qtd = 1.0

# --- FUNÇÕES DE SUPORTE ---
def safe_update(worksheet, data):
    try:
        df_to_save = data.copy()
        if "Sel." in df_to_save.columns: df_to_save = df_to_save.drop(columns=["Sel."])
        conn.update(worksheet=worksheet, data=df_to_save)
        return True
    except: return False

@st.cache_data(ttl=60)
def get_data_sheets(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df is None or df.empty: return pd.DataFrame()
        df = df.dropna(how='all').reset_index(drop=True)
        mapeamento = {'Proteina': 'Proteína', 'Acucar': '(açúcar)', 'Açúcar': '(açúcar)', 
                      'Lipidos': 'Lípidos', 'Saturadas': '(satur.)', 'Fibra': 'Fibras', 'Kcal': 'Calorias'}
        return df.rename(columns=mapeamento)
    except: return pd.DataFrame()

@st.cache_data(ttl=600)
def load_combined_food_data():
    try:
        df_excel = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        df_excel.columns = df_excel.columns.str.strip()
    except: df_excel = pd.DataFrame()
    df_sheets = get_data_sheets("Novos_Alimentos")
    return pd.concat([df_excel, df_sheets], axis=0, ignore_index=True).drop_duplicates(subset=['ALIMENTO'], keep='last')

df_alimentos = load_combined_food_data()

# --- INTERFACE ---
user = st.sidebar.selectbox("Utilizador:", ["Mia", "João Carlos", "Jorge", "Celeste"])
data_sel = st.sidebar.date_input("Data:", date.today())
page = st.sidebar.selectbox("Ir para:", ["Diário / Registo", "Estatísticas", "Exercício", "Câmara IA"])

if page == "Diário / Registo":
    st.header(f"📝 Diário de {user}")
    
    # PROPORÇÕES AJUSTADAS: Coluna de registo maior (1.5) e tabela (2.0)
    col_form, col_resumo = st.columns([1.5, 2.0], gap="large")
    
    with col_form:
        if st.session_state.edit_mode:
            st.subheader("✏️ Editar Registo")
            alimento_sel = st.session_state.edit_alimento
            st.warning(f"A alterar: **{alimento_sel}**")
        else:
            st.subheader("Novo Registo")
            opcoes = df_alimentos['ALIMENTO'].unique() if not df_alimentos.empty else []
            alimento_sel = st.selectbox("Pesquisar Alimento:", options=opcoes, index=None)

        if alimento_sel:
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento_sel].iloc[0]
            def_q = st.session_state.edit_qtd if st.session_state.edit_mode else 1.0
            qtd = st.number_input("Quantidade / Coeficiente:", min_value=0.01, value=float(def_q), step=0.05)
            
            # Cálculo de Nutrientes
            def get_v(names, q):
                for n in names:
                    if n in row and pd.notnull(row[n]): return float(row[n]) * q
                return 0.0

            nutri = {
                "Calorias": get_v(['Calorias', 'Kcal'], qtd),
                "Proteína": get_v(['Proteína', 'Proteina'], qtd),
                "Hidratos": get_v(['Hidratos'], qtd),
                "(açúcar)": get_v(['(açúcar)', 'Acucar'], qtd),
                "Lípidos": get_v(['Lípidos', 'Lipidos'], qtd),
                "(satur.)": get_v(['(satur.)', 'Saturadas'], qtd),
                "Fibras": get_v(['Fibras', 'Fibra'], qtd),
                "Sal": get_v(['Sal'], qtd)
            }

            # Visualização clara dos valores antes de registar
            st.markdown(f"""
            **Resumo Nutricional:**
            * 🔥 **{nutri['Calorias']:.1f}** Kcal
            * 🥩 **{nutri['Proteína']:.1f}g** Proteína | 🍞 **{nutri['Hidratos']:.1f}g** Hidratos
            * 🌾 **{nutri['Fibras']:.1f}g** Fibras | 🥑 **{nutri['Lípidos']:.1f}g** Lípidos
            """)

            if st.session_state.edit_mode:
                if st.button("💾 ATUALIZAR", type="primary", use_container_width=True):
                    df_h = get_data_sheets("Sheet1")
                    for k, v in nutri.items(): df_h.at[st.session_state.edit_index, k] = v
                    df_h.at[st.session_state.edit_index, "Qtd/Coef"] = qtd
                    if safe_update("Sheet1", df_h):
                        st.session_state.edit_mode = False
                        st.cache_data.clear(); st.rerun()
                if st.button("Cancelar Edição", use_container_width=True):
                    st.session_state.edit_mode = False; st.rerun()
            else:
                if st.button("✅ CONFIRMAR REGISTO", type="primary", use_container_width=True):
                    df_h = get_data_sheets("Sheet1")
                    novo = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento_sel, "Qtd/Coef": qtd, **nutri}])
                    if safe_update("Sheet1", pd.concat([df_h, novo], ignore_index=True)):
                        st.cache_data.clear(); st.rerun()

    with col_resumo:
        st.subheader("Resumo do Dia")
        df_h = get_data_sheets("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            dia_df = df_h[(df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)].copy()
            
            if not dia_df.empty:
                # Coluna de seleção para ações
                dia_df.insert(0, "Sel.", False)
                
                # Barra de Ferramentas Compacta
                c1, c2 = st.columns(2)
                btn_edit = c1.button("✏️ Editar Selecionado", use_container_width=True)
                btn_del = c2.button("🗑️ Apagar Selecionado", use_container_width=True)

                # TABELA COM SCROLL LATERAL AUTOMÁTICO
                # Mostra todos os nutrientes sem apertar a coluna da esquerda
                edited_df = st.data_editor(
                    dia_df,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Sel.": st.column_config.CheckboxColumn(required=True),
                        "Data": None, "Utilizador": None # Oculta colunas desnecessárias
                    }
                )

                if btn_edit:
                    sel_rows = edited_df[edited_df["Sel."] == True]
                    if len(sel_rows) == 1:
                        idx = sel_rows.index[0]
                        st.session_state.edit_mode = True
                        st.session_state.edit_index = idx
                        st.session_state.edit_alimento = dia_df.at[idx, 'Alimento']
                        st.session_state.edit_qtd = dia_df.at[idx, 'Qtd/Coef']
                        st.rerun()
                    else: st.warning("Selecione apenas 1 item para editar.")

                if btn_del:
                    indices_finais = edited_df[edited_df["Sel."] == True].index
                    if safe_update("Sheet1", df_h.drop(indices_finais)):
                        st.cache_data.clear(); st.rerun()

                st.divider()
                # Métricas Rápidas
                m1, m2, m3 = st.columns(3)
                m1.metric("Kcal", f"{dia_df['Calorias'].sum():.0f}")
                m2.metric("Prot", f"{dia_df['Proteína'].sum():.1f}g")
                m3.metric("Fibras", f"{dia_df['Fibras'].sum():.1f}g")
            else:
                st.info("Nenhum alimento registado para esta data.")
