import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from datetime import date
from streamlit_gsheets import GSheetsConnection
import json
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

# 1. Configurar IA
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

# 2. Conexão Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Carregar Base de Alimentos (Excel GitHub)
@st.cache_data(ttl=3600)
def load_food_data():
    try:
        df = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=['ALIMENTO'])
        return df.sort_values(by='ALIMENTO')
    except:
        return pd.DataFrame()

df_alimentos = load_food_data()

# --- FUNÇÃO DE LEITURA COM CACHE ---
@st.cache_data(ttl=120)
def get_data_cached(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        return df.dropna(how='all') if df is not None else pd.DataFrame()
    except:
        return pd.DataFrame()

# --- NAVEGAÇÃO ---
if "page" not in st.session_state:
    st.session_state.page = "Página Inicial / Registo"

query_params = st.query_params
user_param = query_params.get("user", "Mia")
lista_users = ["Mia", "João Carlos", "Jorge", "Celeste"]
def_idx = lista_users.index(user_param) if user_param in lista_users else 0

st.sidebar.title("🍎 Nutri & Fit Pro")
if st.sidebar.button("⬅️ VOLTAR AO INÍCIO"):
    st.session_state.page = "Página Inicial / Registo"
    st.rerun()

page = st.sidebar.selectbox("Ir para:", 
    ["Página Inicial / Registo", "Estatísticas & Médias", "Registo de Exercício", "Câmara IA"], key="nav_main")
user = st.sidebar.selectbox("Utilizador:", lista_users, index=def_idx)
data_sel = st.sidebar.date_input("Data:", date.today())

# --- PÁGINA 1: REGISTO ---
if page == "Página Inicial / Registo":
    st.header(f"📝 Diário de {user}")
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Novo Registo")
        opcoes_alimentos = list(df_alimentos['ALIMENTO'].unique())
        
        alimento_sel = st.selectbox(
            "Pesquisar Alimento:", 
            options=opcoes_alimentos, 
            index=None, 
            placeholder="Escreva para procurar..."
        )

        add_novo = st.checkbox("➕ Não encontrei? Adicionar novo alimento à base")

        if add_novo:
            st.markdown("---")
            with st.form("form_novo_alimento"):
                n_nome = st.text_input("Nome do Alimento:")
                c1, c2 = st.columns(2)
                n_kcal = c1.number_input("Kcal (por 100g/dose)", min_value=0.0, step=1.0)
                n_prot = c2.number_input("Proteína (g)", min_value=0.0, step=0.1)
                
                c3, c4 = st.columns(2)
                n_hid = c3.number_input("Hidratos (g)", min_value=0.0, step=0.1)
                n_lip = c4.number_input("Lípidos (g)", min_value=0.0, step=0.1)
                
                c5, c6 = st.columns(2)
                n_acu = c5.number_input("Açúcar (g)", min_value=0.0, step=0.1)
                n_fib = c6.number_input("Fibras (g)", min_value=0.0, step=0.1)
                n_sal = st.number_input("Sal (g)", min_value=0.0, step=0.01)
                
                if st.form_submit_button("💾 GUARDAR E REGISTAR"):
                    if n_nome:
                        try:
                            # Gravar na aba de Novos_Alimentos
                            novo_df = pd.DataFrame([{"Alimento": n_nome, "Kcal": n_kcal, "Proteina": n_prot, "Hidratos": n_hid, "Lipidos": n_lip, "Acucar": n_acu, "Fibras": n_fib, "Sal": n_sal}])
                            conn.update(worksheet="Novos_Alimentos", data=pd.concat([get_data_cached("Novos_Alimentos"), novo_df], ignore_index=True))
                            
                            # Registar no diário (Sheet1)
                            nova_l = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": n_nome, "Kcal": n_kcal, "Proteina": n_prot, "Hidratos": n_hid, "Lipidos": n_lip, "Acucar": n_acu, "Fibras": n_fib, "Sal": n_sal}])
                            st.cache_data.clear()
                            conn.update(worksheet="Sheet1", data=pd.concat([conn.read(worksheet="Sheet1", ttl=0), nova_l], ignore_index=True))
                            st.success(f"✅ {n_nome} registado!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao gravar: {e}")
                    else:
                        st.warning("Por favor, dê um nome ao alimento.")

        elif alimento_sel:
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento_sel].iloc[0]
            qtd = st.number_input("Quantidade (Coeficiente):", min_value=0.01, value=1.00, step=0.05)
            
            def get_v(names):
                for n in names:
                    if n in row: return float(row[n]) * qtd
                return 0.0

            vals = {"Kcal": get_v(['Calorias', 'Kcal']), "Proteina": get_v(['Proteína', 'Proteina']), "Hidratos": get_v(['Hidratos']), "Lipidos": get_v(['Lípidos', 'Lipidos']), "Acucar": get_v(['(açúcar)', 'Acucar', 'Açúcar']), "Fibras": get_v(['Fibras']), "Sal": get_v(['Sal'])}
            st.info(f"✨ {vals['Kcal']:.1f} kcal | {vals['Proteina']:.1f}g Proteína")

            if st.button("CONFIRMAR E GRAVAR"):
                st.cache_data.clear()
                nova_l = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento_sel, **{k: round(v, 2) for k, v in vals.items()}}])
                conn.update(data=pd.concat([conn.read(worksheet="Sheet1", ttl=0), nova_l], ignore_index=True))
                st.success("Gravado!")
                time.sleep(1)
                st.rerun()

    with col2:
        st.subheader(f"Resumo de {data_sel}")
        df_h = get_data_cached("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            dia_df = df_h[(df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)].copy()
            if not dia_df.empty:
                display_df = dia_df[["Alimento", "Kcal", "Proteina", "Hidratos", "Lipidos", "Acucar", "Fibras", "Sal"]].rename(columns={"Proteina": "Proteína", "Lipidos": "Lípidos", "Acucar": "Açúcar"})
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                m1, m2, m3 = st.columns(3)
                m1.metric("Energia", f"{dia_df['Kcal'].sum():.0f} kcal")
                m2.metric("Proteína", f"{dia_df['Proteina'].sum():.1f}g")
                m3.metric("Açúcar", f"{dia_df['Acucar'].sum():.1f}g")
                if st.button("🗑️ Apagar último"):
                    st.cache_data.clear()
                    conn.update(data=df_h.drop(dia_df.index[-1]))
                    st.rerun()

# --- PÁGINAS ADICIONAIS ---
elif page == "Estatísticas & Médias":
    st.header(f"📊 Análise Global - {user}")
    df_h = get_data_cached("Sheet1")
    if not df_h.empty:
        df_h['Data'] = pd.to_datetime(df_h['Data'], errors='coerce')
        df_u = df_h[df_h['Utilizador'] == user].dropna(subset=['Data'])
        if not df_u.empty:
            diario = df_u.groupby('Data').agg({'Kcal':'sum','Proteina':'sum','Hidratos':'sum','Acucar':'sum','Fibras':'sum'}).sort_index()
            c1, c2, c3 = st.columns(3)
            c1.metric("Média Kcal", f"{diario['Kcal'].mean():.0f}")
            c2.metric("Média Prot.", f"{diario['Proteina'].mean():.1f}g")
            c3.metric("Média Açúcar", f"{diario['Acucar'].mean():.1f}g")
            st.line_chart(diario['Kcal'])

elif page == "Registo de Exercício":
    st.header("🏃 Atividade Física")
    tipo = st.selectbox("Modalidade:", ["Corrida", "Treino de Força", "Remo", "Caminhada", "HIIT"])
    tempo = st.number_input("Duração (min):", min_value=1, value=45)
    if st.button("GRAVAR TREINO"):
        novo_t = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Modalidade": tipo, "Duracao": tempo}])
        conn.update(worksheet="Exercicio", data=pd.concat([get_data_cached("Exercicio"), novo_t], ignore_index=True))
        st.success("Treino guardado!")

elif page == "Câmara IA":
    st.header("📸 Câmara IA")
    foto = st.camera_input("Foto do rótulo")
    if foto:
        img = Image.open(foto)
        with st.spinner("IA a analisar..."):
            prompt = "Extrai valores por 100g: Alimento, Kcal, Proteina, Hidratos, Lipidos, Acucar, Fibras, Sal. Responde apenas em JSON."
            res = model.generate_content([prompt, img])
            try:
                data_ia = json.loads(res.text.replace('```json', '').replace('```', '').strip())
                st.write("Dados extraídos:")
                edited = st.data_editor(pd.DataFrame([data_ia]))
                if st.button("💾 GRAVAR NA BASE"):
                    conn.update(worksheet="Novos_Alimentos", data=pd.concat([get_data_cached("Novos_Alimentos"), edited], ignore_index=True))
                    st.success("Alimento guardado no Back Desk!")
            except: st.error("Erro ao ler rótulo.")
