import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from datetime import date
from streamlit_gsheets import GSheetsConnection

# Configuração Base
st.set_page_config(page_title="Nutri Control", layout="wide")

# Conexões
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')

conn = st.connection("gsheets", type=GSheetsConnection)

# Carregar Alimentos
@st.cache_data(ttl=600)
def load_food():
    return pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")

df_alimentos = load_food()

# --- INTERFACE ---
st.title("🍎 Nutri Control Mia & JC")

user = st.sidebar.radio("Utilizador:", ["Mia", "João Carlos"])
data_sel = st.sidebar.date_input("Data:", date.today())

# BOTÃO DA CÂMARA (Fora das abas para garantir visibilidade)
with st.expander("📸 ANALISAR RÓTULO COM IA"):
    foto = st.camera_input("Tire foto aqui")
    if foto:
        img = Image.open(foto)
        with st.spinner("IA a ler..."):
            res = model.generate_content(["Diz os valores por 100g de: Calorias, Proteína, Hidratos, Açúcar, Lípidos, Fibras e Sal.", img])
            st.info(res.text)

st.divider()

# --- REGISTO E HISTÓRICO ---
col_reg, col_hist = st.columns([1, 1])

with col_reg:
    st.subheader("📝 Registar")
    if not df_alimentos.empty:
        alimento = st.selectbox("Alimento:", df_alimentos['ALIMENTO'].unique())
        row = df_alimentos[df_alimentos['ALIMENTO'] == alimento].iloc[0]
        
        # Lógica de Coeficiente (Ex: 1 = 1 dose, 0.5 = meia dose)
        qtd = st.number_input("Quantidade (Doses/Coeficiente):", min_value=0.1, value=1.0, step=0.1)
        
        # Cálculo baseado no seu Excel original
        v_kcal = float(row['Calorias']) * qtd
        v_prot = float(row['Proteína']) * qtd
        
        st.write(f"**Total para este registo:** {v_kcal:.1f} kcal")

        if st.button("GRAVAR REGISTO"):
            try:
                # Criar nova linha
                nova_linha = pd.DataFrame([{
                    "Data": str(data_sel),
                    "Utilizador": user,
                    "Alimento": alimento,
                    "Kcal": round(v_kcal, 1),
                    "Proteina": round(v_prot, 1)
                }])
                
                # Forçar leitura e escrita imediata
                df_atual = conn.read(ttl=0)
                df_novo = pd.concat([df_atual, nova_linha], ignore_index=True) if df_atual is not None else nova_linha
                conn.update(data=df_novo)
                
                st.success("✅ Gravado!")
                st.rerun() # Força a app a atualizar e mostrar no histórico
            except Exception as e:
                st.error(f"Erro: {e}")

with col_hist:
    st.subheader(f"📊 Totais de {user}")
    try:
        df_hist = conn.read(ttl=0)
        if df_hist is not None and not df_hist.empty:
            # Filtro simples
            filtro = df_hist[(df_hist['Data'] == str(data_sel)) & (df_hist['Utilizador'] == user)]
            if not filtro.empty:
                st.dataframe(filtro)
                st.metric("Calorias Totais", f"{filtro['Kcal'].sum():.1f} kcal")
            else:
                st.write("Sem dados para hoje.")
    except:
        st.write("Histórico indisponível.")
