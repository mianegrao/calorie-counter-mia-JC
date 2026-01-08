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
    col1, col2 = st.columns([1, 1.3])
    
    with col1:
        st.subheader("Novo Registo")
        opcoes_alimentos = list(df_alimentos['ALIMENTO'].unique())
        
        alimento_sel = st.selectbox(
            "Pesquisar Alimento:", 
            options=opcoes_alimentos, 
            index=None, 
            placeholder="Escreva para procurar..."
        )

        add_novo = st.checkbox("➕ Não encontrei? Criar novo alimento completo")

        if add_novo:
            st.markdown("---")
            st.info("Insere os valores por 100g/dose e depois indica a quantidade consumida.")
            
            n_nome = st.text_input("Nome do Alimento:", key="manual_n_nome")
            
            c_q1, c_q2 = st.columns([2, 1])
            n_qtd = c_q2.number_input("Quantidade (Qtd):", min_value=0.01, value=1.00, step=0.05, help="Ex: 0.5 para metade, 2 para o dobro")
            
            c1, c2 = st.columns(2)
            n_kcal = c1.number_input("Energia (Kcal por 100g)", min_value=0.0, step=1.0)
            n_prot = c2.number_input("Proteína (g por 100g)", min_value=0.0, step=0.1)
            
            c3, c4 = st.columns(2)
            n_hid = c3.number_input("Hidratos (g por 100g)", min_value=0.0, step=0.1)
            n_acu = c4.number_input("Açúcares (g por 100g)", min_value=0.0, step=0.1)
            
            c5, c6 = st.columns(2)
            n_lip = c5.number_input("Lípidos (g por 100g)", min_value=0.0, step=0.1)
            n_sat = c6.number_input("Saturadas (g por 100g)", min_value=0.0, step=0.1)
            
            if st.button("💾 GUARDAR NA BASE E REGISTAR"):
                if n_nome:
                    try:
                        with st.spinner("A processar..."):
                            # 1. Dados originais (para a base de Novos Alimentos)
                            dados_base = {
                                "Alimento": n_nome, "Kcal": n_kcal, "Proteina": n_prot, "Hidratos": n_hid,
                                "Acucar": n_acu, "Lipidos": n_lip, "Saturadas": n_sat, "Sal": 0.0
                            }
                            df_n_atual = conn.read(worksheet="Novos_Alimentos", ttl=0)
                            conn.update(worksheet="Novos_Alimentos", data=pd.concat([df_n_atual, pd.DataFrame([dados_base])], ignore_index=True))
                            
                            # 2. Dados calculados (para o Diário Sheet1)
                            dados_diario = {
                                "Data": str(data_sel), "Utilizador": user, "Alimento": n_nome,
                                "Kcal": n_kcal * n_qtd, "Proteina": n_prot * n_qtd, "Hidratos": n_hid * n_qtd,
                                "Acucar": n_acu * n_qtd, "Lipidos": n_lip * n_qtd, "Saturadas": n_sat * n_qtd, "Sal": 0.0
                            }
                            df_s1_atual = conn.read(worksheet="Sheet1", ttl=0)
                            conn.update(worksheet="Sheet1", data=pd.concat([df_s1_atual, pd.DataFrame([dados_diario])], ignore_index=True))
                            
                            st.cache_data.clear()
                            st.success(f"✅ Registado: {n_nome} ({n_qtd} doses)")
                            time.sleep(1.5)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")
                else:
                    st.warning("Introduz o nome do alimento.")

        elif alimento_sel:
            # Lógica normal para alimentos que já existem no Excel
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento_sel].iloc[0]
            qtd = st.number_input("Quantidade (Doses/Coeficiente):", min_value=0.01, value=1.00, step=0.05)
            
            def get_v(names):
                for n in names:
                    if n in row: return float(row[n]) * qtd
                return 0.0

            vals = {
                "Kcal": get_v(['Calorias', 'Kcal']),
                "Proteina": get_v(['Proteína', 'Proteina']),
                "Hidratos": get_v(['Hidratos']),
                "Acucar": get_v(['(açúcar)', 'Acucar', 'Açúcar']),
                "Lipidos": get_v(['Lípidos', 'Lipidos']),
                "Saturadas": get_v(['saturadas', 'Saturadas']),
                "Sal": get_v(['Sal'])
            }
            
            st.info(f"✨ {vals['Kcal']:.1f} kcal | {vals['Proteina']:.1f}g Proteína")

            if st.button("CONFIRMAR E GRAVAR"):
                df_atual = conn.read(worksheet="Sheet1", ttl=0)
                nova_l = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento_sel, **{k: round(v, 2) for k, v in vals.items()}}])
                conn.update(worksheet="Sheet1", data=pd.concat([df_atual, nova_l], ignore_index=True))
                st.cache_data.clear()
                st.success("Registado!")
                time.sleep(1)
                st.rerun()

    with col2:
        st.subheader(f"Resumo de {data_sel}")
        df_h = get_data_cached("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            mask = (df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)
            dia_df = df_h[mask].copy()
            
            if not dia_df.empty:
                dia_df.insert(0, "Sel.", False)
                display_cols = ["Sel.", "Alimento", "Kcal", "Proteina", "Hidratos", "Acucar", "Lipidos", "Saturadas"]
                cols_to_show = [c for c in display_cols if c in dia_df.columns]
                
                edited_df = st.data_editor(
                    dia_df[cols_to_show].rename(columns={"Proteina": "Prot", "Lipidos": "Líp", "Acucar": "Açúcar", "Saturadas": "Sat"}),
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
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Kcal", f"{dia_df['Kcal'].sum():.0f}")
                m2.metric("Proteína", f"{dia_df['Proteina'].sum():.1f}g")
                m3.metric("Açúcar", f"{dia_df['Acucar'].sum():.1f}g")
                m4.metric("Sat.", f"{dia_df.get('Saturadas', pd.Series([0])).sum():.1f}g")
