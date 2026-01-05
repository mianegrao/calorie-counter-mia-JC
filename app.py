import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image

# Configuração
st.set_page_config(page_title="Nutri Control Mia & JC", page_icon="🍎")

# 1. Configurar Gemini
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("Chave API não encontrada nos Secrets!")

st.title("🍎 Nutri Control")

# 2. Carregar Excel
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        cols = ['Proteína', 'Hidratos', '(açúcar)', 'Lípidos', 'Fibras', 'Sal', 'Calorias']
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

df = load_data()
user = st.sidebar.radio("Utilizador:", ["Mia", "João Carlos"])

# --- ABAS DA APP ---
tab1, tab2, tab3 = st.tabs(["📝 Registar", "📸 Foto/IA", "📊 Totais"])

with tab1:
    if not df.empty:
        alimento_nome = st.selectbox("O que comeste?", df['ALIMENTO'].unique())
        row = df[df['ALIMENTO'] == alimento_nome].iloc[0]
        qtd = st.number_input("Quantidade (g/ml):", min_value=1.0, value=100.0)
        fator = qtd / 100
        st.metric("Calorias", f"{row['Calorias'] * fator:.1f} kcal")
        if st.button("Registar"):
            st.success("Guardado!")

with tab2:
    st.subheader("Analisar Rótulo com IA")
    foto = st.camera_input("Tire foto à tabela nutricional")
    
    if foto:
        img = Image.open(foto)
        st.image(img, caption="Imagem carregada", width=300)
        
        with st.spinner("O Gemini está a ler o rótulo..."):
            prompt = """Analisa esta tabela nutricional. Extrai os valores por 100g de: 
            Calorias, Proteína, Hidratos, Açúcar, Lípidos, Fibras e Sal. 
            Responde apenas com os números neste formato:
            Calorias: X
            Proteína: X
            Hidratos: X
            Açúcar: X
            Lípidos: X
            Fibras: X
            Sal: X"""
            
            try:
                response = model.generate_content([prompt, img])
                st.markdown("### Valores detetados (por 100g):")
                st.write(response.text)
                st.info("Pode agora copiar estes valores para o seu Excel ou registar diretamente.")
            except Exception as e:
                st.error(f"Erro na IA: {e}")

with tab3:
    st.write(f"Histórico de {user} (Em desenvolvimento)")
