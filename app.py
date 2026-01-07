import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from datetime import date
from streamlit_gsheets import GSheetsConnection
import json

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

# 1. Configurar IA
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

# 2. Conexão Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Carregar Base de Alimentos
@st.cache_data(ttl=600)
def load_food_data():
    try:
        df = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

df_alimentos = load_food_data()

# --- NAVEGAÇÃO ---
if "page" not in st.session_state:
    st.session_state.page = "Página Inicial / Registo"

# Lógica de utilizador via URL
query_params = st.query_params
user_param = query_params.get("user", "Mia")
lista_users = ["Mia", "João Carlos", "Jorge", "Celeste"]
def_idx = lista_users.index(user_param) if user_param in lista_users else 0

st.sidebar.title("🍎 Nutri & Fit Pro")
if st.sidebar.button("⬅️ VOLTAR AO INÍCIO"):
    st.session_state.page = "Página Inicial / Registo"
    st.rerun()

page = st.sidebar.selectbox("Ir para:", 
    ["Página Inicial / Registo", "Estatísticas & Médias", "Registo de Exercício", "Câmara IA"],
    key="nav_main")
user = st.sidebar.selectbox("Utilizador:", lista_users, index=def_idx)
data_sel = st.sidebar.date_input("Data:", date.today())

def get_data(worksheet_name="Sheet1"):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        return df.dropna(how='all') if df is not None else pd.DataFrame()
    except: return pd.DataFrame()

# --- PÁGINA 1: REGISTO ---
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
                "Acucar": get_v(['(açúcar)', 'Acucar', 'Açúcar', 'açúcar']),
                "Fibras": get_v(['Fibras']),
                "Sal": get_v(['Sal'])
            }
            st.info(f"Cálculo: {vals['Kcal']:.1f} kcal | {vals['Proteina']:.1f}g Proteína")

            if st.button("CONFIRMAR E GRAVAR"):
                nova_linha = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento, **{k: round(v, 2) for k, v in vals.items()}}])
                conn.update(data=pd.concat([get_data("Sheet1"), nova_linha], ignore_index=True))
                st.success("Gravado!")
                st.rerun()

    with col2:
        st.subheader(f"Totais de {data_sel}")
        df_h = get_data("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            dia_df = df_h[(df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)].copy()
            if not dia_df.empty:
                # Renomear colunas apenas para exibição
                display_df = dia_df[["Alimento", "Kcal", "Proteina", "Hidratos", "Lipidos", "Acucar", "Fibras", "Sal"]].rename(columns={
                    "Proteina": "Proteína", "Lipidos": "Lípidos", "Acucar": "Açúcar"
                })
                st.dataframe(display_df, use_container_width=True)
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Energia", f"{dia_df['Kcal'].sum():.0f} kcal")
                m2.metric("Proteína", f"{dia_df['Proteina'].sum():.1f}g")
                m3.metric("Hidratos", f"{dia_df['Hidratos'].sum():.1f}g")
                m4.metric("Lípidos", f"{dia_df['Lipidos'].sum():.1f}g")
                
                m5, m6, m7 = st.columns(3)
                m5.metric("Açúcar", f"{dia_df['Acucar'].sum():.1f}g")
                m6.metric("Fibras", f"{dia_df['Fibras'].sum():.1f}g")
                m7.metric("Sal", f"{dia_df['Sal'].sum():.2f}g")

                if st.button("🗑️ Apagar último"):
                    conn.update(data=df_h.drop(dia_df.index[-1]))
                    st.rerun()

# --- PÁGINA 4: CÂMARA IA ---
elif page == "Câmara IA":
    st.header("📸 Analisar e Guardar Novo Alimento")
    st.write("Tire foto ao rótulo para guardar os dados no Back Desk.")
    
    foto = st.camera_input("Foto do rótulo")
    if foto:
        img = Image.open(foto)
        with st.spinner("IA a extrair dados..."):
            prompt = """Extrai os valores nutricionais por 100g. 
            Responde APENAS um objeto JSON com as chaves: Alimento, Kcal, Proteina, Hidratos, Lipidos, Acucar, Fibras, Sal.
            Se não encontrares um valor, coloca 0."""
            res = model.generate_content([prompt, img])
            try:
                # Limpar a resposta da IA para garantir que é JSON puro
                json_str = res.text.replace('```json', '').replace('```', '').strip()
                data_ia = json.loads(json_str)
                
                st.subheader("Dados Extraídos:")
                # Criar DataFrame para edição antes de gravar
                df_novo = pd.DataFrame([data_ia])
                edited_df = st.data_editor(df_novo) # Permite corrigir o nome do alimento
                
                if st.button("💾 GRAVAR NA BASE DE DADOS"):
                    df_base_novos = get_data("Novos_Alimentos")
                    df_final_novos = pd.concat([df_base_novos, edited_df], ignore_index=True)
                    conn.update(worksheet="Novos_Alimentos", data=df_final_novos)
                    st.success("✅ Alimento guardado na aba 'Novos_Alimentos' do Google Sheets!")
            except:
                st.error("Erro ao processar imagem. Tente uma foto mais nítida.")
                st.write(res.text)

# (Páginas de Estatísticas e Exercício mantidas com a lógica de navegação)
