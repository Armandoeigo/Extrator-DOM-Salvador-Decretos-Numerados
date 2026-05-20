import streamlit as st
import requests
import google.generativeai as genai
import re
import time
from datetime import datetime, date

# ==========================================
# 1. INTERFACE DO SITE E CONFIGURAÇÃO DA IA
# ==========================================
st.set_page_config(page_title="Extrator DOM com IA", page_icon="🤖")

st.sidebar.title("⚙️ Configurações da IA")
st.sidebar.write("Para ler os arquivos complexos, o robô usa a IA do Google Gemini.")
chave_api = st.sidebar.text_input("🔑 Cole sua API Key aqui:", type="password")
st.sidebar.markdown("[Clique aqui para criar/ver sua API Key grátis](https://aistudio.google.com/)")

st.title("🤖 Extrator Inteligente: Decretos Numerados")

st.write("Selecione o período abaixo para buscar os Decretos Numerados no Diário Oficial de Salvador.")
st.write("**:red[Atenção: Base de dados disponível desde 06/2012]**")
st.write("*(A IA vai ler o Diário Oficial, extrair o bloco e estruturar tabelas e anexos automaticamente).*")

data_minima = date(2012, 6, 1)
data_maxima = date.today()

col1, col2 = st.columns(2)
with col1:
    data_inicio = st.date_input("Data de Início", min_value=data_minima, max_value=data_maxima, format="DD/MM/YYYY")
with col2:
    data_fim = st.date_input("Data Final", min_value=data_minima, max_value=data_maxima, format="DD/MM/YYYY")

# ==========================================
# 2. AÇÃO DO BOTÃO
# ==========================================
if st.button("🚀 Buscar e Extrair com IA"):
    
    if not chave_api:
        st.error("⚠️ Por favor, cole a sua API Key no menu lateral esquerdo antes de clicar em buscar.")
    else:
        genai.configure(api_key=chave_api)
        # O modelo 2.0-flash é o único homologado na sua chave
        modelo_ia = genai.GenerativeModel('gemini-2.0-flash')
        
        str_inicio = data_inicio.strftime("%Y-%m-%d")
        str_fim = data_fim.strftime("%Y-%m-%d")
        
        with st.spinner("Buscando diários no servidor..."):
            url_api = "https://api.queridodiario.ok.org.br/api/gazettes/"
            lista_diarios = []
            offset = 0 
            
            while True:
                parametros = {
                    "territory_ids": "2927408", 
                    "querystring": '"DECRETOS NUMERADOS"',
                    "published_since": str_inicio,
                    "published_until": str_fim,
                    "size": 50,       
                    "offset": offset  
                }
                try:
                    resposta_api = requests.get(url_api, params=parametros)
                    resposta_api.raise_for_status() 
                    dados = resposta_api.json()
                    if "gazettes" in dados and len(dados["gazettes"]) > 0:
                        lista_diarios.extend(dados["gazettes"])
                        offset += 50 
                    else:
                        break 
                except Exception as e:
                    st.error(f"Erro de conexão com o Querido Diário: {e}")
                    break

            if len(lista_diarios) > 0:
                lista_diarios = sorted(lista_diarios, key=lambda x: x["date"])
                
                texto_para_salvar = f"RELATÓRIO DE DECRETOS NUMERADOS (EXTRAÍDO POR IA)\n"
                texto_para_salvar += f"PERÍODO: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}\n"
                texto_para_salvar += "="*60 + "\n\n"

                progresso = st.progress(0)
                total = len(lista_diarios)
                
                st.info("🧠 A IA começou a ler e estruturar os diários...")
                
                for i, diario in enumerate(lista_diarios):
                    data_pub = diario["date"]
                    url_txt = diario["txt_url"]
                    
                    try:
                        # 1. Baixa o texto completo do diário
                        texto_completo = requests.get(url_txt).text
                        
                        # 2. O CORTE CIRÚRGICO: Localiza os Decretos Numerados
                        match_inicio = re.search(r"DECRETOS\s+NUMERADOS", texto_completo, re.IGNORECASE)
                        if not match_inicio:
                            continue 
                            
                        inicio_idx = match_inicio.start()
                        
                        # Recorta uma janela segura de texto a partir dali (evita estourar a cota da API)
                        texto_secao = texto_completo[inicio_idx : inicio_idx + 150000]
                        
                        # 3. Comando enviado para a IA (Uma única requisição leve por diário)
                        prompt = f"""
                        Você é um especialista em análise de Diários Oficiais.
                        Abaixo está um trecho focado do Diário Oficial de Salvador contendo leis do executivo.
                        
                        Sua tarefa:
                        1. Encontre e extraia todo o conteúdo da seção "DECRETOS NUMERADOS" e seus anexos presentes no texto abaixo.
                        2. Pare de extrair assim que notar que o bloco dos decretos e seus anexos acabou (geralmente quando começam seções como CONTRATOS, LICITAÇÕES ou EDITAIS).
                        3. Se houver tabelas, reorganize-as perfeitamente em formato Markdown (usando barras |).
                        4. Se houver organogramas, liste as hierarquias de forma lógica usando marcadores (bolinhas).
                        5. Ignore decretos simples ou seções de outros órgãos.
                        6. Retorne APENAS o conteúdo extraído. Se não houver nada de relevante, retorne EXATAMENTE a palavra "NADA".
                        
                        Texto para análise:
                        {texto_secao}
                        """
                        
                        resposta = modelo_ia.generate_content(prompt)
                        conteudo_inteligente = resposta.text.strip()
                        
                        if conteudo_inteligente != "NADA" and conteudo_inteligente != "":
                            texto_para_salvar += "🟥"*30 + "\n"
                            texto_para_salvar += f"📅 DATA DA PUBLICAÇÃO: {data_pub}\n"
                            texto_para_salvar += "🟥"*30 + "\n\n"
                            texto_para_salvar += conteudo_inteligente + "\n\n\n\n"
                        
                        # Pausa de 6 segundos entre diários para garantir estabilidade na cota por minuto
                        time.sleep(6)
                        
                    except Exception as e:
                        st.error(f"Erro no diário de {data_pub}: {e}")
                    
                    progresso.progress((i + 1) / total)

                st.success(f"✅ Análise concluída pela IA! Diários processados: {total}")
                
                # 4. BOTÃO DE DOWNLOAD
                nome_arquivo = f"Decretos_Numerados_IA_{str_inicio}_a_{str_fim}.txt"
                st.download_button(
                    label="📥 Baixar Relatório Estruturado", 
                    data=texto_para_salvar, 
                    file_name=nome_arquivo,
                    mime="text/plain"
                )

            else:
                st.warning("Nenhum diário encontrado no período.")
