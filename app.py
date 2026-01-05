import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from datetime import date
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Nutri Control Mia & JC", layout="wide", page_icon="🍎")

# 1. Configurar Gemini (IA)
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')

# 2. Ligar ao Google Sheets (Histórico)
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Carregar Base de Alimentos (do Excel no GitHub)
@st.cache_data
def load_food_data():
    try:
        df = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        cols = ['Proteína', 'Hidratos', '(açúcar)', 'Lípidos', 'Fibras', 'Sal', 'Calorias']
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame()

df_alimentos = load_food_data()

# --- INTERFACE ---
st.title("🍎 Nutri Control Profissional")

# Barra Lateral
st.sidebar.header("Painel de Controlo")
user = st.sidebar.radio("Utilizador:", ["Mia", "João Carlos"])
data_sel = st.sidebar.date_input("Data:", date.today())

tabs = st.tabs(["📝 Registar", "📸 Foto/IA", "📅 Histórico Real"])

# ABA 1: REGISTO
with tabs[0]:
    if not df_alimentos.empty:
        alimento = st.selectbox("O que comeste?", df_alimentos['ALIMENTO'].unique())
        row = df_alimentos[df_alimentos['ALIMENTO'] == alimento].iloc[0]
        
        qtd = st.number_input("Quantidade (g ou ml):", min_value=1.0, value=100.0)
        fator = qtd / 100
        
        # Preparar dados para gravar
        v_kcal = row['Calorias'] * fator
        v_prot = row['Proteína'] * fator
        v_hid = row['Hidratos'] * fator
        v_lip = row['Lípidos'] * fator
        v_acucar = row['(açúcar)'] * fator
        v_fibra = row['Fibras'] * fator
        v_sal = row['Sal'] * fator
        
        st.metric("Calorias", f"{v_kcal:.1f} kcal")
        
        if st.button("Confirmar e Gravar no Histórico"):
            # Criar linha para o Google Sheets
            novo_registo = pd.DataFrame([{
                "Data": data_sel.strftime("%Y-%m-%d"),
                "Utilizador": user,
                "Alimento": alimento,
                "Kcal": round(v_kcal, 1),
                "Proteina": round(v_prot, 1),
                "Hidratos": round(v_hid, 1),
                "Acucar": round(v_acucar, 1),
                "Lipidos": round(v_lip, 1),
                "Fibras": round(v_fibra, 1),
                "Sal": round(v_sal, 2)
            }])
            
            # Ler dados atuais, juntar novo e gravar
            try:
                dados_atuais = conn.read()
                df_final = pd.concat([dados_atuais, novo_registo], ignore_index=True)
                conn.update(data=df_final)
                st.success("Gravado com sucesso no Google Sheets!")
                st.cache_data.clear() # Limpa cache para atualizar histórico
            except Exception as e:
                st.error(f"Erro ao gravar: {e}")

# ABA 2: FOTO / IA
with tabs[1]:
    st.subheader("Analisar Rótulo")
    foto = st.camera_input("Foto da tabela nutricional")
    if foto:
        img = Image.open(foto)
        with st.spinner("IA a analisar..."):
            prompt = "Lê a tabela nutricional e diz os valores por 100g: Calorias, Proteína, Hidratos, Açúcar, Lípidos, Fibras e Sal."
            res = model.generate_content([prompt, img])
            st.write(res.text)

# ABA 3: HISTÓRICO
with tabs[2]:
    st.subheader(f"Registos de {user}")
    try:
        historico_completo = conn.read()
        if not historico_completo.empty:
            # Filtrar por data e utilizador
            historico_completo['Data'] = historico_completo['Data'].astype(str)
            filtro = historico_completo[
                (historico_completo['Data'] == data_sel.strftime("%Y-%m-%d")) & 
                (historico_completo['Utilizador'] == user)
            ]
            
            if not filtro.empty:
                st.dataframe(filtro)
                st.metric("Total Calorias do Dia", f"{filtro['Kcal'].sum():.1f} kcal")
            else:
                st.info("Sem registos para este dia.")
    except:
        st.write("Ainda não existem dados no Google Sheets.")
