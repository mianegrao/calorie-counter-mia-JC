import streamlit as st
import pandas as pd

# Configuração da Página para Mobile
st.set_page_config(page_title="Nutri Control Mia & JC", page_icon="🍎")

st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #ff4b4b;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🍎 Nutri Control")

# 1. Carregar os Dados do Excel
@st.cache_data
def load_data():
    try:
        # Lê o ficheiro Excel e a folha específica
        df = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        
        # Limpeza básica: garantir que as colunas numéricas são lidas como números
        cols_nutri = ['Proteína', 'Hidratos', '(açúcar)', 'Lípidos', 'Fibras', 'Sal', 'Calorias']
        for col in cols_nutri:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Erro ao ler o ficheiro: {e}")
        return pd.DataFrame()

df = load_data()

# 2. Seleção de Utilizador na Barra Lateral
st.sidebar.header("Perfil")
user = st.sidebar.radio("Quem está a usar?", ["Mia", "João Carlos"])

if not df.empty:
    tab1, tab2, tab3 = st.tabs(["📝 Registar", "📊 Totais Diários", "📖 Back Desk"])

    with tab1:
        st.subheader(f"Refeição de {user}")
        
        # Procura de alimento
        alimento_nome = st.selectbox("O que comeste?", df['ALIMENTO'].unique())
        
        # Obter dados do alimento selecionado
        row = df[df['ALIMENTO'] == alimento_nome].iloc[0]
        
        qtd = st.number_input("Quantidade (g ou ml):", min_value=1.0, value=100.0, step=10.0)
        
        # Cálculo proporcional (assumindo que os dados no Excel são por 100g/ml)
        fator = qtd / 100
        
        cal = row['Calorias'] * fator
        prot = row['Proteína'] * fator
        hid = row['Hidratos'] * fator
        acucar = row['(açúcar)'] * fator
        lip = row['Lípidos'] * fator
        sal = row['Sal'] * fator

        st.info(f"**Totais desta porção:**\n\n🔥 {cal:.1f} kcal  |  💪 {prot:.1f}g Prot  |  🍞 {hid:.1f}g Hid")
        
        if st.button("Confirmar Registo"):
            st.success(f"Registo de {user} guardado com sucesso!")
            # Futuramente: lógica para salvar em base de dados permanente

    with tab2:
        st.header("Consumo de Hoje")
        st.write("Aqui aparecerá a soma de todos os teus registos do dia.")
        # Placeholder para gráficos

    with tab3:
        st.header("Lista de Alimentos")
        st.dataframe(df[['ALIMENTO', 'Calorias', 'Proteína', 'Lípidos', 'Sal']])

else:
    st.warning("Verifica se o ficheiro 'alimentos.xlsx' está no teu GitHub com este nome exato.")
