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

# --- FUNÇÕES DE SUPORTE E RETRY ---

def safe_update(worksheet, data, max_retries=3):
    """Tenta atualizar o Sheets com sistema de repetição em caso de erro."""
    for i in range(max_retries):
        try:
            conn.update(worksheet=worksheet, data=data)
            return True
        except Exception as e:
            if i < max_retries - 1:
                time.sleep(2)
                continue
            else:
                raise e
    return False

@st.cache_data(ttl=60)
def get_data_sheets(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df is None or df.empty:
            return pd.DataFrame()
        return df.dropna(how='all')
    except:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_combined_food_data():
    try:
        # 1. Carregar Excel (GitHub)
        df_excel = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        df_excel.columns = df_excel.columns.str.strip()
        df_excel = df_excel.dropna(subset=['ALIMENTO']).reset_index(drop=True)
    except:
        df_excel = pd.DataFrame()

    # 2. Carregar Google Sheets (Novos_Alimentos)
    df_sheets = get_data_sheets("Novos_Alimentos")
    if not df_sheets.empty:
        df_sheets.columns = df_sheets.columns.str.strip()
        df_sheets = df_sheets.reset_index(drop=True)
    
    # 3. Fundir com segurança
    if df_excel.empty and df_sheets.empty:
        return pd.DataFrame(columns=["ALIMENTO", "Proteína", "Hidratos", "(açúcar)", "Lípidos", "(satur.)", "Fibras", "Sal", "Calorias"])
    
    df_combined = pd.concat([df_excel, df_sheets], axis=0, ignore_index=True)
    df_combined = df_combined.loc[:, ~df_combined.columns.duplicated()]
    df_combined = df_combined.drop_duplicates(subset=['ALIMENTO'], keep='last')
    
    return df_combined.sort_values(by='ALIMENTO')

# Carregar lista consolidada
df_alimentos = load_combined_food_data()

# --- NAVEGAÇÃO ---
if "page" not in st.session_state:
    st.session_state.page = "Página Inicial / Registo"

user = st.sidebar.selectbox("Utilizador:", ["Mia", "João Carlos", "Jorge", "Celeste"])
data_sel = st.sidebar.date_input("Data:", date.today())
page = st.sidebar.selectbox("Ir para:", ["Página Inicial / Registo", "Estatísticas & Médias", "Registo de Exercício", "Câmara IA"])

# --- PÁGINA 1: REGISTO ---
if page == "Página Inicial / Registo":
    st.header(f"📝 Diário de {user}")
    col1, col2 = st.columns([1, 1.3])
    
    with col1:
        st.subheader("Novo Registo")
        opcoes = df_alimentos['ALIMENTO'].unique() if not df_alimentos.empty else []
        alimento_sel = st.selectbox("Pesquisar Alimento:", options=opcoes, index=None, placeholder="Procurar...")

        add_novo = st.checkbox("➕ Não existe? Adicionar à base permanentemente")

        if add_novo:
            st.markdown("---")
            st.info("Layout: ALIMENTO | Prot | Hid | Açúcar | Líp | Sat | Fib | Sal | Kcal")
            n_nome = st.text_input("Nome do Alimento (ALIMENTO):")
            
            c1, c2 = st.columns(2)
            n_prot = c1.number_input("Proteína (g)", min_value=0.0, step=0.1)
            n_hid = c2.number_input("Hidratos (g)", min_value=0.0, step=0.1)
            
            c3, c4 = st.columns(2)
            n_acu = c3.number_input("(açúcar) (g)", min_value=0.0, step=0.1)
            n_lip = c4.number_input("Lípidos (g)", min_value=0.0, step=0.1)
            
            c5, c6 = st.columns(2)
            n_sat = c5.number_input("(satur.) (g)", min_value=0.0, step=0.1)
            n_fib = c6.number_input("Fibras (g)", min_value=0.0, step=0.1)
            
            c7, c8 = st.columns(2)
            n_sal = c7.number_input("Sal (g)", min_value=0.0, step=0.01)
            n_kcal = c8.number_input("Calorias (Kcal)", min_value=0.0, step=1.0)
            
            if st.button("💾 GUARDAR NA BASE PERMANENTE"):
                if n_nome:
                    try:
                        with st.spinner("A guardar..."):
                            novo_item = pd.DataFrame([{
                                "ALIMENTO": n_nome, "Proteína": n_prot, "Hidratos": n_hid,
                                "(açúcar)": n_acu, "Lípidos": n_lip, "(satur.)": n_sat,
                                "Fibras": n_fib, "Sal": n_sal, "Calorias": n_kcal
                            }])
                            
                            df_n_atual = get_data_sheets("Novos_Alimentos")
                            df_n_final = pd.concat([df_n_atual, novo_item], ignore_index=True)
                            
                            cols = ["ALIMENTO", "Proteína", "Hidratos", "(açúcar)", "Lípidos", "(satur.)", "Fibras", "Sal", "Calorias"]
                            df_n_final = df_n_final[cols]
                            
                            safe_update("Novos_Alimentos", df_n_final)
                            st.cache_data.clear()
                            st.success("Guardado!")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Erro no Sheets: {e}")
        
        elif alimento_sel:
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento_sel].iloc[0]
            qtd = st.number_input("Quantidade / Coeficiente:", min_value=0.01, value=1.00, step=0.05)
            
            def get_v(names):
                for n in names:
                    if n in row and pd.notnull(row[n]): return float(row[n]) * qtd
                return 0.0

            vals = {
                "Calorias": get_v(['Calorias', 'Kcal']),
                "Proteína": get_v(['Proteína', 'Proteina']),
                "Hidratos": get_v(['Hidratos']),
                "(açúcar)": get_v(['(açúcar)', 'Acucar', 'Açúcar']),
                "Lípidos": get_v(['Lípidos', 'Lipidos']),
                "(satur.)": get_v(['(satur.)', 'saturadas', 'Saturadas']),
                "Fibras": get_v(['Fibras', 'Fibra']),
                "Sal": get_v(['Sal'])
            }
            
            st.info(f"✨ {vals['Calorias']:.1f} kcal | {vals['Proteína']:.1f}g Prot")

            if st.button("CONFIRMAR REGISTO NO DIÁRIO"):
                try:
                    with st.spinner("A registar..."):
                        df_atual = get_data_sheets("Sheet1")
                        nova_l = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Alimento": alimento_sel, **{k: round(v, 2) for k, v in vals.items()}}])
                        safe_update("Sheet1", pd.concat([df_atual, nova_l], ignore_index=True))
                        st.cache_data.clear()
                        st.success("Registado!")
                        time.sleep(1)
                        st.rerun()
                except Exception as e:
                    st.error(f"Erro ao gravar: {e}")

    with col2:
        st.subheader(f"Resumo de {data_sel}")
        df_h = get_data_sheets("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            mask = (df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)
            dia_df = df_h[mask].copy()
            
            if not dia_df.empty:
                dia_df.insert(0, "Sel.", False)
                display_cols = ["Sel.", "Alimento", "Calorias", "Proteína", "(açúcar)", "Fibras"]
                cols_to_show = [c for c in display_cols if c in dia_df.columns]
                
                st.data_editor(dia_df[cols_to_show], hide_index=True, use_container_width=True)
                
                st.markdown("---")
                m1, m2, m3 = st.columns(3)
                m1.metric("Kcal Total", f"{dia_df['Calorias'].sum():.0f}")
                m2.metric("Proteína Total", f"{dia_df['Proteína'].sum():.1f}g")
                m3.metric("Fibras Totais", f"{dia_df.get('Fibras', pd.Series([0])).sum():.1f}g")
            else:
                st.info("Sem registos para este dia.")

# --- OUTRAS PÁGINAS (ESTATÍSTICAS, EXERCÍCIO, CÂMARA IA) ---
elif page == "Estatísticas & Médias":
    st.header(f"📊 Estatísticas - {user}")
    df_h = get_data_sheets("Sheet1")
    if not df_h.empty:
        df_h['Data'] = pd.to_datetime(df_h['Data'], errors='coerce')
        df_u = df_h[df_h['Utilizador'] == user].dropna(subset=['Data'])
        if not df_u.empty:
            diario = df_u.groupby('Data').agg({'Calorias':'sum','Proteína':'sum','(açúcar)':'sum'}).sort_index()
            st.line_chart(diario['Calorias'])
            st.write(f"Média diária: {diario['Calorias'].mean():.0f} kcal")

elif page == "Registo de Exercício":
    st.header("🏃 Registo de Atividade")
    tipo = st.selectbox("Atividade:", ["Treino Força", "Corrida", "Caminhada", "Yoga", "Ciclismo"])
    tempo = st.number_input("Duração (minutos):", min_value=1, value=45)
    if st.button("GRAVAR EXERCÍCIO"):
        try:
            df_ex = get_data_sheets("Exercicio")
            novo_ex = pd.DataFrame([{"Data": str(data_sel), "Utilizador": user, "Modalidade": tipo, "Duracao": tempo}])
            safe_update("Exercicio", pd.concat([df_ex, novo_ex], ignore_index=True))
            st.success("Exercício registado!")
        except Exception as e:
            st.error(f"Erro ao gravar exercício: {e}")

elif page == "Câmara IA":
    st.header("📸 Analisar Rótulo com IA")
    foto = st.camera_input("Tire uma foto do rótulo nutricional")
    if foto:
        img = Image.open(foto)
        with st.spinner("A ler dados nutricionais..."):
            prompt = "Identifica os valores por 100g para: ALIMENTO, Proteína, Hidratos, (açúcar), Lípidos, (satur.), Fibras, Sal, Calorias. Responde apenas em formato JSON."
            res = model.generate_content([prompt, img])
            try:
                # Limpeza básica do texto para garantir JSON puro
                json_text = res.text.replace('```json', '').replace('```', '').strip()
                data_ia = json.loads(json_text)
                st.json(data_ia)
                if st.button("💾 Guardar na Base Permanente"):
                    df_n = get_data_sheets("Novos_Alimentos")
                    safe_update("Novos_Alimentos", pd.concat([df_n, pd.DataFrame([data_ia])], ignore_index=True))
                    st.cache_data.clear()
                    st.success("Dados da IA guardados!")
            except:
                st.error("Não foi possível processar a imagem. Tente uma foto mais nítida.")
