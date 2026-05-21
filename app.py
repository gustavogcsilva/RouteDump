import streamlit as st
import pdfplumber
import re
import io
from datetime import datetime
import pytz  # Necessário para garantir o Horário de Brasília

st.set_page_config(page_title="RouteDump", layout="wide")

# 1. AJUSTE DO HORÁRIO PARA BRASÍLIA
with st.sidebar:
    st.header("Sessão Ativa")
    
    # Define o fuso horário de Brasília de forma robusta, independente do servidor
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    agora = datetime.now(fuso_brasilia).strftime("%d/%m/%Y %H:%M:%S")
    
    st.write(f"🕒 **Processamento em:** {agora}")
    st.markdown("---")
    extrair_mapa = st.sidebar.checkbox("Extrair Mapa Geográfico", value=True)

st.title("RouteDump")

uploaded_file = st.file_uploader("Arraste o PDF ou adicione", type="pdf")

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        textos_paginas = []
        for page in pdf.pages:
            texto = page.extract_text()
            if texto:
                # CORREÇÃO DO "MANDARIM" (Remove caracteres não-ASCII bizarros que corrompem o texto)
                texto_limpo = re.sub(r'[^\x00-\x7Fà-úÀ-ÚçÇªº\s\-.,:|/()#]', '', texto)
                textos_paginas.append(texto_limpo)
        
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
                            try:
                                mapa_final = page.within_bbox(bbox).to_image(resolution=300).original
                            except Exception:
                                pass # Previne travamentos se o crop falhar por milímetros

    linhas = full_text.split('\n')
    atendimentos = {}
    atendimento_atual = None
    
    # Expandido e normalizado para cobrir variações de abreviação e capitais
    prefixos = ('Av.', 'Avenida', 'Rua', 'R.', 'Estrada', 'Viaduto', 'Praça', 'Pr.', 'Terminal', 'Term.', 'Shopping', 'V.', 'Pátio', 'Br-', 'Cais', 'Rodovia', 'Rod.')

    # --- NOVA LÓGICA DE FILTRAGEM AGRESSIVA (MOOVIT / LIXO DO PDF) ---
    # Se a linha contiver qualquer um desses termos (ignorando maiúsculas/minúsculas), ela será descartada na hora
    padroes_bloqueados = [
        r"moovit", 
        r"use o", 
        r"na regi", 
        r"baixe o", 
        r"app", 
        r"gratuito", 
        r"paradas\s*:", 
        r"dura\(\c|c\)ao", 
        r"ver os hor", 
        r"confira os", 
        r"informa\(\c|c\)oes da linha", 
        r"tabela de hor", 
        r"visualizar o pdf",
        r"hor\(\a|a\)rios da linha"
    ]

    for l_crua in linhas:
        l = l_crua.strip()
        if not l:
            continue
            
        if "Tabela de horários sentido" in l:
            atendimento_atual = l.replace("Tabela de horários sentido ", "").strip()
            if atendimento_atual not in atendimentos:
                atendimentos[atendimento_atual] = []
            continue
        
        if atendimento_atual:
            # 1. Verifica se a linha contém alguma frase institucional/lixo do Moovit
            contem_lixo = any(re.search(padrao, l, re.IGNORECASE) for padrao in padroes_bloqueados)
            if contem_lixo:
                continue # Pula a linha se for propaganda/metadado
            
            # 2. Mantém a captura flexível se a linha for válida
            is_valid_ponto = l.startswith(prefixos) or '|' in l or (len(l) > 3 and not re.search(r'\d{2}:\d{2}', l) and "Não Utilizar" not in l)
            
            if is_valid_ponto:
                # Limpeza interna fina (caso sobre algum fragmento na mesma linha)
                l_limpa = re.sub(r'Informações da linha.*|Paradas: \d+.*|Duração da viagem.*|VER OS HORÁRIOS.*|Confira os horários.*', '', l, flags=re.IGNORECASE).strip()
                
                # Validação final para garantir que não restaram linhas puramente numéricas ou vazias
                if l_limpa and not re.match(r'^\d+$', l_limpa) and ":" not in l_limpa:
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
        dicionario_individuais = {} # Guarda os textos já processados para os botões individuais

        for nome in selecionados:
            pontos = atendimentos[nome]
            if not pontos: 
                continue

            # --- LÓGICA DE ROTAÇÃO: COLOCAR O TERMINAL NO INÍCIO ---
            idx_inicio = -1
            for i, p in enumerate(pontos):
                if any(term.lower() in p.lower() for term in ["terminal", "ananias", "cais", "term."]):
                    idx_inicio = i
                    break
            
            if idx_inicio != -1:
                pontos = pontos[idx_inicio:] + pontos[:idx_inicio]

            # Remove duplicatas consecutivas de forma segura
            pontos_finais = []
            for p in pontos:
                if not pontos_finais or p != pontos_finais[-1]:
                    pontos_finais.append(p)

            # Montagem do bloco de texto do sentido atual
            txt_sentido = f"--- SENTIDO: {nome.upper()} ---\n"
            txt_sentido += "\n".join(pontos_finais)
            
            # Garante o fechamento do ciclo de retorno ao terminal
            if pontos_finais and not any(term.lower() in pontos_finais[-1].lower() for term in ["terminal", "ananias", "cais", "term."]):
                txt_sentido += f"\n{pontos_finais[0]}"
            
            # Salva para o download individual
            dicionario_individuais[nome] = txt_sentido
            
            # Alimenta o text_area global
            resultado_txt += txt_sentido + "\n\n" + ("="*30) + "\n\n"

        # --- EXIBIÇÃO DO LAYOUT EM DUAS COLUNAS ---
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.text_area("Itinerário ", resultado_txt, height=500)
            
            st.markdown("### 📥 Opções de Download")
            st.download_button(
                label="📄 Baixar Itinerário Completo (TXT)", 
                data=resultado_txt, 
                file_name="itinerario_completo_gcs.txt",
                mime="text/plain"
            )
            
            # Gerador de botões individuais por sentido
            if len(dicionario_individuais) > 1:
                st.markdown("---")
                st.caption("Ou baixe os sentidos individualmente:")
                
                for nome, txt_individual in dicionario_individuais.items():
                    nome_arquivo = re.sub(r'[^a-zA-Z0-9_]', '_', nome.lower())
                    st.download_button(
                        label=f"➔ Baixar Sentido: {nome.upper()}",
                        data=txt_individual,
                        file_name=f"itinerario_{nome_arquivo}.txt",
                        mime="text/plain",
                        key=f"dl_{nome}"
                    )

        with col2:
            if mapa_final:
                st.subheader("Mapeamento Linha Selecionada")
                st.image(mapa_final, use_container_width=True)
                buf = io.BytesIO()
                mapa_final.save(buf, format="PNG")
                st.download_button("Baixar Mapa (PNG)", buf.getvalue(), file_name="mapa_itinerario.png")

# O divisor fica fora das colunas para organizar melhor o rodapé
st.divider()

col_f1, col_f2, col_f3 = st.columns([1, 2, 1])
with col_f2:
    st.markdown("### GCS Core System Intelligence")
    st.write("© 2026 - Todos os direitos reservados")