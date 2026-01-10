import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import date, timedelta
from streamlit_gsheets import GSheetsConnection
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

# Estilo para melhorar a legibilidade das métricas e tabelas
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 10px; border-radius: 8px; }
    div[data-testid="stExpander"] { border: none !important; box-shadow: none !important; }
    </style>
    """, unsafe_allow_html=True)

# Configuração da API Gemini (IA)
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
else:
    st.error("API Key do Gemini não encontrada nos secrets.")

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
        df_to_save['Data'] = df_to_save['Data'].astype(str)
        conn.update(worksheet=worksheet, data=df_to_save)
        return True
    except:
        return False

@st.cache_data(ttl=5)
def get_data_sheets(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df is None or df.empty: return pd.DataFrame()
        df = df.dropna(how='all').reset_index(drop=True)
        df.columns = df.columns.str.strip()
        for col in ['Utilizador', 'Alimento']:
            if col in df.columns: df[col] = df[col].astype(str).str.strip()
        
        mapeamento = {
            'Proteina': 'Proteína', 'Acucar': '(açúcar)', 'Açúcar': '(açúcar)', 
            'Lipidos': 'Lípidos', 'Saturadas': '(satur.)', 'Fibra': 'Fibras', 'Kcal': 'Calorias'
        }
        return df.rename(columns=mapeamento)
    except:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_combined_food_data():
    try:
        df_excel = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        df_excel.columns = df_excel.columns.str.strip()
    except:
        df_excel = pd.DataFrame()
    df_sheets = get_data_sheets("Novos_Alimentos")
    return pd.concat([df_excel, df_sheets], axis=0, ignore_index=True).drop_duplicates(subset=['ALIMENTO'], keep='last')

df_alimentos = load_combined_food_data()

# --- INTERFACE ---
user = st.sidebar.selectbox("Utilizador:", ["Mia", "João Carlos", "Jorge", "Celeste"])
data_sel = st.sidebar.date_input("Data:", date.today())
page = st.sidebar.selectbox("Ir para:", ["Diário / Registo", "Estatísticas", "Câmara IA"])

# --- PÁGINA: DIÁRIO ---
if page == "Diário / Registo":
    st.header(f"📝 Diário de {user}")
    col_form, col_resumo = st.columns([1.5, 2.0], gap="large")
    
    with col_form:
        if st.session_state.edit_mode:
            st.subheader("✏️ Editar")
            alimento_sel = st.session_state.edit_alimento
        else:
            st.subheader("Novo Registo")
            opcoes = df_alimentos['ALIMENTO'].unique().tolist() if not df_alimentos.empty else []
            alimento_sel = st.selectbox("Pesquisar Alimento:", options=opcoes, index=None, placeholder="Escreva o nome...")

        # SE O ALIMENTO NÃO EXISTE (Lógica de Adição)
        if not st.session_state.edit_mode and alimento_sel is None:
            with st.expander("✨ Alimento não encontrado? Adicionar novo"):
                novo_nome = st.text_input("Nome do alimento:")
                metodo = st.radio("Método:", ["Usar IA (Gemini)", "Manual"], horizontal=True)
                
                if st.button("Analisar / Preparar"):
                    if metodo == "Usar IA (Gemini)" and novo_nome:
                        prompt = f"Gera apenas os valores nutricionais para 100g de '{novo_nome}' no formato: Calorias, Proteína, Hidratos, Açúcar, Lípidos, Saturadas, Fibras, Sal. Responde apenas com os números separados por vírgulas."
                        res = model.generate_content(prompt).text
                        st.session_state.new_data = res.split(',')
                        st.success(f"Valores sugeridos pela IA para {novo_nome}")
                    
        # FORMULÁRIO DE NUTRIENTES
        if alimento_sel:
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento_sel].iloc[0]
            qtd = st.number_input("Coeficiente (ex: 1.0 = 100g):", min_value=0.01, value=float(st.session_state.edit_qtd), step=0.05)
            
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

            st.write(f"**Total atual:** {nutri['Calorias']:.0f} kcal | {nutri['Proteína']:.1f}g Prot")

            if st.button("💾 " + ("ATUALIZAR" if st.session_state.edit_mode else "CONFIRMAR"), type="primary", use_container_width=True):
                df_h = get_data_sheets("Sheet1")
                if st.session_state.edit_mode:
                    for k, v in nutri.items(): df_h.at[st.session_state.edit_index, k] = v
                    df_h.at[st.session_state.edit_index, "Qtd/Coef"] = qtd
                    st.session_state.edit_mode = False
                else:
                    novo_reg = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento_sel, "Qtd/Coef": qtd, **nutri}])
                    df_h = pd.concat([df_h, novo_reg], ignore_index=True)
                
                if safe_update("Sheet1", df_h):
                    st.cache_data.clear()
                    st.rerun()

    with col_resumo:
        st.subheader("Resumo do Dia")
        df_h = get_data_sheets("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            dia_df = df_h[(df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)].copy()
            if not dia_df.empty:
                dia_df.insert(0, "Sel.", False)
                
                # Configuração da tabela para máxima legibilidade
                edited_df = st.data_editor(
                    dia_df,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Sel.": st.column_config.CheckboxColumn(width="small"),
                        "Alimento": st.column_config.TextColumn(width="large"),
                        "Qtd/Coef": st.column_config.NumberColumn(format="%.2f"),
                        "Data": None, "Utilizador": None # Escondidos para poupar espaço
                    }
                )
                
                c1, c2 = st.columns(2)
                if c1.button("✏️ Editar Selecionado", use_container_width=True):
                    sel = edited_df[edited_df["Sel."] == True]
                    if len(sel) == 1:
                        idx = sel.index[0]
                        st.session_state.edit_mode, st.session_state.edit_index = True, idx
                        st.session_state.edit_alimento, st.session_state.edit_qtd = dia_df.at[idx, 'Alimento'], dia_df.at[idx, 'Qtd/Coef']
                        st.rerun()

                if c2.button("🗑️ Apagar Selecionado", use_container_width=True):
                    indices = edited_df[edited_df["Sel."] == True].index
                    if safe_update("Sheet1", df_h.drop(indices)):
                        st.cache_data.clear(); st.rerun()

                st.divider()
                # MÉTRICAS TOTAIS
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🔥 Kcal", f"{dia_df['Calorias'].sum():.0f}")
                m2.metric("🥩 Prot", f"{dia_df['Proteína'].sum():.1f}g")
                m3.metric("🍞 Hidratos", f"{dia_df['Hidratos'].sum():.1f}g")
                m4.metric("🍭 Açúcar", f"{dia_df['(açúcar)'].sum():.1f}g")

# --- PÁGINA: ESTATÍSTICAS ---
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

            t1, t2 = st.tabs(["📅 Médias Semanais", "📆 Histórico Mensal"])
            with t1:
                ultimos = diario.sort_values('Data', ascending=False).head(7)
                st.subheader(f"Médias por dia ativo (Últimos {len(ultimos)})")
                r1 = st.columns(4)
                r1[0].metric("🔥 Kcal", f"{ultimos['Calorias'].mean():.0f}")
                r1[1].metric("🥩 Prot", f"{ultimos['Proteína'].mean():.1f}g")
                r1[2].metric("🍞 Hidratos", f"{ultimos['Hidratos'].mean():.1f}g")
                r1[3].metric("🥑 Lípidos", f"{ultimos['Lípidos'].mean():.1f}g")
                r2 = st.columns(4)
                r2[0].metric("🍭 Açúcar", f"{ultimos['(açúcar)'].mean():.1f}g")
                r2[1].metric("🌾 Fibras", f"{ultimos['Fibras'].mean():.1f}g")
                r2[2].metric("🍔 Satur.", f"{ultimos['(satur.)'].mean():.1f}g")
                r2[3].metric("🧂 Sal", f"{ultimos['Sal'].mean():.2f}g")
                st.line_chart(diario.set_index('Data')[['Calorias', '(açúcar)']])
            with t2:
                diario['Mês'] = diario['Data'].dt.strftime('%Y-%m')
                st.dataframe(diario.groupby('Mês')[cols].mean(), use_container_width=True)
        else:
            st.warning(f"Sem dados para {user}.")

# --- PÁGINA: CÂMARA IA ---
elif page == "Câmara IA":
    st.header("📸 Analisar Alimento por Imagem")
    img_file = st.camera_input("Tire uma foto do alimento ou rótulo")
    if img_file:
        st.info("A analisar imagem com Gemini IA...")
        # Lógica de análise de imagem simplificada aqui
        st.warning("Funcionalidade de análise de imagem pronta para processar.")
