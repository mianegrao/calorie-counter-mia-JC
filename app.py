import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
from datetime import date
from streamlit_gsheets import GSheetsConnection
import json
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Nutri Control Pro", layout="wide", page_icon="🍎")

# 1. Configurar IA (Gemini)
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

# 2. Conexão Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE SUPORTE ---

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
    """Lê dados do Google Sheets de forma segura."""
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df is None or df.empty:
            return pd.DataFrame()
        return df.dropna(how='all').reset_index(drop=True)
    except:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_combined_food_data():
    """Funde a lista do Excel (GitHub) com a lista de Novos Alimentos (Sheets)."""
    try:
        # Carregar Excel original
        df_excel = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        df_excel.columns = df_excel.columns.str.strip()
        df_excel = df_excel.dropna(subset=['ALIMENTO']).reset_index(drop=True)
    except:
        df_excel = pd.DataFrame()

    # Carregar Novos Alimentos do Google Sheets
    df_sheets = get_data_sheets("Novos_Alimentos")
    
    # Fundir as listas garantindo que não há duplicados de colunas ou de alimentos
    if df_excel.empty and df_sheets.empty:
        return pd.DataFrame(columns=["ALIMENTO", "Proteína", "Hidratos", "(açúcar)", "Lípidos", "(satur.)", "Fibras", "Sal", "Calorias"])
    
    df_combined = pd.concat([df_excel, df_sheets], axis=0, ignore_index=True)
    df_combined = df_combined.loc[:, ~df_combined.columns.duplicated()]
    
    # Manter a versão mais recente se o alimento estiver repetido
    return df_combined.drop_duplicates(subset=['ALIMENTO'], keep='last').sort_values(by='ALIMENTO')

# Carregar base de dados consolidada
df_alimentos = load_combined_food_data()

# --- BARRA LATERAL (NAVEGAÇÃO) ---
st.sidebar.title("🍎 Nutri Control")
user = st.sidebar.selectbox("Utilizador:", ["Mia", "João Carlos", "Jorge", "Celeste"])
data_sel = st.sidebar.date_input("Data de Registo:", date.today())
page = st.sidebar.selectbox("Ir para:", ["Diário / Registo", "Estatísticas", "Exercício", "Câmara IA"])

# --- PÁGINA 1: DIÁRIO / REGISTO ---
if page == "Diário / Registo":
    st.header(f"📝 Diário de {user}")
    
    col1, col2 = st.columns([1, 1.3])
    
    with col1:
        st.subheader("Novo Registo")
        opcoes = df_alimentos['ALIMENTO'].unique() if not df_alimentos.empty else []
        alimento_sel = st.selectbox("Pesquisar Alimento:", options=opcoes, index=None, placeholder="Escreva para procurar...")

        add_novo = st.checkbox("➕ O alimento não existe? Adicionar à base")

        if add_novo:
            st.info("Preencha os dados (por 100g ou dose). Ficará guardado para sempre.")
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
                        with st.spinner("A guardar alimento..."):
                            novo_item = pd.DataFrame([{
                                "ALIMENTO": n_nome, "Proteína": n_prot, "Hidratos": n_hid,
                                "(açúcar)": n_acu, "Lípidos": n_lip, "(satur.)": n_sat,
                                "Fibras": n_fib, "Sal": n_sal, "Calorias": n_kcal
                            }])
                            df_n_atual = get_data_sheets("Novos_Alimentos")
                            df_n_final = pd.concat([df_n_atual, novo_item], ignore_index=True)
                            
                            # Garantir ordem de colunas
                            cols_base = ["ALIMENTO", "Proteína", "Hidratos", "(açúcar)", "Lípidos", "(satur.)", "Fibras", "Sal", "Calorias"]
                            df_n_final = df_n_final[cols_base]
                            
                            safe_update("Novos_Alimentos", df_n_final)
                            st.cache_data.clear()
                            st.success(f"'{n_nome}' adicionado! Já o pode pesquisar.")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao ligar ao Sheets: {e}")
        
        elif alimento_sel:
            row = df_alimentos[df_alimentos['ALIMENTO'] == alimento_sel].iloc[0]
            qtd = st.number_input("Quantidade / Coeficiente (ex: 1.5 para 150g):", min_value=0.01, value=1.00, step=0.05)
            
            # Função para capturar valores independentemente de nomes antigos/novos
            def get_v(names):
                for n in names:
                    if n in row and pd.notnull(row[n]): return float(row[n]) * qtd
                return 0.0

            vals = {
                "Proteína": get_v(['Proteína', 'Proteina']),
                "Hidratos": get_v(['Hidratos']),
                "(açúcar)": get_v(['(açúcar)', 'Acucar']),
                "Lípidos": get_v(['Lípidos', 'Lipidos']),
                "(satur.)": get_v(['(satur.)', 'Saturadas']),
                "Fibras": get_v(['Fibras', 'Fibra']),
                "Sal": get_v(['Sal']),
                "Calorias": get_v(['Calorias', 'Kcal'])
            }
            
            st.info(f"⚡ {vals['Calorias']:.1f} Kcal | 💪 {vals['Proteína']:.1f}g Prot")

            if st.button("✅ CONFIRMAR REGISTO NO DIÁRIO"):
                try:
                    with st.spinner("A registar..."):
                        df_h = get_data_sheets("Sheet1")
                        
                        novo_reg = pd.DataFrame([{
                            "Data": str(data_sel),
                            "Utilizador": user,
                            "Alimento": alimento_sel,
                            "Proteína": round(vals["Proteína"], 2),
                            "Hidratos": round(vals["Hidratos"], 2),
                            "(açúcar)": round(vals["(açúcar)"], 2),
                            "Lípidos": round(vals["Lípidos"], 2),
                            "(satur.)": round(vals["(satur.)"], 2),
                            "Fibras": round(vals["Fibras"], 2),
                            "Sal": round(vals["Sal"], 2),
                            "Calorias": round(vals["Calorias"], 2)
                        }])
                        
                        # Padronização da Sheet1
                        ordem_diario = ["Data", "Utilizador", "Alimento", "Proteína", "Hidratos", "(açúcar)", "Lípidos", "(satur.)", "Fibras", "Sal", "Calorias"]
                        df_final_diario = pd.concat([df_h, novo_reg], ignore_index=True)
                        
                        # Criar colunas que faltem no histórico para evitar erros
                        for c in ordem_diario:
                            if c not in df_final_diario.columns: df_final_diario[c] = 0.0
                        
                        df_final_diario = df_final_diario[ordem_diario]
                        
                        safe_update("Sheet1", df_final_diario)
                        st.cache_data.clear()
                        st.success("Registado!")
                        time.sleep(0.5)
                        st.rerun()
                except Exception as e:
                    st.error(f"Erro ao gravar: {e}")

    with col2:
        st.subheader(f"Resumo do Dia: {data_sel}")
        df_h = get_data_sheets("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            dia_df = df_h[(df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)].copy()
            
            if not dia_df.empty:
                # Garantir colunas para cálculo de totais
                for c in ["Calorias", "Proteína", "(açúcar)", "Fibras"]:
                    if c not in dia_df.columns: dia_df[c] = 0.0

                # Editor para permitir apagar ou ver detalhes
                st.data_editor(
                    dia_df[["Alimento", "Calorias", "Proteína", "(açúcar)", "Fibras"]],
                    hide_index=True,
                    use_container_width=True
                )
                
                st.markdown("---")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🔥 Kcal", f"{dia_df['Calorias'].sum():.0f}")
                m2.metric("🥩 Prot", f"{dia_df['Proteína'].sum():.1f}g")
                m3.metric("🍭 Açúcar", f"{dia_df['(açúcar)'].sum():.1f}g")
                m4.metric("🌾 Fibras", f"{dia_df['Fibras'].sum():.1f}g")
            else:
                st.info("Ainda não existem registos para este dia.")

# --- OUTRAS PÁGINAS ---
elif page == "Estatísticas":
    st.header("📊 Análise de Progresso")
    st.info("Aqui poderá ver as suas médias semanais e gráficos de calorias.")

elif page == "Exercício":
    st.header("🏃 Registo de Atividade Física")
    tipo = st.selectbox("Atividade:", ["Treino Força", "Caminhada", "Corrida", "Natação"])
    tempo = st.number_input("Duração (min):", 15, 300, 45)
    if st.button("Registar Exercício"):
        st.success("Exercício guardado!")

elif page == "Câmara IA":
    st.header("📸 Analisar Rótulo")
    foto = st.camera_input("Tire foto aos valores nutricionais")
    if foto:
        st.warning("IA em processamento... (Requer configuração de Prompt)")
