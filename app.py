import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import date, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE SUPORTE ---
@st.cache_data(ttl=5) # Atualização quase imediata
def get_data_sheets(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df is None or df.empty: return pd.DataFrame()
        df = df.dropna(how='all').reset_index(drop=True)
        # Normalização de colunas e limpeza de espaços nos dados
        df.columns = df.columns.str.strip()
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
            
        mapeamento = {'Proteina': 'Proteína', 'Acucar': '(açúcar)', 'Açúcar': '(açúcar)', 
                      'Lipidos': 'Lípidos', 'Fibra': 'Fibras', 'Kcal': 'Calorias'}
        return df.rename(columns=mapeamento)
    except: return pd.DataFrame()

# ... (restante das funções de carregamento de alimentos iguais) ...

# --- INTERFACE ---
user = st.sidebar.selectbox("Utilizador:", ["Mia", "João Carlos", "Jorge", "Celeste"])
page = st.sidebar.selectbox("Ir para:", ["Diário / Registo", "Estatísticas", "Câmara IA"])

if page == "Diário / Registo":
    # ... (lógica de registo mantida) ...
    st.header(f"📝 Diário de {user}")
    # (Inserir aqui o código de registo anterior)

elif page == "Estatísticas":
    st.header(f"📊 Estatísticas de {user}")
    df_h = get_data_sheets("Sheet1")
    
    if not df_h.empty:
        # Garante que o filtro ignora espaços e maiúsculas/minúsculas
        user_df = df_h[df_h['Utilizador'].str.upper() == user.upper()].copy()
        user_df['Data'] = pd.to_datetime(user_df['Data'], errors='coerce')
        user_df = user_df.dropna(subset=['Data'])
        
        if not user_df.empty:
            # Agrupar por dia para somar o que foi comido em cada data
            diario = user_df.groupby(user_df['Data'].dt.date).agg({
                'Calorias': 'sum', 'Proteína': 'sum', '(açúcar)': 'sum', 'Fibras': 'sum'
            }).reset_index()
            diario.columns = ['Data', 'Calorias', 'Proteína', 'Açúcar', 'Fibras']
            diario['Data'] = pd.to_datetime(diario['Data'])

            tab1, tab2 = st.tabs(["📅 Médias Semanais", "📆 Médias Mensais"])

            with tab1:
                # Média APENAS dos dias com registo (últimos 7 registos)
                ultimos_dias = diario.sort_values('Data', ascending=False).head(7)
                num_dias = len(ultimos_dias)
                
                st.subheader(f"Média baseada nos últimos {num_dias} dias ativos")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("🔥 Kcal", f"{ultimos_dias['Calorias'].mean():.0f}")
                c2.metric("🥩 Prot", f"{ultimos_dias['Proteína'].mean():.1f}g")
                c3.metric("🍭 Açúcar", f"{ultimos_dias['Açúcar'].mean():.1f}g")
                c4.metric("🌾 Fibras", f"{ultimos_dias['Fibras'].mean():.1f}g")
                st.line_chart(diario.set_index('Data')[['Calorias']])

            with tab2:
                diario['Mês'] = diario['Data'].dt.strftime('%Y-%m')
                # Média diária por mês (considerando apenas dias com entradas)
                mensal = diario.groupby('Mês').agg({
                    'Calorias': 'mean', 'Proteína': 'mean', 'Açúcar': 'mean'
                }).reset_index()
                st.write("**Média diária por mês (Dias com registo):**")
                st.dataframe(mensal, hide_index=True, use_container_width=True)
        else:
            st.warning(f"A base de dados tem dados, mas nenhum corresponde exatamente ao nome '{user}'.")
