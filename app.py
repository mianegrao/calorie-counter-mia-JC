import streamlit as st
import pandas as pd

# Configuração da Página
st.set_page_config(page_title="Nutri Control Mia & JC", page_icon="🍎")

st.title("🍎 Nutri Control")

# 1. Carregar os Dados do Excel
@st.cache_data
def load_data():
    try:
        # Lê o ficheiro Excel e a folha correta
        df = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        # Garante que as colunas numéricas não têm erros
        cols_nutri = ['Proteína', 'Hidratos', '(açúcar)', 'Lípidos', 'Fibras', 'Sal', 'Calorias']
        for col in cols_nutri:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Erro ao ler o ficheiro: {e}")
        return pd.DataFrame()

df = load_data()

# 2. Seleção de Utilizador
user = st.sidebar.radio("Utilizador:", ["Mia", "João Carlos"])

if not df.empty:
    tab1, tab2, tab3 = st.tabs(["📝 Registar", "📊 Totais", "⚙️ Base de Dados"])

    with tab1:
        st.header(f"Diário de {user}")
        alimento_nome = st.selectbox("Escolha o Alimento:", df['ALIMENTO'].unique())
        
        row = df[df['ALIMENTO'] == alimento_nome].iloc[0]
        qtd = st.number_input("Quantidade (g ou ml):", min_value=1, value=100)
        fator = qtd / 100
        
        # Cálculos
        cal = row['Calorias'] * fator
        prot = row['Proteína'] * fator
        hid = row['Hidratos'] * fator
        acucar = row['(açúcar)'] * fator
        lip = row['Lípidos'] * fator
        sal = row['Sal'] * fator
        
        st.subheader("Nutrientes nesta porção:")
        c1, c2, c3 = st.columns(3)
        c1.metric("Energia", f"{cal:.1f} kcal")
        c2.metric("Proteína", f"{prot:.1f} g")
        c3.metric("Hidratos", f"{hid:.1f} g")
        
        with st.expander("Ver detalhes"):
            st.write(f"**Açúcar:** {acucar:.1f}g | **Gordura:** {lip:.1f}g | **Sal:** {sal:.2f}g")

        if st.button("Confirmar Registo"):
            st.success(f"Adicionado: {qtd}g de {alimento_nome}")

    with tab3:
        st.header("Lista de Alimentos (Back Desk)")
        st.dataframe(df)
else:
    st.info("A carregar base de dados... Verifica se o ficheiro 'alimentos.xlsx' está no GitHub.")
