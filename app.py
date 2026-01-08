with col2:
        st.subheader(f"Resumo de {data_sel}")
        df_h = get_data_cached("Sheet1")
        if not df_h.empty:
            df_h['Data'] = df_h['Data'].astype(str)
            # Filtrar dados do utilizador e dia atual
            dia_df = df_h[(df_h['Data'] == str(data_sel)) & (df_h['Utilizador'] == user)].copy()
            
            if not dia_df.empty:
                # Criar uma coluna de seleção para o data_editor
                dia_df.insert(0, "Selecionar", False)
                
                # Configurar nomes bonitos para exibição
                display_df = dia_df.rename(columns={
                    "Proteina": "Proteína", 
                    "Lipidos": "Lípidos", 
                    "Acucar": "Açúcar"
                })

                # Tabela interativa que permite selecionar linhas
                edited_df = st.data_editor(
                    display_df,
                    hide_index=True,
                    column_config={"Selecionar": st.column_config.CheckboxColumn(required=True)},
                    disabled=["Alimento", "Kcal", "Proteína", "Hidratos", "Lípidos", "Açúcar", "Fibras", "Sal", "Data", "Utilizador"],
                    use_container_width=True
                )

                # Verificar quais foram as linhas selecionadas para apagar
                indices_para_apagar = edited_df[edited_df["Selecionar"] == True].index

                if not indices_para_apagar.empty:
                    if st.button(f"🗑️ Apagar {len(indices_para_apagar)} registo(s)"):
                        try:
                            st.cache_data.clear()
                            # Criar novo DataFrame excluindo as linhas selecionadas
                            df_final = df_h.drop(indices_para_apagar)
                            conn.update(data=df_final)
                            st.success("Registos eliminados!")
                            time.sleep(1)
                            st.rerun()
                        except:
                            st.error("Erro ao comunicar com o Google Sheets.")
                
                # Totais (calculados sobre o dia_df original para não contar a coluna 'Selecionar')
                st.markdown("---")
                c1, c2, c3 = st.columns(3)
                c1.metric("Energia", f"{dia_df['Kcal'].sum():.0f} kcal")
                c2.metric("Proteína", f"{dia_df['Proteina'].sum():.1f}g")
                c3.metric("Açúcar", f"{dia_df['Acucar'].sum():.1f}g")
            else:
                st.write("Sem registos para este dia.")
