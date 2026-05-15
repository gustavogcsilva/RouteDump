import streamlit as st
import pdfplumber
import re
import io
from datetime import datetime

st.set_page_config(page_title="GCS Intelligence - Gestor de Itinerários", layout="wide")

# 1. DATA E HORA NA INTERFACE
with st.sidebar:
    st.header("Sessão Ativa")
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    st.write(f"🕒 **Processamento em:** {agora}")
    st.markdown("---")
    extrair_mapa = st.sidebar.checkbox("Extrair Mapa Geográfico", value=True)

st.title(" RouteDump ")


uploaded_file = st.file_uploader("Arraste o PDF ou adicione", type="pdf")

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        textos_paginas = [page.extract_text() for page in pdf.pages]
        full_text = "\n".join(textos_paginas)
        
        mapa_final = None
        if extrair_mapa:
            maior_area = 0
            for page in pdf.pages:
                if page.images:
                    for img_obj in page.images:
                        area = (img_obj["x1"] - img_obj["x0"]) * (img_obj["bottom"] - img_obj["top"])
                        if area > maior_area:
                            maior_area = area
                            bbox = (img_obj["x0"], img_obj["top"], img_obj["x1"], img_obj["bottom"])
                            mapa_final = page.within_bbox(bbox).to_image(resolution=300).original

    linhas = full_text.split('\n')
    atendimentos = {}
    atendimento_atual = None
    prefixos = ('Av.', 'Avenida', 'Rua', 'R.', 'Estrada', 'Viaduto', 'Praça', 'Terminal', 'Shopping', 'V.', 'Pátio', 'Br-', 'Cais')

    for linha in linhas:
        l = linha.strip()
        if "Tabela de horários sentido" in l:
            atendimento_atual = l.replace("Tabela de horários sentido ", "").strip()
            if atendimento_atual not in atendimentos:
                atendimentos[atendimento_atual] = []
            continue
        
        if atendimento_atual and (l.startswith(prefixos) or '|' in l):
            if not re.search(r'\d{2}:\d{2}', l) and "Não Utilizar" not in l:
                l_limpa = re.sub(r'Informações da linha.*|Paradas: \d+.*|Duração da viagem.*|VER OS HORÁRIOS.*', '', l).strip()
                if l_limpa:
                    atendimentos[atendimento_atual].append(l_limpa)

    if atendimentos:
        st.subheader("Seleção de Atendimentos")
        opcoes = list(atendimentos.keys())
        selecionados = st.multiselect(
            "Selecione a ordem dos sentidos:", 
            options=opcoes, 
            default=opcoes[:2] if len(opcoes) >= 2 else opcoes
        )

        resultado_txt = ""

        for nome in selecionados:
            pontos = atendimentos[nome]
            if not pontos: continue

            # --- NOVA LÓGICA DE ROTAÇÃO: COLOCAR O TERMINAL NO INÍCIO ---
            # Identifica o índice onde a palavra 'Terminal' ou o ponto de controle aparece pela primeira vez
            idx_inicio = -1
            for i, p in enumerate(pontos):
                if any(term in p for term in ["Terminal", "Ananias", "Cais"]):
                    idx_inicio = i
                    break
            
            # Se achou o terminal no meio da lista, rotaciona a lista
            if idx_inicio != -1:
                # O que estava do terminal pra frente vira o começo + o que estava antes vira o final
                pontos = pontos[idx_inicio:] + pontos[:idx_inicio]

            # Remove duplicatas consecutivas
            pontos_finais = []
            for p in pontos:
                if not pontos_finais or p != pontos_finais[-1]:
                    pontos_finais.append(p)

            # Montagem do bloco
            resultado_txt += f"--- SENTIDO: {nome.upper()} ---\n"
            resultado_txt += "\n".join(pontos_finais)
            
            # Garante que termine no terminal para fechar o ciclo
            if not any(term in pontos_finais[-1] for term in ["Terminal", "Ananias", "Cais"]):
                resultado_txt += f"\n{pontos_finais[0]}"
            
            resultado_txt += "\n\n" + ("="*30) + "\n\n"

        col1, col2 = st.columns([1, 1])
        with col1:
            st.text_area("Itinerário Corrigido (Início no Terminal)", resultado_txt, height=500)
            st.download_button("Baixar Itinerário (TXT)", resultado_txt, file_name="itinerario_corrigido_gcs.txt")

        with col2:
            if mapa_final:
                st.subheader("Mapeamento Linha Selecionada")
                st.image(mapa_final, use_container_width=True)
                buf = io.BytesIO()
                mapa_final.save(buf, format="PNG")
                st.download_button("Baixar Mapa (PNG)", buf.getvalue(), file_name="mapa_itinerario.png")


st.divider() # Linha horizontal nativa

# Usando colunas para centralizar o conteúdo
col_f1, col_f2, col_f3 = st.columns([1, 2, 1])

with col_f2:

    st.markdown("### GCS Core System Intelligence")

    st.write("© 2026 - Todos os direitos reservados")