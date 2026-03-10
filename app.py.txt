import streamlit as st
import pandas as pd
import json
import os
from datetime import date

# Configuração da página
st.set_page_config(page_title="Gestor de Finanças Pessoais", layout="wide")

# Arquivo de banco de dados local (JSON)
DB_FILE = "dados.json"

# Inicializar banco de dados se não existir
if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w") as f:
        json.dump({"fornecedores": ["Supermercado A", "Posto B"], "classificacoes": ["Alimentação", "Transporte"], "despesas": []}, f)

def carregar_dados():
    with open(DB_FILE, "r") as f:
        return json.load(f)

def salvar_dados(dados):
    with open(DB_FILE, "w") as f:
        json.dump(dados, f, indent=4)

db = carregar_dados()

# Sistema de Login Simples
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
            st.error("Usuário ou senha incorretos. (Dica: admin / 123)")
else:
    st.title("Gestor de Finanças Pessoais")
    st.header("Menu: Lançar Despesas")

    # Abas do sistema
    aba1, aba2, aba3 = st.tabs(["Lançar Despesa Unitária", "Despesa em Lote", "Editar ou Excluir Despesa"])

    # Opções padrão
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    formas_pag = ["PIX", "Cartão de Crédito", "Cartão de Débito"]
    status_pag = ["A Pagar", "Pago"]

    # --- ABA 1: UNITÁRIA ---
    with aba1:
        col1, col2 = st.columns(2)
        
        with col1:
            fornecedor = st.selectbox("Fornecedor", db["fornecedores"])
            with st.expander("Cadastrar Novo Fornecedor"):
                novo_forn = st.text_input("Nome do novo fornecedor")
                if st.button("Cadastrar Fornecedor") and novo_forn:
                    if novo_forn not in db["fornecedores"]:
                        db["fornecedores"].append(novo_forn)
                        salvar_dados(db)
                        st.success("Cadastrado!")
                        st.rerun()

            classificacao = st.selectbox("Classificação da Despesa", db["classificacoes"])
            with st.expander("Cadastrar Nova Classificação"):
                nova_class = st.text_input("Nome da nova classificação")
                if st.button("Cadastrar Classificação") and nova_class:
                    if nova_class not in db["classificacoes"]:
                        db["classificacoes"].append(nova_class)
                        salvar_dados(db)
                        st.success("Cadastrado!")
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
            nova_despesa = {
                "Fornecedor": fornecedor, "Classificação": classificacao, "Valor": valor,
                "Forma de Pagamento": forma, "Data": str(data_pag), "Mês": mes,
                "Ano": ano, "Status": status, "Observação": obs
            }
            db["despesas"].append(nova_despesa)
            salvar_dados(db)
            st.success("Despesa salva com sucesso!")

    # --- ABA 2: LOTE ---
    with aba2:
        st.write("Preencha a planilha abaixo e clique em salvar.")
        
        # Criar um dataframe vazio estruturado para edição
        df_lote = pd.DataFrame(columns=["Valor", "Data", "Mês", "Ano", "Fornecedor", "Classificação", "Forma de Pagamento", "Status", "Observação"])
        df_lote["Valor"] = pd.to_numeric(df_lote["Valor"])
        df_lote["Ano"] = pd.to_numeric(df_lote["Ano"])
        
        editado_lote = st.data_editor(
            df_lote,
            num_rows="dynamic",
            column_config={
                "Mês": st.column_config.SelectboxColumn(options=meses),
                "Fornecedor": st.column_config.SelectboxColumn(options=db["fornecedores"]),
                "Classificação": st.column_config.SelectboxColumn(options=db["classificacoes"]),
                "Forma de Pagamento": st.column_config.SelectboxColumn(options=formas_pag),
                "Status": st.column_config.SelectboxColumn(options=status_pag),
                "Data": st.column_config.DateColumn()
            },
            use_container_width=True
        )

        if st.button("CADASTRAR DESPESAS EM LOTE", type="primary"):
            if not editado_lote.empty:
                # Converter datas para string antes de salvar no JSON
                editado_lote["Data"] = editado_lote["Data"].astype(str)
                novas_despesas_lote = editado_lote.to_dict(orient="records")
                db["despesas"].extend(novas_despesas_lote)
                salvar_dados(db)
                st.success(f"{len(novas_despesas_lote)} despesas cadastradas!")
            else:
                st.warning("A planilha está vazia.")

    # --- ABA 3: EDITAR / EXCLUIR ---
    with aba3:
        if len(db["despesas"]) > 0:
            df_editar = pd.DataFrame(db["despesas"])
            
            # O st.data_editor permite editar e excluir linhas diretamente na interface!
            st.write("Edite as células diretamente na tabela abaixo. Para excluir, selecione a linha na lateral esquerda e aperte a tecla 'Delete'.")
            
            df_atualizado = st.data_editor(
                df_editar,
                num_rows="dynamic",
                column_config={
                    "Mês": st.column_config.SelectboxColumn(options=meses),
                    "Fornecedor": st.column_config.SelectboxColumn(options=db["fornecedores"]),
                    "Classificação": st.column_config.SelectboxColumn(options=db["classificacoes"]),
                    "Forma de Pagamento": st.column_config.SelectboxColumn(options=formas_pag),
                    "Status": st.column_config.SelectboxColumn(options=status_pag)
                },
                use_container_width=True,
                key="editor_banco"
            )

            if st.button("Confirmar Alterações", type="primary"):
                db["despesas"] = df_atualizado.to_dict(orient="records")
                salvar_dados(db)
                st.success("Base de dados atualizada com sucesso!")
        else:
            st.info("Nenhuma despesa cadastrada ainda.")