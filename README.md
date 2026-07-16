# RouteDump 🚌📄➡️🔤

O **RouteDump** é uma ferramenta desenvolvida em **Python** e **Streamlit** criada para simplificar e automatizar o processo de extração, tratamento e portabilidade de dados de rotas de transporte público obtidos a partir da plataforma Moovit. 

A aplicação realiza o upload de documentos PDF contendo trajetos e horários de linhas de ônibus, executa um parsing inteligente sobre a estrutura desses arquivos e gera um dump bruto em formato de texto estruturado (TXT) para facilitar a integração, manipulação e exportação direta para outros sistemas de logística ou transporte privado.

---

## 🚀 Funcionalidades

* **Processamento Direto:** Upload simples de arquivos de rota em formato PDF (baixados diretamente do Moovit).
* **Conversor Inteligente (Parsing):** Extração de dados textuais e tabelas de horários, eliminando a necessidade de redigitação manual.
* **Exportação Automatizada:** Download imediato das rotas mapeadas em formato bruto de texto (`.txt`).
* **Interface Amigável:** Painel interativo e limpo construído com Streamlit.
* **Agilidade Logística:** Redução de tempo na transposição de itinerários públicos para controle de frotas privadas e planejamento de trajetos corporativos.

---

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** [Python](https://www.python.org/) (Versão 3.10 ou superior)
* **Frontend/Interface:** [Streamlit](https://streamlit.io/) (Visualização dinâmica e interativa)
* **Parser de Documentos:** Bibliotecas especializadas de extração de PDF em Python (ex: `PyPDF2`, `pdfplumber` ou `pypdf`)

---

## 📦 Como Executar o Projeto Localmente

### 1. Pré-requisitos
Certifique-se de ter o Python instalado em sua máquina. Você pode validar usando:
```bash
python --version
