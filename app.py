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

# 1. Configurar IA
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

# 2. Conexão Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE CARREGAMENTO ---

@st.cache_data(ttl=60)
def get_data_sheets(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        return df.dropna(how='all') if df is not None else pd.DataFrame()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_combined_food_data():
    # 1. Carregar do Excel (GitHub)
    try:
        df_excel = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        df_excel.columns = df_excel.columns.str.strip()
        df_excel = df_excel.dropna(subset=['ALIMENTO'])
    except:
        df_excel = pd.DataFrame()

    # 2. Carregar do Google Sheets (Novos_Alimentos)
    df_sheets = get_data_sheets("Novos_Alimentos")
    if not df_sheets.empty:
        df_sheets = df_sheets.rename(columns={"Alimento": "ALIMENTO"})
    
    # 3. Fundir as duas listas
    df_final = pd.concat([df_excel, df_sheets], ignore_index=True)
    return df_final.drop_duplicates(subset=['ALIMENTO'], keep='last').sort_values(by='ALIMENTO')

# Carregar a lista fundida
df_alimentos = load_combined_food_data()

# --- NAVEGAÇÃO ---
if "page" not in st.session_state:
    st.session_state.page = "Página Inicial / Registo"

user = st.sidebar.selectbox("Utilizador:", ["Mia", "João Carlos", "Jorge", "Celeste"])
data_sel = st.sidebar.date_input("Data:", date.today())

page = st.sidebar.selectbox("Ir para:", 
    ["Página Inicial / Registo", "Estatísticas & Médias", "Registo de Exercício", "Câmara IA"])

# --- PÁGINA 1: REGISTO ---
if page == "Página Inicial / Registo":
    st.header(f"📝 Diário de {user}")
    col1, col2 = st.columns([1, 1.3])
    
    with col1:
        st.subheader("Novo Registo")
        
        alimento_sel = st.selectbox(
            "Pesquisar Alimento:", 
            options=df_alimentos['ALIMENTO'].unique(), 
            index=None, 
            placeholder="Procurar no Excel ou Base de Novos..."
        )

        add_novo = st.checkbox("➕ Não existe? Adicionar à base permanentemente")

        if add_novo:
            st.markdown("---")
            st.info("Valores por 100g ou dose. Ficará disponível para sempre após guardar.")
            n_nome = st.text_input("Nome do Alimento:")
            
            c1, c2 = st.columns(2)
            n_kcal = c1.number_input("Kcal", min_value=0.0, step=1.0)
            n_prot = c2.number_input("Proteína (g)", min_value=0.0, step=0.1)
            
            c3, c4 = st.columns(2)
            n_hid = c3.number_input("Hidratos (g)", min_value=0.0, step=0.1)
            n_acu = c4.number_input("Açúcar (g)", min_value=0.0, step=0.1)
            
            c5, c6 = st.columns(2)
            n_lip = c5.number_input("Lípidos (g)", min_value=0.0, step=0.1)
            n_sat = c6.number_input("Saturadas (g)", min_value=0.0, step=0.1)
            
            c7, c8 = st.columns(2)
            n_fib = c7.number_input("Fibra (g)", min_value=0.0, step=0.1)
            n_sal = c8.number_input("Sal (g)", min_value=0.0, step=0.01)
            
            if st.button("💾 GUARDAR NA BASE PERMANENTE"):
                if n_nome:
                    novo_item = pd.DataFrame([{
                        "Alimento": n_nome, "Kcal": n_kcal, "Proteina": n_prot, 
                        "Hidratos": n_hid, "Acucar": n_acu, "Lipidos": n_lip, 
                        "Saturadas": n_sat, "Fibra": n_fib, "Sal": n_sal
                    }])
                    df_n_atual = conn.read(worksheet="Novos_Alimentos", ttl=0)
                    conn.update(worksheet="Novos_Alimentos", data=pd.concat([df_n_atual, novo_item], ignore_index=True))
                    st.cache_data.clear()
                    st.success("Guardado! Agora já o podes pesquisar na lista acima.")
                    time.sleep(1)
                    st.rerun()
        
        elif alimento_sel:
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento_sel].iloc[0]
            qtd = st.number_input("Quantidade / Coeficiente:", min_value=0.01, value=1.00, step=0.05)
            
            def get_v(names):
                for n in names:
                    if n in row and pd.notnull(row[n]): return float(row[n]) * qtd
                return 0.0

            vals = {
                "Kcal": get_v(['Calorias', 'Kcal']),
                "Proteina": get_v(['Proteína', 'Proteina']),
                "Hidratos": get_v(['Hidratos', 'Hidratos de Carbono']),
                "Acucar": get_v(['Acucar', 'Açúcar', '(açúcar)']),
                "Lipidos": get_v(['Lipidos', 'Lípidos']),
                "Saturadas": get_v(['Saturadas', 'saturadas']),
                "Fibra": get_v(['Fibra', 'Fibras']),
                "Sal": get_v(['Sal'])
            }
            
            st.info(f"✨ {vals['Kcal']:.1f} kcal | {vals['Proteina']:.1f}g Prot")

            if st.button("CONFIRMAR REGISTO NO DIÁRIO"):
                df_atual = conn.read(worksheet="Sheet1", ttl=0)
                nova_l = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento_sel, **{k: round(v, 2) for k, v in vals.items()}}])
                conn.update(worksheet="Sheet1", data=pd.concat([df_atual, nova_l], ignore_index=True))
                st.cache_data.clear()
                st.success("Registado no diário!")
                time.sleep(1)
                st.rerun()

    with col2:
        st.subheader(f"Resumo de {data_sel}")
        df_h = get_data_sheets("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            mask = (df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)
            dia_df = df_h[mask].copy()
            
            if not dia_df.empty:
                dia_df.insert(0, "Sel.", False)
                # Adicionadas colunas de Fibra e Sal à visualização
                display_cols = ["Sel.", "Alimento", "Kcal", "Proteina", "Acucar", "Saturadas", "Fibra", "Sal"]
                cols_to_show = [c for c in display_cols if c in dia_df.columns]
                
                edited_df = st.data_editor(
                    dia_df[cols_to_show].rename(columns={"Proteina": "Prot", "Acucar": "Açúcar", "Saturadas": "Sat"}),
                    hide_index=True,
                    column_config={"Sel.": st.column_config.CheckboxColumn(required=True)},
                    use_container_width=True
                )

                selected_indices = edited_df[edited_df["Sel."] == True].index
                if len(selected_indices) > 0:
                    if st.button(f"🗑️ Apagar Selecionados"):
                        df_final = df_h.drop(selected_indices)
                        conn.update(worksheet="Sheet1", data=df_final)
                        st.cache_data.clear()
                        st.rerun()
                
                st.markdown("---")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Kcal", f"{dia_df['Kcal'].sum():.0f}")
                m2.metric("Proteína", f"{dia_df['Proteina'].sum():.1f}g")
                m3.metric("Açúcar", f"{dia_df['Acucar'].sum():.1f}g")
                m4.metric("Fibra", f"{dia_df.get('Fibra', pd.Series([0])).sum():.1f}g")
