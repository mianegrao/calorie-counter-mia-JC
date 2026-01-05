import streamlit as st
import pandas as pd

st.set_page_config(page_title="Nutri Control Mia & JC", page_icon="🍎")

st.title("🍎 Nutri Control")

@st.cache_data
def load_data():
    try:
        # Lendo o ficheiro Excel diretamente
        df = pd.read_excel("alimentos.xlsx", sheet_name="Valor nutricional")
        return df
    except Exception as e:
        st.error(f"Erro ao ler alimentos.xlsx: {e}")
        return pd.DataFrame()

df = load_data()

user = st.sidebar.radio("Utilizador:", ["Mia", "João Carlos"])

if not df.empty:
    tab1, tab2, tab3 = st.tabs(["📝 Registar", "📊 Totais", "⚙️ Base de Dados"])

    with tab1:
        st.header(f"Diário de {user}")
        alimento_nome = st.selectbox("Escolha o Alimento:", df['ALIMENTO'].unique())
        
        # Dados do alimento
        row = df[df['ALIMENTO'] == alimento_nome].iloc[0]
        
        qtd = st.number_input("Quantidade (g ou ml):", min_value=1, value=100)
        fator = qtd / 100
        
        # Cálculos com base nas tuas colunas exatas
        cal = row['Calorias'] * fator
        prot = row['Proteína'] * fator
        hid = row['Hidratos'] * fator
        acucar = row['(açúcar)'] * fator
        lip = row['Lípidos'] * fator
        fib = row['Fibras'] * fator
        sal = row['Sal'] * fator
        
        st.subheader("Valores para esta porção:")
        c1, c2, c3 = st.columns(3)
        c1.metric("Energia", f"{cal:.1f} kcal")
        c2.metric("Proteína", f"{prot:.1f} g")
        c3.metric("Hidratos", f"{hid:.1f} g")
        
        with st.expander("Ver detalhes completos"):
            st.write(f"**Açúcar:** {acucar:.1f}g | **Lípidos:** {lip:.1f}g | **Fibras:** {fib:.1f}g | **Sal:** {sal:.2f}g")

        if st.button("Registar"):
            st.success("Adicionado com sucesso!")

    with tab3:
        st.header("Teu 'Back Desk' de Alimentos")
        st.dataframe(df)