import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import date

# Configuração da página
st.set_page_config(page_title="Gestor de Finanças Pessoais", layout="wide")

# Colunas exatas que devem existir na sua planilha do Google
COLUNAS = ["Valor", "Data", "Mês", "Ano", "Fornecedor", "Classificação", "Forma de Pagamento", "Status", "Observação"]

# Conectar ao Google Sheets usando as credenciais configuradas nos Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

# Função para carregar os dados da nuvem
@st.cache_data(ttl=5) # Atualiza o cache rapidamente
def carregar_dados():
    try:
        df = conn.read()
        # Garante que as colunas existam mesmo se a planilha estiver recém-criada
        for col in COLUNAS:
            if col not in df.columns:
                df[col] = ""
        # Remove linhas 100% vazias que o Google Sheets costuma trazer
        df = df.dropna(how="all")
        return df
    except Exception as e:
        st.error("Erro ao conectar com a planilha. Verifique os Secrets e o compartilhamento da planilha.")
        return pd.DataFrame(columns=COLUNAS)

# Função para enviar os dados para a nuvem
def salvar_dados(df_novo):
    conn.update(data=df_novo)
    st.cache_data.clear() # Limpa a memória para forçar a leitura dos novos dados

# --- Inicialização da Base de Dados ---
df_banco = carregar_dados()

# Variáveis de sessão para manter as listas de seleção dinâmicas
if "fornecedores" not in st.session_state:
    st.session_state["fornecedores"] = ["Supermercado A", "Posto B"]
if "classificacoes" not in st.session_state:
    st.session_state["classificacoes"] = ["Alimentação", "Transporte"]

# Puxa os fornecedores e classificações que já existem lá na planilha do Google
if not df_banco.empty:
    for f in df_banco["Fornecedor"].dropna().unique():
        if str(f).strip() and f not in st.session_state["fornecedores"]:
            st.session_state["fornecedores"].append(f)
    for c in df_banco["Classificação"].dropna().unique():
        if str(c).strip() and c not in st.session_state["classificacoes"]:
            st.session_state["classificacoes"].append(c)

# --- Sistema de Login Simples ---
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
    st.title("Gestor de Finanças Pessoais")
    st.header("Menu: Lançar Despesas")

    # Criando as Abas
    aba1, aba2, aba3 = st.tabs(["Lançar Despesa Unitária", "Despesa em Lote", "Editar ou Excluir Despesa"])

    # Opções padrão
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    formas_pag = ["PIX", "Cartão de Crédito", "Cartão de Débito"]
    status_pag = ["A Pagar", "Pago"]

    # --- ABA 1: Lançamento Unitário ---
    with aba1:
        col1, col2 = st.columns(2)
        
        with col1:
            fornecedor = st.selectbox("Fornecedor", st.session_state["fornecedores"])
            with st.expander("Cadastrar Novo Fornecedor"):
                novo_forn = st.text_input("Nome do novo fornecedor")
                if st.button("Cadastrar Fornecedor") and novo_forn:
                    if novo_forn not in st.session_state["fornecedores"]:
                        st.session_state["fornecedores"].append(novo_forn)
                        st.success(f"'{novo_forn}' disponível para seleção!")
                        st.rerun()

            classificacao = st.selectbox("Classificação da Despesa", st.session_state["classificacoes"])
            with st.expander("Cadastrar Nova Classificação"):
                nova_class = st.text_input("Nome da nova classificação")
                if st.button("Cadastrar Classificação") and nova_class:
                    if nova_class not in st.session_state["classificacoes"]:
                        st.session_state["classificacoes"].append(nova_class)
                        st.success(f"'{nova_class}' disponível para seleção!")
                        st.rerun()

            valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01)
            forma = st.selectbox("Forma de Pagamento", formas_pag)

        with col2:
            data_pag = st.date_input("Data do Pagamento")
            mes = st.selectbox("Mês da Competência", meses)
            ano = st.number_input("Ano da Competência", min_value=2026, value=2026, step=1)
            status = st.selectbox("Status do Pagamento", status_pag)
            obs = st.text_input("Observação")

        if st.button("Salvar Despesa", type="primary"):
            nova_linha = pd.DataFrame([{
                "Valor": valor, "Data": str(data_pag), "Mês": mes, "Ano": ano,
                "Fornecedor": fornecedor, "Classificação": classificacao,
                "Forma de Pagamento": forma, "Status": status, "Observação": obs
            }])
            # Junta os dados antigos com a nova linha
            df_atualizado = pd.concat([df_banco, nova_linha], ignore_index=True)
            salvar_dados(df_atualizado)
            st.success("Despesa salva com sucesso no Google Sheets!")
            st.rerun()

    # --- ABA 2: Despesa em Lote ---
    with aba2:
        st.write("Preencha a planilha abaixo e clique em salvar.")
        
        df_lote = pd.DataFrame(columns=COLUNAS)
        df_lote["Valor"] = pd.to_numeric(df_lote["Valor"])
        df_lote["Ano"] = pd.to_numeric(df_lote["Ano"])
        
        editado_lote = st.data_editor(
            df_lote,
            num_rows="dynamic",
            column_config={
                "Mês": st.column_config.SelectboxColumn(options=meses),
                "Fornecedor": st.column_config.SelectboxColumn(options=st.session_state["fornecedores"]),
                "Classificação": st.column_config.SelectboxColumn(options=st.session_state["classificacoes"]),
                "Forma de Pagamento": st.column_config.SelectboxColumn(options=formas_pag),
                "Status": st.column_config.SelectboxColumn(options=status_pag),
                "Data": st.column_config.DateColumn()
            },
            use_container_width=True
        )

        if st.button("CADASTRAR DESPESAS EM LOTE", type="primary"):
            if not editado_lote.empty:
                editado_lote["Data"] = editado_lote["Data"].astype(str)
                df_atualizado = pd.concat([df_banco, editado_lote], ignore_index=True)
                salvar_dados(df_atualizado)
                st.success(f"{len(editado_lote)} despesas cadastradas no Google Sheets!")
            else:
                st.warning("A planilha está vazia.")

    # --- ABA 3: Editar ou Excluir ---
    with aba3:
        st.write("Edite as células diretamente na tabela abaixo. Para excluir, selecione a linha na lateral esquerda e aperte a tecla 'Delete'.")
        
        if not df_banco.empty:
            df_atualizado = st.data_editor(
                df_banco,
                num_rows="dynamic",
                column_config={
                    "Mês": st.column_config.SelectboxColumn(options=meses),
                    "Fornecedor": st.column_config.SelectboxColumn(options=st.session_state["fornecedores"]),
                    "Classificação": st.column_config.SelectboxColumn(options=st.session_state["classificacoes"]),
                    "Forma de Pagamento": st.column_config.SelectboxColumn(options=formas_pag),
                    "Status": st.column_config.SelectboxColumn(options=status_pag)
                },
                use_container_width=True,
                key="editor_banco"
            )

            if st.button("Confirmar Alterações", type="primary"):
                salvar_dados(df_atualizado)
                st.success("Planilha do Google atualizada com sucesso!")
        else:
            st.info("Nenhuma despesa cadastrada ainda. A planilha está vazia.")
