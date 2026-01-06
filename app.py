import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from datetime import date
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Nutri Control", layout="wide", page_icon="🍎")

# 1. Configurar IA (Gemini)
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # Usar a versão estável mais recente para evitar o erro NotFound
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
else:
    st.error("Chave API do Gemini não configurada nos Secrets!")

# 2. Ligar ao Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Erro na ligação ao Google Sheets: {e}")

# 3. Carregar Base de Alimentos (Excel do GitHub)
@st.cache_data(ttl=600)
def load_food_data():
    try:
        df = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        # Garantir que as colunas críticas são numéricas
        for col in ['Proteína', 'Hidratos', 'Calorias']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Erro ao ler alimentos.xlsx: {e}")
        return pd.DataFrame()

df_alimentos = load_food_data()

# --- INTERFACE PRINCIPAL ---
st.title("🍎 Nutri Control Mia & JC")

# Barra Lateral
st.sidebar.header("Painel")
user = st.sidebar.radio("Utilizador:", ["Mia", "João Carlos"])
data_sel = st.sidebar.date_input("Data do Registo:", date.today())

# Separadores
tabs = st.tabs(["📝 Registar", "📸 Foto/IA", "📊 Histórico"])

# ABA 1: REGISTO MANUAL (Lógica de Coeficiente)
with tabs[0]:
    if not df_alimentos.empty:
        alimento = st.selectbox("Selecione o Alimento:", df_alimentos['ALIMENTO'].unique())
        row = df_alimentos[df_alimentos['ALIMENTO'] == alimento].iloc[0]
        
        # O João Carlos usa coeficientes (ex: 1 para 1 dose, 0.5 para meia)
        qtd = st.number_input("Quantidade (Coeficiente/Doses):", min_value=0.01, value=1.00, step=0.05)
        
        v_kcal = float(row['Calorias']) * qtd
        v_prot = float(row['Proteína']) * qtd
        
        st.info(f"Cálculo: {v_kcal:.1f} kcal | {v_prot:.1f}g Proteína")
        
        if st.button("CONFIRMAR E GRAVAR"):
            try:
                nova_linha = pd.DataFrame([{
                    "Data": str(data_sel),
                    "Utilizador": user,
                    "Alimento": alimento,
                    "Kcal": round(v_kcal, 1),
                    "Proteina": round(v_prot, 1)
                }])
                
                # Ler histórico e anexar
                df_atual = conn.read(ttl=0)
                if df_atual is not None and not df_atual.empty:
                    df_final = pd.concat([df_atual, nova_linha], ignore_index=True)
                else:
                    df_final = nova_linha
                
                conn.update(data=df_final)
                st.success("✅ Gravado no Diário!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao gravar dados: {e}")
    else:
        st.warning("A base de alimentos.xlsx não foi carregada.")

# ABA 2: CÂMARA E IA (Extrair de rótulo)
with tabs[1]:
    st.subheader("Analisar Tabela Nutricional")
    foto = st.camera_input("Tire foto ao rótulo", key="cam_v3")
    
    if foto:
        img = Image.open(foto)
        with st.spinner("O Gemini está a analisar a imagem..."):
            try:
                prompt = "Identifica os valores por 100g para: Calorias, Proteína, Hidratos, Açúcar, Lípidos, Fibras e Sal. Responde apenas os valores."
                response = model.generate_content([prompt, img])
                st.markdown("### Valores detetados pela IA:")
                st.write(response.text)
                st.warning("Nota: Adicione estes valores ao seu ficheiro alimentos.xlsx no computador para que apareçam na lista de registo.")
            except Exception as e:
                st.error(f"A IA encontrou um problema: {e}")

# ABA 3: HISTÓRICO E TOTAIS
with tabs[2]:
    st.subheader(f"Diário de {user} - {data_sel}")
    try:
        df_hist = conn.read(ttl=0)
        if df_hist is not None and not df_hist.empty:
            # Converter coluna Data para texto para filtrar corretamente
            df_hist['Data'] = df_hist['Data'].astype(str)
            dia_str = str(data_sel)
            
            filtro = df_hist[(df_hist['Data'] == dia_str) & (df_hist['Utilizador'] == user)]
            
            if not filtro.empty:
                st.dataframe(filtro[["Alimento", "Kcal", "Proteina"]], use_container_width=True)
                st.metric("Total Calorias", f"{filtro['Kcal'].sum():.1f} kcal")
                st.metric("Total Proteína", f"{filtro['Proteina'].sum():.1f} g")
            else:
                st.write("Sem registos para o dia selecionado.")
        else:
            st.write("A base de dados do histórico está vazia.")
    except Exception as e:
        st.write("Ainda não existem dados gravados ou houve um erro na leitura.")
