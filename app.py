import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import date, timedelta
from streamlit_gsheets import GSheetsConnection
import time

# --- 1. CONFIGURAÇÃO E ESTILOS (CSS) ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

# CSS Ajustado: Métricas menores e texto legível
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { color: #1f1f1f !important; font-size: 1.2rem !important; font-weight: bold; }
    [data-testid="stMetricLabel"] { color: #5f6368 !important; font-size: 0.8rem !important; }
    .stMetric { background-color: #ffffff !important; border: 1px solid #e0e0e0; padding: 5px 10px !important; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("API Key do Gemini não encontrada.")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. ESTADO DA SESSÃO ---
if "edit_mode" not in st.session_state:
    st.session_state.update({"edit_mode": False, "edit_index": None, "edit_alimento": None, "edit_qtd": 1.0})

# --- 3. FUNÇÕES DE SUPORTE ---

def safe_update(worksheet_name, data):
    try:
        df_to_save = data.copy()
        if "Sel." in df_to_save.columns: df_to_save = df_to_save.drop(columns=["Sel."])
        if 'Data' in df_to_save.columns: df_to_save['Data'] = df_to_save['Data'].astype(str)
        conn.update(worksheet=worksheet_name, data=df_to_save)
        return True
    except Exception as e:
        st.error(f"Erro na gravação: {e}"); return False

@st.cache_data(ttl=5)
def get_data_sheets(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df is None or df.empty: return pd.DataFrame()
        df = df.dropna(how='all').reset_index(drop=True)
        df.columns = df.columns.str.strip()
        mapeamento = {'Proteina': 'Proteína', 'Acucar': '(açúcar)', 'Açúcar': '(açúcar)', 
                      'Lipidos': 'Lípidos', 'Saturadas': '(satur.)', 'Fibra': 'Fibras', 'Kcal': 'Calorias'}
        return df.rename(columns=mapeamento)
    except: return pd.DataFrame()

@st.cache_data(ttl=600)
def load_combined_food_data():
    try:
        df_ex = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        df_ex.columns = df_ex.columns.str.strip()
    except: df_ex = pd.DataFrame()
    df_sh = get_data_sheets("Novos_Alimentos")
    return pd.concat([df_ex, df_sh], axis=0, ignore_index=True).drop_duplicates(subset=['ALIMENTO'], keep='last').sort_values('ALIMENTO')

df_alimentos = load_combined_food_data()

# --- 4. INTERFACE ---
user = st.sidebar.selectbox("Utilizador:", ["Mia", "João Carlos", "Jorge", "Celeste"])
data_sel = st.sidebar.date_input("Data:", date.today())
page = st.sidebar.selectbox("Ir para:", ["Diário / Registo", "Estatísticas", "Câmara IA"])

# --- 5. PÁGINA: DIÁRIO / REGISTO ---
if page == "Diário / Registo":
    st.header(f"📝 Diário de {user}")
    col_form, col_resumo = st.columns([1.2, 2.3], gap="medium")
    
    with col_form:
        if st.session_state.edit_mode:
            st.subheader("✏️ Editar Registo")
            alimento_sel = st.session_state.edit_alimento
        else:
            st.subheader("Novo Registo")
            opcoes = df_alimentos['ALIMENTO'].unique().tolist() if not df_alimentos.empty else []
            alimento_sel = st.selectbox("Pesquisar:", options=opcoes, index=None)

        if not st.session_state.edit_mode and alimento_sel is None:
            with st.expander("✨ Novo Alimento"):
                novo_n = st.text_input("Nome:")
                if st.button("Sugerir com IA") and novo_n:
                    try:
                        res = model.generate_content(f"Gera valores 100g para '{novo_n}': Calorias, Proteína, Hidratos, Açúcar, Lípidos, Saturadas, Fibras, Sal. Só números e vírgulas.").text
                        st.session_state.ia_vals = [float(x.strip()) for x in res.split(',')]
                    except: st.error("Erro na IA.")
                v = st.session_state.get('ia_vals', [0.0]*8)
                n_kcal = st.number_input("Kcal:", value=v[0]); n_prot = st.number_input("Prot:", value=v[1])
                n_hidr = st.number_input("Hidr:", value=v[2]); n_acuc = st.number_input("Açúcar:", value=v[3])
                n_lipd = st.number_input("Líp:", value=v[4]); n_satu = st.number_input("Sat:", value=v[5])
                n_fibr = st.number_input("Fib:", value=v[6]); n_sal = st.number_input("Sal:", value=v[7])
                if st.button("Gravar Alimento"):
                    df_n = get_data_sheets("Novos_Alimentos")
                    row = pd.DataFrame([{"ALIMENTO": novo_n, "Calorias": n_kcal, "Proteína": n_prot, "Hidratos": n_hidr, "(açúcar)": n_acuc, "Lípidos": n_lipd, "(satur.)": n_satu, "Fibras": n_fibr, "Sal": n_sal}])
                    if safe_update("Novos_Alimentos", pd.concat([df_n, row], ignore_index=True)):
                        st.cache_data.clear(); st.rerun()

        if alimento_sel:
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento_sel].iloc[0]
            qtd = st.number_input("Coeficiente (1.0=100g):", min_value=0.01, value=float(st.session_state.edit_qtd))
            nutri = {"Calorias": row.get('Calorias',0)*qtd, "Proteína": row.get('Proteína',0)*qtd, "Hidratos": row.get('Hidratos',0)*qtd, "(açúcar)": row.get('(açúcar)',0)*qtd, "Lípidos": row.get('Lípidos',0)*qtd, "(satur.)": row.get('(satur.)',0)*qtd, "Fibras": row.get('Fibras',0)*qtd, "Sal": row.get('Sal',0)*qtd}
            if st.button("💾 CONFIRMAR", type="primary", use_container_width=True):
                df_h = get_data_sheets("Sheet1")
                if st.session_state.edit_mode:
                    for k,v in nutri.items(): df_h.at[st.session_state.edit_index, k] = v
                    df_h.at[st.session_state.edit_index, "Qtd/Coef"] = qtd
                    st.session_state.edit_mode = False
                else:
                    novo = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento_sel, "Qtd/Coef": qtd, **nutri}])
                    df_h = pd.concat([df_h, novo], ignore_index=True)
                if safe_update("Sheet1", df_h): st.cache_data.clear(); st.rerun()

    with col_resumo:
        st.subheader("Resumo do Dia")
        df_h = get_data_sheets("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            dia_df = df_h[(df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)].copy()
            if not dia_df.empty:
                dia_df.insert(0, "Sel.", False)
                edited_df = st.data_editor(dia_df, hide_index=True, use_container_width=True, column_config={"Sel.": st.column_config.CheckboxColumn(), "Data": None, "Utilizador": None})
                
                c1, c2, c3 = st.columns([1, 1, 1.2])
                if c1.button("✏️ Editar", use_container_width=True):
                    sel = edited_df[edited_df["Sel."]]
                    if len(sel) == 1:
                        idx = sel.index[0]
                        st.session_state.update({"edit_mode": True, "edit_index": idx, "edit_alimento": dia_df.at[idx, 'Alimento'], "edit_qtd": dia_df.at[idx, 'Qtd/Coef']})
                        st.rerun()
                if c2.button("🗑️ Apagar", use_container_width=True):
                    indices = edited_df[edited_df["Sel."]].index
                    if safe_update("Sheet1", df_h.drop(indices)): st.cache_data.clear(); st.rerun()
                
                # MUDANÇA DE DATA EM MASSA
                with c3:
                    with st.popover("📅 Alterar Data"):
                        nova_d = st.date_input("Nova data:", date.today())
                        if st.button("Mover Selecionados"):
                            indices = edited_df[edited_df["Sel."]].index
                            df_h.loc[indices, "Data"] = str(nova_d)
                            if safe_update("Sheet1", df_h): st.cache_data.clear(); st.rerun()

                st.divider()
                m = st.columns(8)
                m[0].metric("Kcal", f"{dia_df['Calorias'].sum():.0f}")
                m[1].metric("Prot", f"{dia_df['Proteína'].sum():.1f}")
                m[2].metric("Hidr", f"{dia_df['Hidratos'].sum():.1f}")
                m[3].metric("Açúc", f"{dia_df['(açúcar)'].sum():.1f}")
                m[4].metric("Líp", f"{dia_df['Lípidos'].sum():.1f}")
                m[5].metric("Sat", f"{dia_df['(satur.)'].sum():.1f}")
                m[6].metric("Fib", f"{dia_df['Fibras'].sum():.1f}")
                m[7].metric("Sal", f"{dia_df['Sal'].sum():.2f}")

# --- 6. PÁGINA: ESTATÍSTICAS (CORRIGIDA) ---
elif page == "Estatísticas":
    st.header(f"📊 Estatísticas de {user}")
    df_h = get_data_sheets("Sheet1")
    if not df_h.empty:
        df_h['Data'] = pd.to_datetime(df_h['Data'], errors='coerce')
        user_df = df_h[df_h['Utilizador'].str.lower() == user.lower()].copy()
        if not user_df.empty:
            cols = ['Calorias', 'Proteína', 'Hidratos', '(açúcar)', 'Lípidos', '(satur.)', 'Fibras', 'Sal']
            for c in cols: user_df[c] = pd.to_numeric(user_df[c], errors='coerce').fillna(0)
            
            # Agrupar por dia (apenas dias com entradas)
            diario = user_df.groupby(user_df['Data'].dt.date)[cols].sum().reset_index()
            diario['Data'] = pd.to_datetime(diario['Data'])
            
            t1, t2 = st.tabs(["📅 Médias de Dias Ativos", "📆 Histórico Mensal"])
            with t1:
                u = diario.tail(7)
                st.subheader(f"Média Diária (Últimos {len(u)} dias com registo)")
                r1, r2 = st.columns(4), st.columns(4)
                r1[0].metric("🔥 Kcal", f"{u['Calorias'].mean():.0f}")
                r1[1].metric("🥩 Prot", f"{u['Proteína'].mean():.1f}g")
                r1[2].metric("🍞 Hidr", f"{u['Hidratos'].mean():.1f}g")
                r1[3].metric("🥑 Líp", f"{u['Lípidos'].mean():.1f}g")
                r2[0].metric("🍭 Açúcar", f"{u['(açúcar)'].mean():.1f}g")
                r2[1].metric("🍔 Sat.", f"{u['(satur.)'].mean():.1f}g")
                r2[2].metric("🌾 Fibra", f"{u['Fibras'].mean():.1f}g")
                r2[3].metric("🧂 Sal", f"{u['Sal'].mean():.2f}g")
                st.line_chart(diario.set_index('Data')['Calorias'])
            with t2:
                diario['Mês'] = diario['Data'].dt.strftime('%Y-%m')
                st.dataframe(diario.groupby('Mês')[cols].mean(), use_container_width=True)
        else: st.warning("Sem dados para este utilizador.")

elif page == "Câmara IA":
    st.header("📸 Câmara IA")
    st.camera_input("Tire foto")
