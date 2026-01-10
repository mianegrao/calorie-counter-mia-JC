import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import date, timedelta
from streamlit_gsheets import GSheetsConnection
import time

# --- 1. CONFIGURAÇÃO E ESTILOS ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

# CSS para garantir que a interface se mantém limpa
st.markdown("""
    <style>
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. ESTADO DA SESSÃO ---
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
    st.session_state.edit_index = None
    st.session_state.edit_alimento = None
    st.session_state.edit_qtd = 1.0

# --- 3. FUNÇÕES DE SUPORTE (O MOTOR DA APP) ---

def safe_update(worksheet, data):
    """Grava os dados no Google Sheets de forma segura."""
    try:
        df_to_save = data.copy()
        if "Sel." in df_to_save.columns: df_to_save = df_to_save.drop(columns=["Sel."])
        df_to_save['Data'] = df_to_save['Data'].astype(str)
        conn.update(worksheet=worksheet, data=df_to_save)
        return True
    except Exception as e:
        st.error(f"Erro na gravação: {e}")
        return False

@st.cache_data(ttl=10)
def get_data_sheets(worksheet_name):
    """Lê os dados e normaliza nomes de colunas e utilizadores."""
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df is None or df.empty: return pd.DataFrame()
        df = df.dropna(how='all').reset_index(drop=True)
        df.columns = df.columns.str.strip()
        # Limpa espaços em branco nos nomes de utilizadores e alimentos
        for col in ['Utilizador', 'Alimento']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
        
        mapeamento = {
            'Proteina': 'Proteína', 'Acucar': '(açúcar)', 'Açúcar': '(açúcar)', 
            'Lipidos': 'Lípidos', 'Saturadas': '(satur.)', 'Fibra': 'Fibras', 
            'Kcal': 'Calorias'
        }
        return df.rename(columns=mapeamento)
    except:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_combined_food_data():
    """Carrega base de dados de alimentos (Excel + Novos)."""
    try:
        df_excel = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        df_excel.columns = df_excel.columns.str.strip()
    except:
        df_excel = pd.DataFrame()
    df_sheets = get_data_sheets("Novos_Alimentos")
    return pd.concat([df_excel, df_sheets], axis=0, ignore_index=True).drop_duplicates(subset=['ALIMENTO'], keep='last')

df_alimentos = load_combined_food_data()

# --- 4. INTERFACE LATERAL ---
user = st.sidebar.selectbox("Utilizador:", ["Mia", "João Carlos", "Jorge", "Celeste"])
data_sel = st.sidebar.date_input("Data:", date.today())
page = st.sidebar.selectbox("Ir para:", ["Diário / Registo", "Estatísticas", "Câmara IA"])

# --- 5. PÁGINA: DIÁRIO / REGISTO ---
if page == "Diário / Registo":
    st.header(f"📝 Diário de {user}")
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
            
            def get_v(names, q):
                for n in names:
                    if n in row and pd.notnull(row[n]): return float(row[n]) * q
                return 0.0

            nutri = {
                "Calorias": get_v(['Calorias', 'Kcal'], qtd), "Proteína": get_v(['Proteína', 'Proteina'], qtd),
                "Hidratos": get_v(['Hidratos'], qtd), "(açúcar)": get_v(['(açúcar)', 'Acucar'], qtd),
                "Lípidos": get_v(['Lípidos', 'Lipidos'], qtd), "(satur.)": get_v(['(satur.)', 'Saturadas'], qtd),
                "Fibras": get_v(['Fibras', 'Fibra'], qtd), "Sal": get_v(['Sal'], qtd)
            }

            st.info(f"👉 {nutri['Calorias']:.0f} Kcal | {nutri['Proteína']:.1f}g Prot | {nutri['(açúcar)']:.1f}g Açúcar")

            if st.session_state.edit_mode:
                if st.button("💾 ATUALIZAR", type="primary", use_container_width=True):
                    df_h = get_data_sheets("Sheet1")
                    for k, v in nutri.items(): df_h.at[st.session_state.edit_index, k] = v
                    df_h.at[st.session_state.edit_index, "Qtd/Coef"] = qtd
                    if safe_update("Sheet1", df_h):
                        st.session_state.edit_mode = False; st.cache_data.clear(); st.rerun()
                if st.button("Cancelar Edição", use_container_width=True):
                    st.session_state.edit_mode = False; st.rerun()
            else:
                if st.button("✅ CONFIRMAR", type="primary", use_container_width=True):
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
                dia_df.insert(0, "Sel.", False)
                c1, c2 = st.columns(2)
                
                edited_df = st.data_editor(dia_df, hide_index=True, use_container_width=True, 
                                           column_config={"Sel.": st.column_config.CheckboxColumn(), "Data": None, "Utilizador": None})
                
                if c1.button("✏️ Editar Selecionado", use_container_width=True):
                    sel_idx = edited_df[edited_df["Sel."] == True].index
                    if len(sel_idx) == 1:
                        idx = sel_idx[0]
                        st.session_state.edit_mode, st.session_state.edit_index = True, idx
                        st.session_state.edit_alimento = dia_df.at[idx, 'Alimento']
                        st.session_state.edit_qtd = dia_df.at[idx, 'Qtd/Coef'] if 'Qtd/Coef' in dia_df.columns else 1.0
                        st.rerun()
                    else: st.warning("Selecione 1 item.")

                if c2.button("🗑️ Apagar Selecionado", use_container_width=True):
                    indices = edited_df[edited_df["Sel."] == True].index
                    if safe_update("Sheet1", df_h.drop(indices)): st.cache_data.clear(); st.rerun()

                st.divider()
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🔥 Kcal", f"{dia_df['Calorias'].sum():.0f}")
                m2.metric("🥩 Prot", f"{dia_df['Proteína'].sum():.1f}g")
                m3.metric("🍭 Açúcar", f"{dia_df['(açúcar)'].sum():.1f}g")
                m4.metric("🌾 Fibras", f"{dia_df['Fibras'].sum():.1f}g")

# --- 6. PÁGINA: ESTATÍSTICAS ---
elif page == "Estatísticas":
    st.header(f"📊 Perfil Nutricional: {user}")
    df_h = get_data_sheets("Sheet1")
    
    if not df_h.empty:
        df_h['Data'] = pd.to_datetime(df_h['Data'], errors='coerce')
        user_df = df_h[(df_h['Utilizador'].str.upper() == user.upper()) & (df_h['Data'].notnull())].copy()
        
        if not user_df.empty:
            cols_n = ['Calorias', 'Proteína', 'Hidratos', '(açúcar)', 'Lípidos', '(satur.)', 'Fibras', 'Sal']
            for c in cols_n: user_df[c] = pd.to_numeric(user_df[c], errors='coerce').fillna(0)

            diario = user_df.groupby(user_df['Data'].dt.date)[cols_n].sum().reset_index()
            diario['Data'] = pd.to_datetime(diario['Data'])

            t1, t2 = st.tabs(["📅 Médias Semanais", "📆 Histórico Mensal"])

            with t1:
                ultimos = diario.sort_values('Data', ascending=False).head(7)
                st.subheader(f"Média Diária (Últimos {len(ultimos)} dias ativos)")
                row1 = st.columns(4)
                row1[0].metric("🔥 Kcal", f"{ultimos['Calorias'].mean():.0f}")
                row1[1].metric("🥩 Prot", f"{ultimos['Proteína'].mean():.1f}g")
                row1[2].metric("🍞 Hidratos", f"{ultimos['Hidratos'].mean():.1f}g")
                row1[3].metric("🥑 Lípidos", f"{ultimos['Lípidos'].mean():.1f}g")
                
                row2 = st.columns(4)
                row2[0].metric("🍭 Açúcar", f"{ultimos['(açúcar)'].mean():.1f}g")
                row2[1].metric("🍔 Satur.", f"{ultimos['(satur.)'].mean():.1f}g")
                row2[2].metric("🌾 Fibras", f"{ultimos['Fibras'].mean():.1f}g")
                row2[3].metric("🧂 Sal", f"{ultimos['Sal'].mean():.2f}g")
                
                st.line_chart(diario.set_index('Data')[['Calorias', '(açúcar)']])

            with t2:
                diario['Mês'] = diario['Data'].dt.strftime('%Y-%m')
                mensal = diario.groupby('Mês')[cols_n].mean().reset_index()
                st.dataframe(mensal, hide_index=True, use_container_width=True)
        else:
            st.warning(f"Sem registos para {user}.")
