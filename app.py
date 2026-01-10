import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import date, timedelta
from streamlit_gsheets import GSheetsConnection
import time

# --- 1. CONFIGURAÇÃO E ESTILOS (CSS) ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

st.markdown("""
    <style>
    [data-testid="stMetricValue"] { color: #1f1f1f !important; font-weight: bold; }
    [data-testid="stMetricLabel"] { color: #5f6368 !important; }
    .stMetric { background-color: #ffffff !important; border: 1px solid #e0e0e0; padding: 10px; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. ESTADO DA SESSÃO ---
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
    st.session_state.edit_index = None
    st.session_state.edit_alimento = None
    st.session_state.edit_qtd = 1.0

# --- 3. FUNÇÕES DE SUPORTE ---

def safe_update(worksheet, data):
    try:
        df_to_save = data.copy()
        if "Sel." in df_to_save.columns: df_to_save = df_to_save.drop(columns=["Sel."])
        df_to_save['Data'] = df_to_save['Data'].astype(str)
        conn.update(worksheet=worksheet, data=df_to_save)
        return True
    except: return False

@st.cache_data(ttl=5)
def get_data_sheets(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df is None or df.empty: return pd.DataFrame()
        df = df.dropna(how='all').reset_index(drop=True)
        df.columns = df.columns.str.strip()
        for col in ['Utilizador', 'Alimento']:
            if col in df.columns: df[col] = df[col].astype(str).str.strip()
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
    return pd.concat([df_excel, df_sheets], axis=0, ignore_index=True).drop_duplicates(subset=['ALIMENTO'], keep='last').sort_values('ALIMENTO')

df_alimentos = load_combined_food_data()

# --- 4. INTERFACE ---
user = st.sidebar.selectbox("Utilizador:", ["Mia", "João Carlos", "Jorge", "Celeste"])
data_sel = st.sidebar.date_input("Data:", date.today())
page = st.sidebar.selectbox("Ir para:", ["Diário / Registo", "Estatísticas", "Câmara IA"])

if page == "Diário / Registo":
    st.header(f"📝 Diário de {user}")
    col_form, col_resumo = st.columns([1.5, 2.0], gap="large")
    
    with col_form:
        if st.session_state.edit_mode:
            st.subheader("✏️ Editar Registo")
            alimento_sel = st.session_state.edit_alimento
        else:
            st.subheader("Novo Registo")
            opcoes = df_alimentos['ALIMENTO'].unique().tolist() if not df_alimentos.empty else []
            alimento_sel = st.selectbox("Pesquisar Alimento:", options=opcoes, index=None, placeholder="Escreva o nome...")

        # --- ADICIONAR NOVO ALIMENTO À LISTA (ESTRUTURA EXCEL) ---
        if not st.session_state.edit_mode and alimento_sel is None:
            with st.expander("✨ Alimento não listado? Adicionar à base de dados"):
                novo_nome = st.text_input("Nome do Alimento:")
                
                c1, c2 = st.columns(2)
                with c1:
                    ia_btn = st.button("Sugerir com IA")
                
                # Valores padrão ou vindos da IA
                v = [0.0] * 8
                if ia_btn and novo_nome:
                    try:
                        p = f"Gera valores para 100g de '{novo_nome}': Calorias, Proteína, Hidratos, Açúcar, Lípidos, Saturadas, Fibras, Sal. Responde apenas com números separados por vírgulas."
                        res = model.generate_content(p).text
                        v = [float(x.strip()) for x in res.split(',')]
                    except: st.error("Erro na IA. Insira manualmente.")

                # Campos na ordem exata do Excel
                n_kcal = st.number_input("Calorias (100g):", value=v[0])
                n_prot = st.number_input("Proteína (100g):", value=v[1])
                n_hidr = st.number_input("Hidratos (100g):", value=v[2])
                n_acuc = st.number_input("Açúcar (100g):", value=v[3])
                n_lipd = st.number_input("Lípidos (100g):", value=v[4])
                n_satu = st.number_input("Saturadas (100g):", value=v[5])
                n_fibr = st.number_input("Fibras (100g):", value=v[6])
                n_sal  = st.number_input("Sal (100g):", value=v[7])

                if st.button("Salvar na Base de Dados"):
                    df_novos = get_data_sheets("Novos_Alimentos")
                    novo_row = pd.DataFrame([{
                        "ALIMENTO": novo_nome, "Calorias": n_kcal, "Proteína": n_prot, "Hidratos": n_hidr,
                        "(açúcar)": n_acuc, "Lípidos": n_lipd, "(satur.)": n_satu, "Fibras": n_fibr, "Sal": n_sal
                    }])
                    if safe_update("Novos_Alimentos", pd.concat([df_novos, novo_row], ignore_index=True)):
                        st.success("Adicionado! Atualize a página."); st.cache_data.clear()

        # --- REGISTO NO DIÁRIO ---
        if alimento_sel:
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento_sel].iloc[0]
            qtd = st.number_input("Coeficiente (1.0 = 100g):", min_value=0.01, value=float(st.session_state.edit_qtd), step=0.05)
            
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

            st.info(f"👉 {nutri['Calorias']:.0f} Kcal | {nutri['Proteína']:.1f}g Prot")

            if st.button("💾 " + ("ATUALIZAR" if st.session_state.edit_mode else "CONFIRMAR"), type="primary", use_container_width=True):
                df_h = get_data_sheets("Sheet1")
                if st.session_state.edit_mode:
                    for k, v in nutri.items(): df_h.at[st.session_state.edit_index, k] = v
                    df_h.at[st.session_state.edit_index, "Qtd/Coef"] = qtd
                    st.session_state.edit_mode = False
                else:
                    novo = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento_sel, "Qtd/Coef": qtd, **nutri}])
                    df_h = pd.concat([df_h, novo], ignore_index=True)
                
                if safe_update("Sheet1", df_h):
                    st.cache_data.clear(); st.rerun()

    with col_resumo:
        st.subheader("Resumo do Dia")
        df_h = get_data_sheets("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            dia_df = df_h[(df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)].copy()
            if not dia_df.empty:
                dia_df.insert(0, "Sel.", False)
                edited_df = st.data_editor(dia_df, hide_index=True, use_container_width=True, 
                                           column_config={"Sel.": st.column_config.CheckboxColumn(), "Data": None, "Utilizador": None})
                
                c1, c2 = st.columns(2)
                if c1.button("✏️ Editar Selecionado"):
                    sel = edited_df[edited_df["Sel."] == True]
                    if len(sel) == 1:
                        idx = sel.index[0]
                        st.session_state.edit_mode, st.session_state.edit_index = True, idx
                        st.session_state.edit_alimento, st.session_state.edit_qtd = dia_df.at[idx, 'Alimento'], dia_df.at[idx, 'Qtd/Coef']
                        st.rerun()

                if c2.button("🗑️ Apagar Selecionado"):
                    indices = edited_df[edited_df["Sel."] == True].index
                    if safe_update("Sheet1", df_h.drop(indices)): st.cache_data.clear(); st.rerun()

                st.divider()
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🔥 Kcal", f"{dia_df['Calorias'].sum():.0f}")
                m2.metric("🥩 Prot", f"{dia_df['Proteína'].sum():.1f}g")
                m3.metric("🍞 Hidratos", f"{dia_df['Hidratos'].sum():.1f}g")
                m4.metric("🍭 Açúcar", f"{dia_df['(açúcar)'].sum():.1f}g")

elif page == "Estatísticas":
    st.header(f"📊 Estatísticas: {user}")
    df_h = get_data_sheets("Sheet1")
    if not df_h.empty:
        df_h['Data'] = pd.to_datetime(df_h['Data'], errors='coerce')
        user_df = df_h[(df_h['Utilizador'].str.upper() == user.upper()) & (df_h['Data'].notnull())].copy()
        if not user_df.empty:
            cols = ['Calorias', 'Proteína', 'Hidratos', '(açúcar)', 'Lípidos', '(satur.)', 'Fibras', 'Sal']
            for c in cols: user_df[c] = pd.to_numeric(user_df[c], errors='coerce').fillna(0)
            diario = user_df.groupby(user_df['Data'].dt.date)[cols].sum().reset_index()
            diario['Data'] = pd.to_datetime(diario['Data'])
            
            t1, t2 = st.tabs(["📅 Semanal", "📆 Mensal"])
            with t1:
                u = diario.sort_values('Data', ascending=False).head(7)
                st.subheader(f"Média Diária ({len(u)} dias ativos)")
                r1, r2 = st.columns(4), st.columns(4)
                r1[0].metric("🔥 Kcal", f"{u['Calorias'].mean():.0f}")
                r1[1].metric("🥩 Prot", f"{u['Proteína'].mean():.1f}g")
                r1[2].metric("🍞 Hidratos", f"{u['Hidratos'].mean():.1f}g")
                r1[3].metric("🥑 Lípidos", f"{u['Lípidos'].mean():.1f}g")
                r2[0].metric("🍭 Açúcar", f"{u['(açúcar)'].mean():.1f}g")
                r2[1].metric("🌾 Fibras", f"{u['Fibras'].mean():.1f}g")
                r2[2].metric("🍔 Satur.", f"{u['(satur.)'].mean():.1f}g")
                r2[3].metric("🧂 Sal", f"{u['Sal'].mean():.2f}g")
                st.line_chart(diario.set_index('Data')[['Calorias']])
            with t2:
                diario['Mês'] = diario['Data'].dt.strftime('%Y-%m')
                st.dataframe(diario.groupby('Mês')[cols].mean(), use_container_width=True)

elif page == "Câmara IA":
    st.header("📸 Câmara IA")
    st.camera_input("Foto do alimento")
