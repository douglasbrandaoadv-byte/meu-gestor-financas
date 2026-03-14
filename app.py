import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import date
import plotly.express as px
from ofxparse import OfxParser
import time 
import io

# Configuração da página
st.set_page_config(page_title="Gestor de Finanças", layout="wide")

# Colunas exatas que devem existir na sua planilha
COLUNAS = ["Valor", "Data", "Mês", "Ano", "Fornecedor", "Classificação", "Forma de Pagamento", "Status", "Observação"]

# Conexão com o Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=5)
def carregar_dados():
    try:
        df = conn.read()
        for col in COLUNAS:
            if col not in df.columns:
                df[col] = ""
        df = df.dropna(how="all")
        
        if "Valor" in df.columns:
            df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0.0)
            
        return df
    except Exception as e:
        st.error("Erro ao conectar com a planilha. Verifique os Secrets e o compartilhamento.")
        return pd.DataFrame(columns=COLUNAS)

def salvar_dados(df_novo):
    conn.update(data=df_novo)
    st.cache_data.clear()

# --- Inicialização ---
df_banco = carregar_dados()

if "fornecedores" not in st.session_state:
    st.session_state["fornecedores"] = ["Supermercado A", "Posto B"]
if "classificacoes" not in st.session_state:
    st.session_state["classificacoes"] = ["Alimentação", "Transporte", "Taxas Bancárias", "A SER RESSARCIDO"]

if not df_banco.empty:
    for f in df_banco["Fornecedor"].dropna().unique():
        if str(f).strip() and f not in st.session_state["fornecedores"]:
            st.session_state["fornecedores"].append(f)
    for c in df_banco["Classificação"].dropna().unique():
        if str(c).strip() and c not in st.session_state["classificacoes"]:
            st.session_state["classificacoes"].append(c)

meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
formas_pag = ["PIX", "Cartão de Crédito", "Cartão de Débito", "Boleto", "Débito Automático"]
status_pag = ["A Pagar", "Pago"]

def aplicar_filtros(df, prefixo_chave):
    st.markdown("### 🔍 Filtros")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        f_fornecedor = st.multiselect("Fornecedor", options=st.session_state["fornecedores"], key=f"{prefixo_chave}_forn")
        f_classificacao = st.multiselect("Classificação", options=st.session_state["classificacoes"], key=f"{prefixo_chave}_class")
    with col2:
        f_mes = st.multiselect("Mês de Competência", options=meses, key=f"{prefixo_chave}_mes")
        f_ano = st.number_input("Ano", value=0, step=1, key=f"{prefixo_chave}_ano", help="Deixe 0 para ignorar")
    with col3:
        f_status = st.multiselect("Status", options=status_pag, key=f"{prefixo_chave}_status")
        f_forma = st.multiselect("Forma de Pagamento", options=formas_pag, key=f"{prefixo_chave}_forma")
    with col4:
        f_valor_min = st.number_input("Valor Mínimo", value=0.0, step=10.0, key=f"{prefixo_chave}_vmin")
        f_valor_max = st.number_input("Valor Máximo", value=0.0, step=10.0, key=f"{prefixo_chave}_vmax")

    df_filtrado = df.copy()
    
    if f_fornecedor:
        df_filtrado = df_filtrado[df_filtrado["Fornecedor"].isin(f_fornecedor)]
    if f_classificacao:
        df_filtrado = df_filtrado[df_filtrado["Classificação"].isin(f_classificacao)]
    if f_mes:
        df_filtrado = df_filtrado[df_filtrado["Mês"].isin(f_mes)]
    if f_ano != 0:
        df_filtrado = df_filtrado[df_filtrado["Ano"] == f_ano]
    if f_status:
        df_filtrado = df_filtrado[df_filtrado["Status"].isin(f_status)]
    if f_forma:
        df_filtrado = df_filtrado[df_filtrado["Forma de Pagamento"].isin(f_forma)]
    if f_valor_min > 0:
        df_filtrado = df_filtrado[df_filtrado["Valor"] >= f_valor_min]
    if f_valor_max > 0:
        df_filtrado = df_filtrado[df_filtrado["Valor"] <= f_valor_max]
        
    return df_filtrado

# --- Sistema de Login ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    st.title("Login - Gestor de Finanças")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if usuario == "admin" and senha == "123":
            st.session_state["logado"] = True
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")
else:
    # --- MENU LATERAL ---
    menu = st.sidebar.radio("Navegação", [
        "📝 Lançamentos e Edição", 
        "📊 Relatórios e Dashboards", 
        "🤝 Valores a Receber (Empréstimos)", 
        "🏦 Conciliação Bancária"
    ])
    st.sidebar.markdown("---")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    # ==========================================
    # MÓDULO 1: LANÇAMENTOS E EDIÇÃO
    # ==========================================
    if menu == "📝 Lançamentos e Edição":
        st.title("Gestão de Despesas")
        aba1, aba2, aba3 = st.tabs(["Lançar Unitário", "Lote", "Editar / Excluir"])

        with aba1:
            col1, col2 = st.columns(2)
            with col1:
                fornecedor = st.selectbox("Fornecedor", st.session_state["fornecedores"])
                with st.expander("Cadastrar Novo Fornecedor"):
                    novo_forn = st.text_input("Nome", key="n_forn_1")
                    if st.button("Salvar Fornecedor", key="b_forn_1") and novo_forn:
                        if novo_forn not in st.session_state["fornecedores"]:
                            st.session_state["fornecedores"].append(novo_forn)
                            st.session_state["n_forn_1"] = "" 
                            st.success(f"Fornecedor '{novo_forn}' cadastrado!")
                            time.sleep(2) 
                            st.rerun()

                classificacao = st.selectbox("Classificação", st.session_state["classificacoes"])
                with st.expander("Cadastrar Nova Classificação"):
                    nova_class = st.text_input("Nome", key="n_class_1")
                    if st.button("Salvar Classificação", key="b_class_1") and nova_class:
                        if nova_class not in st.session_state["classificacoes"]:
                            st.session_state["classificacoes"].append(nova_class)
                            st.session_state["n_class_1"] = "" 
                            st.success(f"Classificação '{nova_class}' cadastrada!")
                            time.sleep(2)
                            st.rerun()

                valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01)
                forma = st.selectbox("Forma de Pagamento", formas_pag)

            with col2:
                data_pag = st.date_input("Data do Pagamento")
                mes = st.selectbox("Mês", meses)
                ano = st.number_input("Ano", min_value=2020, value=2026, step=1)
                status = st.selectbox("Status", status_pag)
                obs = st.text_input("Observação")

            if st.button("Salvar Despesa", type="primary"):
                nova_linha = pd.DataFrame([{"Valor": valor, "Data": str(data_pag), "Mês": mes, "Ano": ano, "Fornecedor": fornecedor, "Classificação": classificacao, "Forma de Pagamento": forma, "Status": status, "Observação": obs}])
                salvar_dados(pd.concat([df_banco, nova_linha], ignore_index=True))
                st.success("Despesa salva com sucesso!")
                time.sleep(2) 
                st.rerun()

        with aba2:
            st.markdown("---")
            col_forn_lote, col_class_lote = st.columns(2)
            
            with col_forn_lote:
                with st.expander("➕ Cadastrar Novo Fornecedor"):
                    novo_forn_lote = st.text_input("Nome do Fornecedor", key="input_novo_forn_aba2")
                    if st.button("Salvar Fornecedor", key="btn_salvar_forn_aba2", use_container_width=True):
                        if novo_forn_lote.strip() == "":
                            st.warning("Por favor, digite o nome do fornecedor.")
                        elif novo_forn_lote in st.session_state["fornecedores"]:
                            st.warning("Este fornecedor já está cadastrado.")
                        else:
                            st.session_state["fornecedores"].append(novo_forn_lote)
                            st.session_state["input_novo_forn_aba2"] = "" 
                            st.success(f"Fornecedor '{novo_forn_lote}' cadastrado!")
                            time.sleep(2)
                            st.rerun()

            with col_class_lote:
                with st.expander("➕ Cadastrar Nova Classificação"):
                    nova_class_lote = st.text_input("Nome da Classificação", key="input_nova_class_aba2")
                    if st.button("Salvar Classificação", key="btn_salvar_class_aba2", use_container_width=True):
                        if nova_class_lote.strip() == "":
                            st.warning("Por favor, digite o nome da classificação.")
                        elif nova_class_lote in st.session_state["classificacoes"]:
                            st.warning("Esta classificação já está cadastrada.")
                        else:
                            st.session_state["classificacoes"].append(nova_class_lote)
                            st.session_state["input_nova_class_aba2"] = "" 
                            st.success(f"Classificação '{nova_class_lote}' cadastrada!")
                            time.sleep(2)
                            st.rerun()
            st.markdown("---")

            df_lote = pd.DataFrame(columns=COLUNAS)
            editado_lote = st.data_editor(
                df_lote, num_rows="dynamic", use_container_width=True,
                column_config={
                    "Mês": st.column_config.SelectboxColumn(options=meses),
                    "Fornecedor": st.column_config.SelectboxColumn(options=st.session_state["fornecedores"]),
                    "Classificação": st.column_config.SelectboxColumn(options=st.session_state["classificacoes"]),
                    "Forma de Pagamento": st.column_config.SelectboxColumn(options=formas_pag),
                    "Status": st.column_config.SelectboxColumn(options=status_pag),
                    "Data": st.column_config.DateColumn()
                }
            )
            if st.button("Salvar Lote", type="primary"):
                editado_lote = editado_lote.dropna(subset=["Fornecedor", "Valor"], how="all")
                if not editado_lote.empty:
                    editado_lote["Data"] = editado_lote["Data"].astype(str)
                    salvar_dados(pd.concat([df_banco, editado_lote], ignore_index=True))
                    st.success(f"{len(editado_lote)} despesa(s) salva(s) com sucesso!")
                    time.sleep(2) 
                    st.rerun()
                else:
                    st.warning("A planilha está vazia.")

        with aba3:
            if df_banco.empty:
                st.info("Nenhuma despesa cadastrada.")
            else:
                df_filtrado = aplicar_filtros(df_banco, "edicao")
                st.markdown("---")
                st.write("Edite as células abaixo. Para excluir, selecione a linha na lateral esquerda e aperte a tecla 'Delete'.")
                
                df_editado = st.data_editor(
                    df_filtrado, num_rows="dynamic", use_container_width=True, key="editor_banco",
                    column_config={
                        "Mês": st.column_config.SelectboxColumn(options=meses),
                        "Fornecedor": st.column_config.SelectboxColumn(options=st.session_state["fornecedores"]),
                        "Classificação": st.column_config.SelectboxColumn(options=st.session_state["classificacoes"]),
                        "Forma de Pagamento": st.column_config.SelectboxColumn(options=formas_pag),
                        "Status": st.column_config.SelectboxColumn(options=status_pag)
                    }
                )

                if st.button("Confirmar Alterações", type="primary"):
                    df_final = df_banco.copy()
                    linhas_excluidas = set(df_filtrado.index) - set(df_editado.index)
                    if linhas_excluidas:
                        df_final = df_final.drop(index=linhas_excluidas)
                    
                    df_final.update(df_editado)
                    
                    linhas_novas = set(df_editado.index) - set(df_filtrado.index)
                    if linhas_novas:
                        df_novas = df_editado.loc[list(linhas_novas)]
                        df_final = pd.concat([df_final, df_novas], ignore_index=True)
                    
                    df_final = df_final.reset_index(drop=True)
                    diferenca_tamanho = len(df_banco) - len(df_final)
                    
                    if diferenca_tamanho > 0:
                        df_vazio = pd.DataFrame([{col: "" for col in COLUNAS}] * diferenca_tamanho)
                        df_para_salvar = pd.concat([df_final, df_vazio], ignore_index=True)
                    else:
                        df_para_salvar = df_final.copy()
                        
                    salvar_dados(df_para_salvar)
                    st.success("Exclusão aplicada com sucesso!")
                    time.sleep(2)
                    st.rerun()

    # ==========================================
    # MÓDULO 2: RELATÓRIOS E DASHBOARDS
    # ==========================================
    elif menu == "📊 Relatórios e Dashboards":
        st.title("Painel de Relatórios")
        
        if df_banco.empty:
            st.warning("Não há dados para gerar relatórios.")
        else:
            # 1. Puxa os dados completos com base nos filtros da tela
            df_base = aplicar_filtros(df_banco, "dash")
            
            st.markdown("---")
            
            if df_base.empty:
                st.info("Nenhum dado encontrado para os filtros selecionados.")
            else:
                # 2. Separa os Lançamentos: Despesas Reais vs Empréstimos
                condicao_emprestimo = df_base["Classificação"].astype(str).str.upper().str.strip() == "A SER RESSARCIDO"
                
                df_despesas = df_base[~condicao_emprestimo]
                df_emprestimos = df_base[condicao_emprestimo]
                
                # 3. Cálculos de Despesas
                total_despesas = df_despesas["Valor"].sum()
                total_pagas = df_despesas[df_despesas["Status"] == "Pago"]["Valor"].sum()
                total_aberto = df_despesas[df_despesas["Status"] == "A Pagar"]["Valor"].sum()
                
                # 4. Cálculos de Empréstimos ("A SER RESSARCIDO")
                total_emprestimos_pendentes = df_emprestimos[df_emprestimos["Status"] == "A Pagar"]["Valor"].sum()
                
                # 5. Soma Total (Despesas Reais + Empréstimos a Pagar)
                soma_despesas_emprestimos = total_despesas + total_emprestimos_pendentes
                
                # --- EXIBIÇÃO DOS INDICADORES NA TELA ---
                st.subheader("💰 Resumo Financeiro (Filtrado)")
                
                # Primeira Linha de Indicadores (Métricas de Despesa)
                col1, col2, col3 = st.columns(3)
                col1.metric("Total de Despesas", f"R$ {total_despesas:,.2f}", help="Soma de todas as despesas reais (exclui empréstimos).")
                col2.metric("Despesas Pagas", f"R$ {total_pagas:,.2f}")
                col3.metric("Despesas em Aberto", f"R$ {total_aberto:,.2f}")
                
                # Segunda Linha de Indicadores (Métricas Adicionais)
                c_emp, c_geral = st.columns(2)
                c_emp.metric(
                    "Empréstimos Pendentes (A Receber)", 
                    f"R$ {total_emprestimos_pendentes:,.2f}", 
                    help="Soma dos lançamentos 'A SER RESSARCIDO' que estão com status 'A PAGAR'."
                )
                c_geral.metric(
                    "Soma das Despesas + Empréstimos", 
                    f"R$ {soma_despesas_emprestimos:,.2f}", 
                    help="Total de Despesas somado aos Empréstimos Pendentes (Impacto total de Saídas)."
                )
                
                st.markdown("---")
                
                # --- GRÁFICOS E TABELA ---
                if df_despesas.empty:
                    st.info("Não há despesas reais para exibir gráficos neste período (apenas empréstimos).")
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.subheader("Despesas por Classificação")
                        fig_class = px.pie(df_despesas, values='Valor', names='Classificação', hole=0.4)
                        st.plotly_chart(fig_class, use_container_width=True)
                        
                    with c2:
                        st.subheader("Despesas por Mês")
                        df_mes = df_despesas.groupby('Mês', as_index=False)['Valor'].sum()
                        fig_mes = px.bar(df_mes, x='Mês', y='Valor', text_auto='.2s')
                        st.plotly_chart(fig_mes, use_container_width=True)
                        
                    st.markdown("---")
                    st.subheader("📄 Detalhamento das Despesas")
                    st.write(f"Mostrando {len(df_despesas)} despesa(s) (Lançamentos 'A ser ressarcido' foram ocultados desta tabela para não bagunçar a prestação de contas).")
                    
                    st.dataframe(
                        df_despesas,
                        column_config={
                            "Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                            "ID_Interno": None, 
                            "Usado": None 
                        },
                        use_container_width=True,
                        hide_index=True 
                    )
    # ==========================================
    # MÓDULO 3: VALORES A RECEBER (EMPRÉSTIMOS)
    # ==========================================
    elif menu == "🤝 Valores a Receber (Empréstimos)":
        st.title("Valores a Receber (A Ser Ressarcido)")
        st.write("Acompanhe aqui os valores que foram emprestados ou adiantados e precisam ser cobrados.")

        if df_banco.empty:
            st.info("Nenhum dado cadastrado.")
        else:
            # Filtra APENAS o que for "A SER RESSARCIDO"
            df_emprestimos = df_banco[df_banco["Classificação"].astype(str).str.upper().str.strip() == "A SER RESSARCIDO"].copy()

            if df_emprestimos.empty:
                st.success("🎉 Você não tem nenhum valor pendente para ser ressarcido no momento!")
            else:
                total_receber = df_emprestimos[df_emprestimos["Status"] == "A Pagar"]["Valor"].sum()
                total_recebido = df_emprestimos[df_emprestimos["Status"] == "Pago"]["Valor"].sum()

                col1, col2 = st.columns(2)
                col1.metric("⏳ Total a Receber (Pendente)", f"R$ {total_receber:,.2f}")
                col2.metric("✅ Total já Devolvido (Pago)", f"R$ {total_recebido:,.2f}")

                st.markdown("---")
                
                # Resumo de quem deve
                st.subheader("Resumo por Pessoa / Empresa")
                df_devedores = df_emprestimos[df_emprestimos["Status"] == "A Pagar"].groupby("Fornecedor")["Valor"].sum().reset_index()
                
                if not df_devedores.empty:
                    df_devedores = df_devedores.sort_values(by="Valor", ascending=False)
                    st.dataframe(
                        df_devedores,
                        column_config={
                            "Fornecedor": "Quem está devendo",
                            "Valor": st.column_config.NumberColumn("Valor Total Pendente", format="R$ %.2f")
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("Todos os empréstimos registrados já foram pagos!")

                st.markdown("---")
                st.subheader("Histórico Completo de Empréstimos")
                st.dataframe(
                    df_emprestimos,
                    column_config={
                        "Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                        "ID_Interno": None, 
                        "Usado": None 
                    },
                    use_container_width=True,
                    hide_index=True
                )

    # ==========================================
    # MÓDULO 4: CONCILIAÇÃO BANCÁRIA
    # ==========================================
    elif menu == "🏦 Conciliação Bancária":
        st.title("Conciliação Bancária (Importação OFX)")
        st.write("Importe seu extrato bancário para confrontar os débitos com as despesas do sistema.")
        
        if "conciliados_sessao" not in st.session_state:
            st.session_state["conciliados_sessao"] = []
            
        arquivo_ofx = st.file_uploader("Selecione o arquivo .OFX", type=["ofx"])
        
        if arquivo_ofx is not None:
            try:
                import io 
                
                conteudo = arquivo_ofx.read().decode('latin-1', errors='ignore')
                
                linhas = conteudo.splitlines()
                conteudo_corrigido = []
                contador_id = 1
                
                for linha in linhas:
                    linha_limpa = linha.strip().upper()
                    if linha_limpa == "<FITID>" or linha_limpa == "<FITID></FITID>":
                        linha = f"<FITID>BB_FIX_{contador_id}"
                        contador_id += 1
                    conteudo_corrigido.append(linha)
                
                novo_texto = "\n".join(conteudo_corrigido)
                arquivo_corrigido = io.BytesIO(novo_texto.encode('utf-8'))
                
                ofx = OfxParser.parse(arquivo_corrigido)
                
                if not df_banco.empty:
                    df_banco_match = df_banco[['Data', 'Valor']].copy()
                    
                    def limpar_data(d):
                        try:
                            return pd.to_datetime(d).strftime('%Y-%m-%d')
                        except:
                            return str(d).strip()[:10]
                            
                    df_banco_match['Data'] = df_banco_match['Data'].apply(limpar_data)
                    
                    def limpar_valor(v):
                        try:
                            if isinstance(v, str):
                                v = v.upper().replace('R$', '').strip()
                                if '.' in v and ',' in v:
                                    v = v.replace('.', '').replace(',', '.')
                                elif ',' in v:
                                    v = v.replace(',', '.')
                            return round(float(v), 2)
                        except:
                            return 0.0
                            
                    df_banco_match['Valor'] = df_banco_match['Valor'].apply(limpar_valor)
                    df_banco_match['Usado'] = False 
                else:
                    df_banco_match = pd.DataFrame(columns=['Data', 'Valor', 'Usado'])

                transacoes_pendentes = []
                qtd_total_ofx = 0
                qtd_ja_conciliadas = 0
                
                if isinstance(ofx.account, list):
                    contas = ofx.account
                else:
                    contas = [ofx.account]
                
                for account in contas:
                    for tx in account.statement.transactions:
                        if tx.amount < 0:
                            qtd_total_ofx += 1
                            tx_data = tx.date.strftime("%Y-%m-%d")
                            tx_valor = round(abs(float(tx.amount)), 2)
                            tx_id = tx.id 
                            
                            match_encontrado = False
                            
                            if tx_id in st.session_state["conciliados_sessao"]:
                                match_encontrado = True
                                qtd_ja_conciliadas += 1
                            
                            elif not df_banco_match.empty:
                                matches = df_banco_match[
                                    (df_banco_match['Data'] == tx_data) & 
                                    (abs(df_banco_match['Valor'] - tx_valor) < 0.05) & 
                                    (df_banco_match['Usado'] == False)
                                ]
                                
                                if not matches.empty:
                                    idx = matches.index[0] 
                                    df_banco_match.at[idx, 'Usado'] = True 
                                    match_encontrado = True
                                    qtd_ja_conciliadas += 1
                                    
                            if not match_encontrado:
                                transacoes_pendentes.append({
                                    "ID_Interno": tx_id, 
                                    "Data": tx_data,
                                    "Descrição Banco": tx.payee,
                                    "Valor": tx_valor,
                                    "Fornecedor": None,
                                    "Classificação": None,
                                    "Forma de Pagamento": "Cartão de Débito",
                                    "Status": "Pago", 
                                    "Observação": "Importado via OFX", 
                                    "Mês": meses[tx.date.month - 1],
                                    "Ano": tx.date.year
                                })
                
                # --- AQUI ESTÁ A CORREÇÃO DA INDENTAÇÃO ---
                st.write(
                    f"📊 **Resumo do Extrato:** {qtd_total_ofx} saídas identificadas | "
                    f"✅ {qtd_ja_conciliadas} já constam no sistema | "
                    f"⚠️ **{len(transacoes_pendentes)} aguardando lançamento**"
                )
                
                df_extrato = pd.DataFrame(transacoes_pendentes)
                
                if df_extrato.empty:
                    st.success("🎉 Excelente! Todas as despesas deste extrato já estão devidamente lançadas e conciliadas no seu sistema.")
                else:
                    st.markdown("### Planilha de Lançamentos Pendentes")
                    st.write("Abaixo estão **APENAS as despesas não lançadas**. Preencha o **Fornecedor** e a **Classificação** das que deseja importar agora.")
                    
                    st.markdown("---")
                    col_forn_concil, col_class_concil = st.columns(2)
                    
                    with col_forn_concil:
                        with st.expander("➕ Cadastrar Novo Fornecedor"):
                            novo_forn_concil = st.text_input("Nome do Fornecedor", key="input_novo_forn_concil")
                            if st.button("Salvar Fornecedor", key="btn_salvar_forn_concil", use_container_width=True):
                                if novo_forn_concil.strip() == "":
                                    st.warning("Por favor, digite o nome do fornecedor.")
                                elif novo_forn_concil in st.session_state["fornecedores"]:
                                    st.warning("Este fornecedor já está cadastrado.")
                                else:
                                    st.session_state["fornecedores"].append(novo_forn_concil)
                                    st.session_state["input_novo_forn_concil"] = "" 
                                    st.success(f"Fornecedor '{novo_forn_concil}' cadastrado!")
                                    time.sleep(2)
                                    st.rerun()

                    with col_class_concil:
                        with st.expander("➕ Cadastrar Nova Classificação"):
                            nova_class_concil = st.text_input("Nome da Classificação", key="input_nova_class_concil")
                            if st.button("Salvar Classificação", key="btn_salvar_class_concil", use_container_width=True):
                                if nova_class_concil.strip() == "":
                                    st.warning("Por favor, digite o nome da classificação.")
                                elif nova_class_concil in st.session_state["classificacoes"]:
                                    st.warning("Esta classificação já está cadastrada.")
                                else:
                                    st.session_state["classificacoes"].append(nova_class_concil)
                                    st.session_state["input_nova_class_concil"] = ""
                                    st.success(f"Classificação '{nova_class_concil}' cadastrada!")
                                    time.sleep(2)
                                    st.rerun()
                    st.markdown("---")

                    df_conciliacao = st.data_editor(
                        df_extrato,
                        column_config={
                            "ID_Interno": None,
                            "Fornecedor": st.column_config.SelectboxColumn("Fornecedor", options=st.session_state["fornecedores"]),
                            "Classificação": st.column_config.SelectboxColumn("Classificação", options=st.session_state["classificacoes"]),
                            "Forma de Pagamento": st.column_config.SelectboxColumn("Forma de Pagamento", options=formas_pag, required=True),
                            "Observação": st.column_config.TextColumn("Observação"),
                            "Valor": st.column_config.NumberColumn(format="R$ %.2f")
                        },
                        use_container_width=True,
                        disabled=["Data", "Descrição Banco", "Valor", "Mês", "Ano"]
                    )
                    
                    if st.button("Importar Lançamentos Preenchidos", type="primary"):
                        lancamentos_novos = df_conciliacao[df_conciliacao["Fornecedor"].notna() & df_conciliacao["Classificação"].notna()]
                        
                        if lancamentos_novos.empty:
                            st.warning("Nenhum lançamento válido para importar. Preencha o Fornecedor e a Classificação na tabela.")
                        else:
                            ids_importados = lancamentos_novos["ID_Interno"].tolist()
                            st.session_state["conciliados_sessao"].extend(ids_importados)
                            
                            lancamentos_novos = lancamentos_novos.drop(columns=["Descrição Banco", "ID_Interno"])
                            
                            df_final = pd.concat([df_banco, lancamentos_novos], ignore_index=True)
                            salvar_dados(df_final)
                            
                            st.success(f"{len(lancamentos_novos)} despesas importadas com sucesso! Elas foram retiradas da lista.")
                            time.sleep(2) 
                            st.rerun()
                            
            except Exception as e:
                st.error(f"Erro ao processar o arquivo OFX. Verifique se o formato é válido. Detalhe: {e}")
