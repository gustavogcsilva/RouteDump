import streamlit as st
import pdfplumber
import re
import io
from datetime import datetime
import pytz

# Configuração da página
st.set_page_config(page_title="RouteDump", layout="wide")

# --- FUNÇÕES DE SUPORTE ---

def obter_horario_brasilia():
    """Retorna o horário atual formatado no fuso de Brasília."""
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    return datetime.now(fuso_brasilia).strftime("%d/%m/%Y %H:%M:%S")

def limpar_texto_pdf(texto):
    """Remove caracteres não-ASCII bizarros que corrompem o texto."""
    if not texto:
        return ""
    return re.sub(r'[^\x00-\x7Fà-úÀ-ÚçÇªº\s\-.,:|/()#]', '', texto)

def extrair_maior_mapa(pdf):
    """Busca e extrai a maior imagem (provavelmente o mapa) dentro do PDF."""
    maior_area = 0
    mapa_final = None
    
    for page in pdf.pages:
        if not page.images:
            continue
        for img_obj in page.images:
            area = (img_obj["x1"] - img_obj["x0"]) * (img_obj["bottom"] - img_obj["top"])
            if area > maior_area:
                maior_area = area
                bbox = (img_obj["x0"], img_obj["top"], img_obj["x1"], img_obj["bottom"])
                try:
                    mapa_final = page.within_bbox(bbox).to_image(resolution=300).original
                except Exception:
                    pass 
    return mapa_final

def processar_itinerarios(full_text):
    """Processa o texto bruto do PDF, remove lixos institucionais agressivamente,
    corrige quebras de linha e limita repetições consecutivas."""
    
    # 1. REMOÇÃO DE LIXO GLOBAL AGRESSIVA
    padroes_limpeza_global = [
        r"(?i)horários em tempo real dos ônibus, trem e metrô, e receber direções passo a passo durante todo o percurso!",
        r"(?i)\d+\s+pontos",
        r"(?i)(segunda|terça|quarta|quinta|sexta|sábado|domingo)-feira\s+\d{2}:\d{2}-\d{2}:\d{2}",
        r"(?i)domingo\s+\d{2}:\d{2}-\d{2}:\d{2}",
        r"(?i)domingo Fora de Operação",
        r"(?i)ver os horários",
        r"(?i)confira os horários",
        r"(?i)visualizar o pdf",
        r"(?i)Resumo da linha:",
        r"(?i)Não Utilizar",
        r"(?i)DA LINHA",
        r"(?i)Informações de ônibus\s+\d+",   # NOVO: Filtra resíduos novos de linhas
        r"(?i)Horários de ônibus\s+\d+",     # NOVO: Filtra resíduos novos de horários
        r"(?i)Sentido:\s*[a-zA-Z0-9\s\/:-]+(?=Avenida|Rua|V\.|Av\.)" 
    ]
    
    texto_tratado = full_text
    for padrao in padroes_limpeza_global:
        texto_tratado = re.sub(padrao, "", texto_tratado)

    linhas_brutas = texto_tratado.split('\n')
    linhas_limpas = []
    
    prefixos = ('Av.', 'Avenida', 'Rua', 'R.', 'Estrada', 'Viaduto', 'Praça', 'Pr.', 'Terminal', 'Term.', 'Shopping', 'V.', 'Pátio', 'Br-', 'Cais', 'Rodovia', 'Rod.', 'Travessa')

    # 2. RECONSTRUÇÃO DE LOGRADOUROS QUEBRADOS
    for l_crua in linhas_brutas:
        l = l_crua.strip()
        if not l or l == ")": 
            continue
            
        if "SENTIDO:" in l or "Tabela de horários sentido" in l:
            linhas_limpas.append(l)
            continue

        if linhas_limpas and not l.startswith(prefixos) and not "SENTIDO:" in linhas_limpas[-1]:
            linhas_limpas[-1] = f"{linhas_limpas[-1]} {l}".strip()
        else:
            linhas_limpas.append(l)

    # 3. SEPARAÇÃO E STRIPPING POR ATENDIMENTO
    atendimentos = {}
    atendimento_atual = None
    
    padroes_bloqueados = [
        r"moovit", r"use o", r"na regi", r"baixe o", r"app", r"gratuito", 
        r"paradas\s*:", r"dura(ç|c)ao", r"informa(ç|c)oes da linha", r"tabela de hor", r"hor(á|a)rios da linha"
    ]

    for l in linhas_limpas:
        if "--- SENTIDO:" in l:
            atendimento_atual = l.replace("--- SENTIDO:", "").replace("---", "").strip()
            if atendimento_atual not in atendimentos:
                atendimentos[atendimento_atual] = []
            continue
        elif "Tabela de horários sentido" in l:
            atendimento_atual = l.replace("Tabela de horários sentido ", "").strip()
            if atendimento_atual not in atendimentos:
                atendimentos[atendimento_atual] = []
            continue
        
        if atendimento_atual:
            if any(re.search(padrao, l, re.IGNORECASE) for padrao in padroes_bloqueados):
                continue
            
            is_valid_ponto = l.startswith(prefixos) or '|' in l or (len(l) > 3 and not re.search(r'\d{2}:\d{2}', l))
            
            if is_valid_ponto:
                l_limpa = re.sub(r'(?i)Informações da linha.*|Paradas: \d+.*|Duração da viagem.*|Central\)', '', l).strip()
                l_limpa = re.sub(r'\s+', ' ', l_limpa) 
                
                if l_limpa and not re.match(r'^\d+$', l_limpa) and l_limpa != "|":
                    atendimentos[atendimento_atual].append(l_limpa)
                    
    # 4. LIMITADOR DE REPETIÇÃO MÁXIMA (ATÉ 3)
    atendimentos_filtrados = {}
    for sentido, pontos in atendimentos.items():
        pontos_filtrados = []
        contador_repeticao = 1
        
        for p in pontos:
            if not pontos_filtrados:
                pontos_filtrados.append(p)
            else:
                if p == pontos_filtrados[-1]:
                    contador_repeticao += 1
                else:
                    contador_repeticao = 1
                
                if contador_repeticao <= 3:
                    pontos_filtrados.append(p)
                    
        atendimentos_filtrados[sentido] = pontos_filtrados

    return atendimentos_filtrados

# --- INTERFACE DO STREAMLIT ---

with st.sidebar:
    st.header("Sessão Ativa")
    st.write(f"🕒 **Processamento em:** {obter_horario_brasilia()}")
    st.markdown("---")
    extrair_mapa = st.sidebar.checkbox("Extrair Mapa Geográfico", value=True)

st.title("RouteDump")
uploaded_file = st.file_uploader("Arraste o PDF ou adicione", type="pdf")

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        textos_paginas = [limpar_texto_pdf(page.extract_text()) for page in pdf.pages]
        full_text = "\n".join(textos_paginas)
        mapa_final = extrair_maior_mapa(pdf) if extrair_mapa else None

    atendimentos = processar_itinerarios(full_text)

    if atendimentos:
        st.subheader("Seleção de Atendimentos")
        opcoes = list(atendimentos.keys())
        
        selecionados = st.multiselect(
            "Selecione os sentidos para visualização/download:", 
            options=opcoes, 
            default=opcoes
        )

        resultado_txt = ""
        dicionario_individuais = {} 

        for nome in selecionados:
            pontos = atendimentos[nome]
            if not pontos: 
                continue

            # ROTAÇÃO: COLOCAR O TERMINAL NO INÍCIO
            idx_inicio = -1
            for i, p in enumerate(pontos):
                if any(term.lower() in p.lower() for term in ["terminal", "ananias", "cais", "term."]):
                    idx_inicio = i
                    break
            
            if idx_inicio != -1:
                pontos = pontos[idx_inicio:] + pontos[:idx_inicio]

            # Reconstrução local do texto deste sentido específico
            txt_sentido = f"--- SENTIDO: {nome.upper()} ---\n"
            txt_sentido += "\n".join(pontos)
            
            if pontos and not any(term.lower() in pontos[-1].lower() for term in ["terminal", "ananias", "cais", "term."]):
                txt_sentido += f"\n{pontos[0]}"
            
            # CORREÇÃO CRÍTICA: O dicionário agora guarda apenas a string individual, sem acumular as outras
            dicionario_individuais[nome] = txt_sentido
            
            # O bloco combinado global continua guardando tudo junto para o botão principal
            resultado_txt += txt_sentido + "\n\n" + ("="*30) + "\n\n"

        # --- EXIBIÇÃO EM DUAS COLUNAS ---
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.text_area("Itinerário Final Limpo", resultado_txt, height=500)
            st.markdown("### 📥 Opções de Download")
            st.download_button(
                label="📄 Baixar Todos os Sentidos Juntos (TXT)", 
                data=resultado_txt, 
                file_name="itinerario_completo_gcs.txt",
                mime="text/plain"
            )
            
            if len(dicionario_individuais) > 0:
                st.markdown("---")
                st.caption("Baixar os sentidos individualmente:")
                
                for nome, txt_individual in dicionario_individuais.items():
                    nome_arquivo = re.sub(r'[^a-zA-Z0-9_]', '_', nome.lower())
                    st.download_button(
                        # Passado explicitamente 'txt_individual' garantindo o download isolado
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

st.divider()

col_f1, col_f2, col_f3 = st.columns([1, 2, 1])
with col_f2:
    st.markdown("### GCS Core System Intelligence")
    st.write("© 2026 - Todos os direitos reservados")