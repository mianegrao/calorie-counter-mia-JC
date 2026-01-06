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

# 2. Ligar ao Google Sheets (Base de Dados)
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Carregar Base de Alimentos (Excel do GitHub)
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
st.title("🍎 Nutri Control")

# Barra Lateral
st.sidebar.header("Definições")
user = st.sidebar.radio("Utilizador:", ["Mia", "João Carlos"])
data_sel = st.sidebar.date_input("Data Selecionada:", date.today())

tabs = st.tabs(["📝 Registar", "📸 Foto/IA", "📅 Histórico Diário"])

# ABA 1: REGISTO
with tabs[0]:
    if not df_alimentos.empty:
        alimento = st.selectbox("O que comeste?", df_alimentos['ALIMENTO'].unique())
        row = df_alimentos[df_alimentos['ALIMENTO'] == alimento].iloc[0]
        
        qtd = st.number_input("Quantidade (g ou ml):", min_value=1.0, value=100.0)
        fator = qtd / 100
        
        # Cálculos
        v_kcal = row['Calorias'] * fator
        v_prot = row['Proteína'] * fator
        v_hid = row['Hidratos'] * fator
        v_lip = row['Lípidos'] * fator
        v_acucar = row.get('(açúcar)', 0) * fator
        v_fibra = row.get('Fibras', 0) * fator
        v_sal = row.get('Sal', 0) * fator
        
        st.metric("Energia Estimada", f"{v_kcal:.1f} kcal")
        
        if st.button("Confirmar e Gravar"):
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
            
            try:
                # Tenta ler o histórico atual
                try:
                    historico_atual = conn.read()
                    if historico_atual is None or historico_atual.empty:
                        df_final = novo_registo
                    else:
                        df_final = pd.concat([historico_atual, novo_registo], ignore_index=True)
                except:
                    df_final = novo_registo
                
                # Atualiza a folha
                conn.update(data=df_final)
                st.success("✅ Registado no Google Sheets!")
                st.cache_data.clear() # Força a atualização do separador Histórico
            except Exception as e:
                st.error(f"Erro ao gravar: {e}")

# ABA 2: FOTO / IA
with tabs[1]:
    st.subheader("Analisar Rótulo")
    foto = st.camera_input("Tirar foto")
    if foto:
        img = Image.open(foto)
        with st.spinner("IA a analisar..."):
            prompt = "Lê a tabela nutricional e diz os valores por 100g: Calorias, Proteína, Hidratos, Açúcar, Lípidos, Fibras e Sal."
            res = model.generate_content([prompt, img])
            st.write(res.text)

# ABA 3: HISTÓRICO
with tabs[2]:
    st.subheader(f"Diário de {user} - {data_sel}")
    try:
        # Lê sempre a versão mais recente
        df_historico = conn.read()
        if df_historico is not None and not df_historico.empty:
            # Garantir que a coluna Data é string para o filtro
            df_historico['Data'] = df_historico['Data'].astype(str)
            dia_str = data_sel.strftime("%Y-%m-%d")
            
            filtro = df_historico[(df_historico['Data'] == dia_str) & (df_historico['Utilizador'] == user)]
            
            if not filtro.empty:
                st.dataframe(filtro)
                st.metric("Total de Calorias", f"{filtro['Kcal'].sum():.1f} kcal")
                st.metric("Total de Proteína", f"{filtro['Proteina'].sum():.1f} g")
            else:
                st.info("Ainda não tens registos para este dia.")
        else:
            st.info("O histórico está totalmente vazio.")
    except Exception as e:
        st.error(f"Não foi possível carregar o histórico: {e}")
