import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from datetime import datetime, date, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

# 1. IA e Conexões
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

conn = st.connection("gsheets", type=GSheetsConnection)

# 2. Carregar Alimentos (Excel GitHub)
@st.cache_data(ttl=600)
def load_food_data():
    try:
        df = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        # Limpeza de nomes de colunas para evitar erros de acentos no código
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

df_alimentos = load_food_data()

# --- NAVEGAÇÃO LATERAL ---
st.sidebar.title("🍎 Nutri & Fit")
page = st.sidebar.selectbox("Ir para:", ["Registo Diário", "Estatísticas & Médias", "Exercício Físico", "Câmara IA"])
user = st.sidebar.selectbox("Utilizador:", ["Mia", "João Carlos", "Jorge", "Celeste"])
data_sel = st.sidebar.date_input("Data:", date.today())

# --- FUNÇÕES DE APOIO ---
def get_full_data():
    try:
        return conn.read(ttl=0).dropna(how='all')
    except:
        return pd.DataFrame()

# --- PÁGINA 1: REGISTO DIÁRIO ---
if page == "Registo Diário":
    st.header(f"📝 Registo de {user}")
    
    if not df_alimentos.empty:
        alimento = st.selectbox("Alimento:", df_alimentos['ALIMENTO'].unique())
        # Mapeamento dinâmico para lidar com acentos no Excel original
        row = df_alimentos[df_alimentos['ALIMENTO'] == alimento].iloc[0]
        
        qtd = st.number_input("Quantidade (Coeficiente):", min_value=0.01, value=1.00, step=0.05)
        
        # Cálculo de todos os macros (lidando com possíveis nomes de colunas do Excel)
        def get_val(col_name):
            return float(row[col_name]) if col_name in row else 0.0

        v_kcal = get_val('Calorias') * qtd
        v_prot = get_val('Proteína') * qtd
        v_hidr = get_val('Hidratos') * qtd
        v_lip = get_val('Lípidos') * qtd
        v_acuc = get_val('(açúcar)') * qtd
        v_fibr = get_val('Fibras') * qtd
        v_sal = get_val('Sal') * qtd

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Energia", f"{v_kcal:.1f} kcal")
        c2.metric("Proteína", f"{v_prot:.1f} g")
        c3.metric("Hidratos", f"{v_hidr:.1f} g")
        c4.metric("Lípidos", f"{v_lip:.1f} g")

        if st.button("GRAVAR REFEIÇÃO"):
            nova_linha = pd.DataFrame([{
                "Data": str(data_sel), "Utilizador": user, "Alimento": alimento,
                "Kcal": round(v_kcal, 1), "Proteina": round(v_prot, 1),
                "Hidratos": round(v_hidr, 1), "Lipidos": round(v_lip, 1),
                "Acucar": round(v_acuc, 1), "Fibras": round(v_fibr, 1), "Sal": round(v_sal, 2)
            }])
            df_atual = get_full_data()
            df_final = pd.concat([df_atual, nova_linha], ignore_index=True)
            conn.update(data=df_final)
            st.success("Gravado!")
            st.rerun()

    st.divider()
    st.subheader("Totais do Dia")
    df_h = get_full_data()
    if not df_h.empty:
        df_h['Data'] = df_h['Data'].astype(str)
        dia_df = df_h[(df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)]
        
        if not dia_df.empty:
            st.dataframe(dia_df)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Kcal Total", f"{dia_df['Kcal'].sum():.1f}")
            m2.metric("Prot Total", f"{dia_df['Proteina'].sum():.1f}g")
            m3.metric("Hidr Total", f"{dia_df['Hidratos'].sum():.1f}g")
            m4.metric("Lip Total", f"{dia_df['Lipidos'].sum():.1f}g")
            
            if st.button("🗑️ Eliminar ÚLTIMO registo deste dia"):
                df_h = df_h.drop(dia_df.index[-1])
                conn.update(data=df_h)
                st.warning("Registo removido.")
                st.rerun()
        else:
            st.info("Sem registos hoje.")

# --- PÁGINA 2: ESTATÍSTICAS & MÉDIAS ---
elif page == "Estatísticas & Médias":
    st.header(f"📊 Médias e Tendências - {user}")
    df_h = get_full_data()
    
    if not df_h.empty:
        df_h['Data'] = pd.to_datetime(df_h['Data'])
        df_user = df_h[df_h['Utilizador'] == user]
        
        if not df_user.empty:
            # Agrupar por dia para ter a soma diária antes das médias
            diario = df_user.groupby('Data').agg({'Kcal': 'sum', 'Proteina': 'sum', 'Hidratos': 'sum', 'Lipidos': 'sum'})
            
            # Filtros de Médias
            hoje = pd.Timestamp(date.today())
            sem_passada = diario[diario.index > (hoje - timedelta(days=7))]
            mes_passado = diario[diario.index > (hoje - timedelta(days=30))]
            
            st.subheader("Médias Reais (Apenas dias com registo)")
            c1, c2, c3 = st.columns(3)
            c1.metric("Média Semanal", f"{sem_passada['Kcal'].mean():.0f} kcal")
            c2.metric("Média Mensal", f"{mes_passado['Kcal'].mean():.0f} kcal")
            c3.metric("Média Anual", f"{diario['Kcal'].mean():.0f} kcal")
            
            st.line_chart(diario['Kcal'])
        else:
            st.write("Sem dados para este utilizador.")

# --- PÁGINA 3: EXERCÍCIO FÍSICO ---
elif page == "Exercício Físico":
    st.header("🏃 Registo de Atividade")
    tipo = st.selectbox("Modalidade:", ["Corrida", "Treino de Força", "Remo", "Biking", "Caminhada", "Yoga", "Pilates", "Escadas", "Treino Funcional", "HIIT"])
    duracao = st.number_input("Duração (minutos):", min_value=1, value=30)
    
    if st.button("Gravar Treino"):
        st.success(f"Treino de {tipo} ({duracao} min) gravado! (Nota: Requer aba 'Exercicio' no Sheets)")
        # Lógica de gravação na aba de exercício pode ser expandida aqui

# --- PÁGINA 4: CÂMARA IA ---
elif page == "Câmara IA":
    st.header("📸 Analisar Rótulo")
    foto = st.camera_input("Foto da tabela nutricional")
    if foto:
        img = Image.open(foto)
        with st.spinner("IA a ler..."):
            res = model.generate_content(["Lê os valores por 100g de Calorias, Proteína, Hidratos, Açúcar, Lípidos, Fibras e Sal.", img])
            st.info(res.text)
