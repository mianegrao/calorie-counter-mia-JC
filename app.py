import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from datetime import date
from streamlit_gsheets import GSheetsConnection

# Configuração da Página
st.set_page_config(page_title="Nutri Control", layout="wide")

# 1. Configurar Gemini
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')

# 2. Conexão Google Sheets
# Adicionamos 'ttl=0' para garantir que ele lê sempre dados novos e não lixo em cache
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Carregar Alimentos do Excel (GitHub)
@st.cache_data
def load_food_data():
    try:
        df = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        return df
    except:
        return pd.DataFrame()

df_alimentos = load_food_data()

# Interface Lateral
st.sidebar.header("Menu")
user = st.sidebar.radio("Utilizador:", ["Mia", "João Carlos"])
data_sel = st.sidebar.date_input("Data:", date.today())

tab1, tab2, tab3 = st.tabs(["📝 Registar", "📸 Foto/IA", "📊 Histórico"])

# --- ABA 1: REGISTO ---
with tab1:
    if not df_alimentos.empty:
        alimento = st.selectbox("Escolha o Alimento:", df_alimentos['ALIMENTO'].unique())
        row = df_alimentos[df_alimentos['ALIMENTO'] == alimento].iloc[0]
        
        qtd = st.number_input("Quantidade (g/ml):", min_value=1.0, value=100.0)
        fator = qtd / 100
        
        # Valores calculados
        res = {
            "Data": data_sel.strftime("%Y-%m-%d"),
            "Utilizador": user,
            "Alimento": alimento,
            "Kcal": round(float(row['Calorias']) * fator, 1),
            "Proteina": round(float(row['Proteína']) * fator, 1),
            "Hidratos": round(float(row['Hidratos']) * fator, 1),
            "Acucar": round(float(row.get('(açúcar)', 0)) * fator, 1),
            "Lipidos": round(float(row['Lípidos']) * fator, 1),
            "Fibras": round(float(row.get('Fibras', 0)) * fator, 1),
            "Sal": round(float(row.get('Sal', 0)) * fator, 2)
        }
        
        st.write(f"**Resumo:** {res['Kcal']} kcal | {res['Proteina']}g Prot")

        if st.button("Gravar Agora"):
            try:
                # Lógica de gravação forçada
                df_existente = conn.read()
                novo_df = pd.DataFrame([res])
                
                if df_existente is not None and not df_existente.empty:
                    # Remove linhas vazias antes de juntar
                    df_existente = df_existente.dropna(how='all')
                    df_final = pd.concat([df_existente, novo_df], ignore_index=True)
                else:
                    df_final = novo_df
                
                conn.update(data=df_final)
                st.success("✅ Guardado no Google Sheets!")
                st.balloons() # Feedback visual de sucesso
            except Exception as e:
                st.error(f"Erro ao gravar: {e}")

# --- ABA 2: FOTO / IA ---
with tab2:
    st.subheader("Análise de Rótulo")
    # Este comando força a abertura da câmara no telemóvel
    foto = st.camera_input("Tire foto à tabela nutricional", key="camera_ia")
    
    if foto:
        img = Image.open(foto)
        with st.spinner("O Gemini está a analisar..."):
            prompt = "Lê a tabela nutricional desta imagem e extrai os valores por 100g para: Calorias, Proteína, Hidratos, Açúcar, Lípidos, Fibras e Sal."
            response = model.generate_content([prompt, img])
            st.markdown("### Resultado da IA:")
            st.info(response.text)
            st.warning("Dica: Adicione estes valores ao seu ficheiro alimentos.xlsx no GitHub para que fiquem disponíveis na lista.")

# --- ABA 3: HISTÓRICO ---
with tab3:
    st.subheader(f"Diário de {user}")
    try:
        # Forçamos a leitura sem cache (ttl=0)
        df_hist = conn.read(ttl=0)
        if df_hist is not None and not df_hist.empty:
            df_hist['Data'] = df_hist['Data'].astype(str)
            dia_str = data_sel.strftime("%Y-%m-%d")
            
            filtro = df_hist[(df_hist['Data'] == dia_str) & (df_hist['Utilizador'] == user)]
            
            if not filtro.empty:
                st.dataframe(filtro)
                total_kcal = filtro['Kcal'].sum()
                st.metric("Total Calorias", f"{total_kcal:.1f} kcal")
            else:
                st.write("Sem registos para hoje.")
        else:
            st.write("A folha está vazia.")
    except:
        st.write("Ainda não foi possível ler os dados.")
