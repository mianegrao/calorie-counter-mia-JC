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
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df is not None:
            return df.dropna(how='all')
        return pd.DataFrame()
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
                "Acucar": get_v(['(açúcar)', 'Acucar', 'Açúcar']),
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

# --- PÁGINA 2: ESTATÍSTICAS & MÉDIAS ---
elif page == "Estatísticas & Médias":
    st.header(f"📊 Análise Global - {user}")
    
    # 1. Obter dados de Alimentação
    df_h = get_data("Sheet1")
    # 2. Obter dados de Exercício
    df_ex = get_data("Exercicio")
    
    if not df_h.empty:
        df_h['Data'] = pd.to_datetime(df_h['Data'], errors='coerce')
        df_h = df_h.dropna(subset=['Data'])
        df_u = df_h[df_h['Utilizador'] == user]
        
        if not df_u.empty:
            # Agrupar alimentação por dia
            diario_nutri = df_u.groupby('Data').agg({
                'Kcal': 'sum', 'Proteina': 'sum', 'Hidratos': 'sum', 'Acucar': 'sum', 'Fibras': 'sum'
            }).sort_index()

            # Processar Exercício para o utilizador
            if not df_ex.empty:
                df_ex['Data'] = pd.to_datetime(df_ex['Data'], errors='coerce')
                df_ex_u = df_ex[df_ex['Utilizador'] == user]
                diario_ex = df_ex_u.groupby('Data').agg({'Duracao': 'sum'}).sort_index()
            else:
                diario_ex = pd.DataFrame(columns=['Duracao'])

            # Função para mostrar métricas incluindo Exercício
            def mostrar_resumo(titulo, df_nutri_sub, df_ex_sub):
                st.markdown(f"### {titulo}")
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                c1.metric("Energia", f"{df_nutri_sub['Kcal'].mean():.0f} kcal")
                c2.metric("Prot.", f"{df_nutri_sub['Proteina'].mean():.1f}g")
                c3.metric("Hidr.", f"{df_nutri_sub['Hidratos'].mean():.1f}g")
                c4.metric("Açúcar", f"{df_nutri_sub['Acucar'].mean():.1f}g")
                c5.metric("Fibras", f"{df_nutri_sub['Fibras'].mean():.1f}g")
                
                # Média de exercício para os dias em que houve treino
                avg_ex = df_ex_sub['Duracao'].mean() if not df_ex_sub.empty else 0
                c6.metric("🏋️ Treino", f"{avg_ex:.0f} min", delta_color="normal")

            st.divider()
            mostrar_resumo("Últimos 7 dias com registo", diario_nutri.tail(7), diario_ex.tail(7))
            st.divider()
            mostrar_resumo("Últimos 30 dias com registo", diario_nutri.tail(30), diario_ex.tail(30))
            st.divider()
            mostrar_resumo("Média Histórica Total", diario_nutri, diario_ex)
            
            # Gráficos
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.subheader("Consumo Calórico")
                st.line_chart(diario_nutri['Kcal'])
            with col_g2:
                st.subheader("Tempo de Exercício (min)")
                if not diario_ex.empty:
                    st.bar_chart(diario_ex['Duracao'])
                else:
                    st.write("Sem dados de exercício.")
        else:
            st.warning("Sem dados de alimentação para este utilizador.")
    else:
        st.info("O histórico está vazio.")

# --- PÁGINA 3: EXERCÍCIO ---
elif page == "Registo de Exercício":
    st.header("🏃 Registo de Atividade Física")
    modalidades = ["Corrida", "Treino de Força", "Remo", "Biking", "Caminhada", "Yoga", "Pilates", "Escadas", "Treino Funcional", "HIIT"]
    tipo = st.selectbox("Modalidade:", modalidades)
    tempo = st.number_input("Duração (minutos):", min_value=1, value=45)
    
    if st.button("GRAVAR TREINO"):
        try:
            novo_t = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Modalidade": tipo, "Duracao": tempo}])
            df_ex_atual = get_data("Exercicio")
            df_ex_final = pd.concat([df_ex_atual, novo_t], ignore_index=True) if not df_ex_atual.empty else novo_t
            conn.update(worksheet="Exercicio", data=df_ex_final)
            st.success(f"Treino de {tipo} guardado!")
            st.rerun()
        except:
            st.error("Certifica-te que criaste a aba 'Exercicio' no Sheets.")

# --- PÁGINA 4: CÂMARA IA ---
elif page == "Câmara IA":
    st.header("📸 Analisar Rótulo")
    foto = st.camera_input("Foto do rótulo")
    if foto:
        img = Image.open(foto)
        with st.spinner("IA a ler..."):
            try:
                res = model.generate_content(["Identifica valores por 100g para: Calorias, Proteína, Hidratos, Açúcar, Lípidos, Fibras e Sal.", img])
                st.info(res.text)
            except Exception as e:
                st.error(f"Erro na IA: {e}")
