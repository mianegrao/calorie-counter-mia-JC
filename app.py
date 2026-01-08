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
@st.cache_data(ttl=600)
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
@st.cache_data(ttl=60)
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
    col1, col2 = st.columns([1, 1.2])
    
    with col1:
        st.subheader("Novo Registo")
        opcoes_alimentos = list(df_alimentos['ALIMENTO'].unique())
        
        alimento_sel = st.selectbox(
            "Pesquisar Alimento:", 
            options=opcoes_alimentos, 
            index=None, 
            placeholder="Escreva para procurar..."
        )

        add_novo = st.checkbox("➕ Não encontrei? Criar novo alimento")

        if add_novo:
            st.markdown("---")
            n_nome = st.text_input("Nome do Alimento:", key="manual_n_nome")
            c1, c2 = st.columns(2)
            n_kcal = c1.number_input("Kcal (100g/dose)", min_value=0.0, step=1.0, key="manual_kcal")
            n_prot = c2.number_input("Proteína (g)", min_value=0.0, step=0.1, key="manual_prot")
            c3, c4 = st.columns(2)
            n_hid = c3.number_input("Hidratos (g)", min_value=0.0, step=0.1, key="manual_hid")
            n_lip = c4.number_input("Lípidos (g)", min_value=0.0, step=0.1, key="manual_lip")
            
            if st.button("💾 GUARDAR E REGISTAR NOVO ALIMENTO"):
                if n_nome:
                    try:
                        with st.spinner("A guardar no Google Sheets..."):
                            # 1. Registar na aba Novos_Alimentos (Base de Dados)
                            item_base = pd.DataFrame([{
                                "Alimento": n_nome, "Kcal": n_kcal, "Proteina": n_prot, 
                                "Hidratos": n_hid, "Lipidos": n_lip, "Acucar": 0.0, "Fibras": 0.0, "Sal": 0.0
                            }])
                            df_n_atual = conn.read(worksheet="Novos_Alimentos", ttl=0)
                            conn.update(worksheet="Novos_Alimentos", data=pd.concat([df_n_atual, item_base], ignore_index=True))
                            
                            # 2. Registar no Diário de hoje (Sheet1)
                            item_diario = pd.DataFrame([{
                                "Data": str(data_sel), "Utilizador": user, "Alimento": n_nome,
                                "Kcal": n_kcal, "Proteina": n_prot, "Hidratos": n_hid, "Lipidos": n_lip,
                                "Acucar": 0.0, "Fibras": 0.0, "Sal": 0.0
                            }])
                            df_s1_atual = conn.read(worksheet="Sheet1", ttl=0)
                            conn.update(worksheet="Sheet1", data=pd.concat([df_s1_atual, item_diario], ignore_index=True))
                            
                            st.cache_data.clear()
                            st.success(f"✅ {n_nome} registado!")
                            time.sleep(1.5)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}. Verifique se a aba 'Novos_Alimentos' existe no Sheets.")
                else:
                    st.warning("Introduza o nome do alimento.")

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
                try:
                    df_atual = conn.read(worksheet="Sheet1", ttl=0)
                    nova_l = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento_sel, **{k: round(v, 2) for k, v in vals.items()}}])
                    conn.update(worksheet="Sheet1", data=pd.concat([df_atual, nova_l], ignore_index=True))
                    st.cache_data.clear()
                    st.success("Registado!")
                    time.sleep(1)
                    st.rerun()
                except:
                    st.error("Erro ao gravar.")

    with col2:
        st.subheader(f"Resumo de {data_sel}")
        df_h = get_data_cached("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            mask = (df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)
            dia_df = df_h[mask].copy()
            
            if not dia_df.empty:
                dia_df.insert(0, "Sel.", False)
                display_df = dia_df.rename(columns={"Proteina": "Proteína", "Lipidos": "Lípidos", "Acucar": "Açúcar"})
                
                edited_df = st.data_editor(
                    display_df[["Sel.", "Alimento", "Kcal", "Proteína", "Hidratos", "Açúcar"]],
                    hide_index=True,
                    column_config={"Sel.": st.column_config.CheckboxColumn(required=True)},
                    use_container_width=True
                )

                selected_indices = edited_df[edited_df["Sel."] == True].index

                if len(selected_indices) > 0:
                    if st.button(f"🗑️ Apagar {len(selected_indices)} itens"):
                        df_final = df_h.drop(selected_indices)
                        conn.update(worksheet="Sheet1", data=df_final)
                        st.cache_data.clear()
                        st.rerun()
                
                st.markdown("---")
                m1, m2, m3 = st.columns(3)
                m1.metric("Kcal", f"{dia_df['Kcal'].sum():.0f}")
                m2.metric("Proteína", f"{dia_df['Proteina'].sum():.1f}g")
                m3.metric("Açúcar", f"{dia_df['Acucar'].sum():.1f}g")
            else:
                st.info("Sem registos hoje.")

# --- OUTRAS PÁGINAS ---
elif page == "Estatísticas & Médias":
    st.header(f"📊 Estatísticas - {user}")
    df_h = get_data_cached("Sheet1")
    if not df_h.empty:
        df_h['Data'] = pd.to_datetime(df_h['Data'], errors='coerce')
        df_u = df_h[df_h['Utilizador'] == user].dropna(subset=['Data'])
        if not df_u.empty:
            diario = df_u.groupby('Data').agg({'Kcal':'sum','Proteina':'sum','Acucar':'sum'}).sort_index()
            st.line_chart(diario['Kcal'])
            st.write(f"Média diária: {diario['Kcal'].mean():.0f} kcal")

elif page == "Registo de Exercício":
    st.header("🏃 Exercício")
    tipo = st.selectbox("Atividade:", ["Treino Força", "Corrida", "Caminhada", "Yoga", "Remo"])
    tempo = st.number_input("Minutos:", min_value=1, value=45)
    if st.button("GRAVAR TREINO"):
        df_ex = get_data_cached("Exercicio")
        novo = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Modalidade": tipo, "Duracao": tempo}])
        conn.update(worksheet="Exercicio", data=pd.concat([df_ex, novo], ignore_index=True))
        st.cache_data.clear()
        st.success("Treino guardado!")

elif page == "Câmara IA":
    st.header("📸 Câmara IA")
    foto = st.camera_input("Rótulo")
    if foto:
        img = Image.open(foto)
        with st.spinner("Analisando..."):
            res = model.generate_content(["Identifica valores por 100g: Alimento, Kcal, Proteina, Hidratos, Lipidos, Acucar, Fibras, Sal. Responde apenas JSON.", img])
            try:
                data_ia = json.loads(res.text.replace('```json', '').replace('```', '').strip())
                st.write("Dados Extraídos:", data_ia)
                if st.button("💾 Guardar no Back Desk"):
                    df_n = get_data_cached("Novos_Alimentos")
                    conn.update(worksheet="Novos_Alimentos", data=pd.concat([df_n, pd.DataFrame([data_ia])], ignore_index=True))
                    st.cache_data.clear()
                    st.success("Guardado!")
            except: st.error("Erro na leitura da imagem.")
