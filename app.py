import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import date, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE SUPORTE ---
@st.cache_data(ttl=5)
def get_data_sheets(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df is None or df.empty: return pd.DataFrame()
        df = df.dropna(how='all').reset_index(drop=True)
        # Normalização de nomes e dados
        df.columns = df.columns.str.strip()
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
            
        mapeamento = {
            'Proteina': 'Proteína', 'Acucar': '(açúcar)', 'Açúcar': '(açúcar)', 
            'Lipidos': 'Lípidos', 'Saturadas': '(satur.)', 'Fibra': 'Fibras', 
            'Kcal': 'Calorias', 'Sal': 'Sal', 'Hidratos': 'Hidratos'
        }
        return df.rename(columns=mapeamento)
    except: return pd.DataFrame()

# ... (restante do código de carregamento de alimentos mantido) ...

# --- INTERFACE ---
user = st.sidebar.selectbox("Utilizador:", ["Mia", "João Carlos", "Jorge", "Celeste"])
page = st.sidebar.selectbox("Ir para:", ["Diário / Registo", "Estatísticas", "Câmara IA"])

if page == "Diário / Registo":
    # (Mantém a lógica de registo e edição já aperfeiçoada anteriormente)
    pass

elif page == "Estatísticas":
    st.header(f"📊 Perfil Nutricional de {user}")
    df_h = get_data_sheets("Sheet1")
    
    if not df_h.empty:
        # Filtro rigoroso
        user_df = df_h[df_h['Utilizador'].str.upper() == user.upper()].copy()
        user_df['Data'] = pd.to_datetime(user_df['Data'], errors='coerce')
        user_df = user_df.dropna(subset=['Data'])
        
        if not user_df.empty:
            # Agrupar todos os nutrientes por dia
            colunas_nutri = ['Calorias', 'Proteína', 'Hidratos', '(açúcar)', 'Lípidos', '(satur.)', 'Fibras', 'Sal']
            
            # Garantir que todas as colunas existem para evitar erros de cálculo
            for col in colunas_nutri:
                if col not in user_df.columns: user_df[col] = 0.0
                user_df[col] = pd.to_numeric(user_df[col], errors='coerce').fillna(0)

            diario = user_df.groupby(user_df['Data'].dt.date)[colunas_nutri].sum().reset_index()
            diario['Data'] = pd.to_datetime(diario['Data'])

            tab1, tab2 = st.tabs(["📅 Médias Semanais", "📆 Histórico Mensal"])

            with tab1:
                ultimos_dias = diario.sort_values('Data', ascending=False).head(7)
                num_ativos = len(ultimos_dias)
                st.subheader(f"Média Diária (Últimos {num_ativos} dias com registo)")
                
                # Primeira linha: Macros Principais
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🔥 Calorias", f"{ultimos_dias['Calorias'].mean():.0f} kcal")
                m2.metric("🥩 Proteína", f"{ultimos_dias['Proteína'].mean():.1f} g")
                m3.metric("🍞 Hidratos", f"{ultimos_dias['Hidratos'].mean():.1f} g")
                m4.metric("🥑 Lípidos", f"{ultimos_dias['Lípidos'].mean():.1f} g")
                
                # Segunda linha: Detalhes e Micros
                d1, d2, d3, d4 = st.columns(4)
                d1.metric("🍭 Açúcar", f"{ultimos_dias['(açúcar)'].mean():.1f} g")
                d2.metric("🍔 Gord. Satur.", f"{ultimos_dias['(satur.)'].mean():.1f} g")
                d3.metric("🌾 Fibras", f"{ultimos_dias['Fibras'].mean():.1f} g")
                d4.metric("🧂 Sal", f"{ultimos_dias['Sal'].mean():.2f} g")
                
                st.markdown("---")
                st.write("**Evolução de Calorias e Açúcar:**")
                st.line_chart(diario.set_index('Data')[['Calorias', '(açúcar)']])

            with tab2:
                diario['Mês'] = diario['Data'].dt.strftime('%Y-%m')
                mensal = diario.groupby('Mês')[colunas_nutri].mean().reset_index()
                st.write("**Média diária por mês (apenas dias com atividade):**")
                st.dataframe(mensal, hide_index=True, use_container_width=True)
        else:
            st.info(f"Ainda não existem registos válidos para {user}.")
    else:
        st.error("Erro ao carregar a base de dados.")
