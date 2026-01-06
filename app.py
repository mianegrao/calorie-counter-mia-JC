import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from datetime import date, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

# 1. Configurar IA
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

# 2. Conexão Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Carregar Base de Alimentos (Excel GitHub)
@st.cache_data(ttl=600)
def load_food_data():
    try:
        df = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

df_alimentos = load_food_data()

# --- NAVEGAÇÃO LATERAL ---
st.sidebar.title("🍎 Nutri & Fit Pro")
page = st.sidebar.selectbox("Ir para:", 
    ["Página Inicial / Registo", "Estatísticas & Médias", "Registo de Exercício", "Câmara IA"])

user = st.sidebar.selectbox("Utilizador:", ["Mia", "João Carlos", "Jorge", "Celeste"])
data_sel = st.sidebar.date_input("Data de referência:", date.today())

# --- FUNÇÃO PARA LER DADOS ---
def get_data(worksheet_name="Sheet1"):
    try:
        return conn.read(worksheet=worksheet_name, ttl=0).dropna(how='all')
    except:
        return pd.DataFrame()

# --- PÁGINA 1: REGISTO E TOTAIS ---
if page == "Página Inicial / Registo":
    st.header(f"📝 Diário de {user}")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Novo Registo")
        if not df_alimentos.empty:
            alimento = st.selectbox("Escolher Alimento:", df_alimentos['ALIMENTO'].unique())
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento].iloc[0]
            qtd = st.number_input("Quantidade (Coeficiente):", min_value=0.01, value=1.00, step=0.05)
            
            def get_v(names):
                for n in names:
                    if n in row: return float(row[n]) * qtd
                return 0.0

            vals = {
                "Kcal": get_v(['Calorias', 'Kcal']),
                "Proteina": get_v(['Proteína', 'Proteina']),
                "Hidratos": get_v(['Hidratos']),
                "Lipidos": get_v(['Lípidos', 'Lipidos']),
                "Acucar": get_v(['(açúcar)', 'Acucar']),
                "Fibras": get_v(['Fibras']),
                "Sal": get_v(['Sal'])
            }

            st.info(f"Cálculo atual: {vals['Kcal']:.1f} kcal | {vals['Proteina']:.1f}g Prot")

            if st.button("CONFIRMAR E GRAVAR"):
                try:
                    nova_linha = pd.DataFrame([{
                        "Data": str(data_sel), "Utilizador": user, "Alimento": alimento,
                        **{k: round(v, 2) for k, v in vals.items()}
                    }])
                    df_atual = get_data("Sheet1")
                    df_final = pd.concat([df_atual, nova_linha], ignore_index=True)
                    conn.update(data=df_final)
                    st.success("Gravado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao gravar: {e}")

    with col2:
        st.subheader(f"Totais de {data_sel}")
        df_h = get_data("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            dia_df = df_h[(df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)]
            
            if not dia_df.empty:
                st.dataframe(dia_df[["Alimento", "Kcal", "Proteina", "Hidratos", "Lipidos"]], use_container_width=True)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Energia", f"{dia_df['Kcal'].sum():.0f} kcal")
                m2.metric("Proteína", f"{dia_df['Proteina'].sum():.1f}g")
                m3.metric("Hidratos", f"{dia_df['Hidratos'].sum():.1f}g")
                m4.metric("Lípidos", f"{dia_df['Lipidos'].sum():.1f}g")

                if st.button("🗑️ Apagar último registo"):
                    df_res = df_h.drop(dia_df.index[-1])
                    conn.update(data=df_res)
                    st.rerun()
            else:
                st.info("Sem registos hoje.")

# --- PÁGINA 2: ESTATÍSTICAS ---
elif page == "Estatísticas & Médias":
    st.header(f"📊 Médias de {user}")
    df_h = get_data("Sheet1")
    if not df_h.empty:
        df_h['Data'] = pd.to_datetime(df_h['Data'])
        df_u = df_h[df_h['Utilizador'] == user]
        if not df_u.empty:
            diario = df_u.groupby('Data').agg({'Kcal': 'sum', 'Proteina': 'sum'})
            
            st.subheader("Médias Reais (Dias com registo)")
            c1, c2, c3 = st.columns(3)
            # Média dos últimos 7 registos
            c1.metric("Média Semanal", f"{diario.tail(7)['Kcal'].mean():.0f} kcal")
            # Média dos últimos 30 registos
            c2.metric("Média Mensal", f"{diario.tail(30)['Kcal'].mean():.0f} kcal")
            # Média total
            c3.metric("Média Anual", f"{diario['Kcal'].mean():.0f} kcal")
            
            st.line_chart(diario['Kcal'])

# --- PÁGINA 3: EXERCÍCIO ---
elif page == "Registo de Exercício":
    st.header("🏃 Registo de Atividade Física")
    
    # Lista exata das modalidades solicitadas
    modalidades = [
        "Corrida", "Treino de Força", "Remo", "Biking", 
        "Caminhada", "Yoga", "Pilates", "Escadas", 
        "Treino Funcional", "HIIT"
    ]
    
    tipo = st.selectbox("Modalidade:", modalidades)
    tempo = st.number_input("Duração (minutos):", min_value=1, value=45)
    
    if st.button("GRAVAR TREINO"):
        try:
            novo_t = pd.DataFrame([{
                "Data": str(data_sel), 
                "Utilizador": user, 
                "Modalidade": tipo, 
                "Duracao": tempo
            }])
            
            # Tentar ler a aba 'Exercicio'
            df_ex = get_data("Exercicio")
            
            if df_ex.empty:
                df_final_ex = novo_t
            else:
                df_final_ex = pd.concat([df_ex, novo_t], ignore_index=True)
            
            # Gravação na aba específica
            conn.update(worksheet="Exercicio", data=df_final_ex)
            st.success(f"Treino de {tipo} ({tempo} min) guardado com sucesso!")
            
        except Exception as e:
            st.error(f"Erro: Certifica-te de que criaste a aba 'Exercicio' no Google Sheets com os cabeçalhos: Data, Utilizador, Modalidade, Duracao. Erro: {e}")

# --- PÁGINA 4: CÂMARA IA ---
elif page == "Câmara IA":
    st.header("📸 Analisar Rótulo")
    foto = st.camera_input("Foto do rótulo")
    if foto:
        img = Image.open(foto)
        with st.spinner("IA a ler..."):
            try:
                res = model.generate_content(["Identifica os valores por 100g para: Calorias, Proteína, Hidratos, Açúcar, Lípidos, Fibras e Sal.", img])
                st.info(res.text)
            except Exception as e:
                st.error(f"Erro na IA: {e}")
