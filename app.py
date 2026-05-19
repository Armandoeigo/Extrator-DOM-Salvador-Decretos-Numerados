import streamlit as st
import requests
import google.generativeai as genai
import time
from datetime import datetime, date

# ==========================================
# 1. INTERFACE DO SITE E CONFIGURAÇÃO DA IA
# ==========================================
st.set_page_config(page_title="Extrator DOM com IA", page_icon="🤖")

st.sidebar.title("⚙️ Configurações da IA")
st.sidebar.write("Para ler os arquivos complexos, o robô usa a IA do Google Gemini.")
# A CAIXINHA SEGURA PARA A SENHA FICA AQUI:
chave_api = st.sidebar.text_input("🔑 Cole sua API Key aqui:", type="password")
st.sidebar.markdown("[Clique aqui para criar/ver sua API Key grátis](https://aistudio.google.com/)")

st.title("🤖 Extrator Inteligente: Decretos Numerados")
st.write("A IA vai ler o Diário Oficial, encontrar os Decretos Numerados e estruturar tabelas e anexos automaticamente.")

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
    
    # Trava de segurança: só roda se a chave foi preenchida
    if not chave_api:
        st.error("⚠️ Por favor, cole a sua API Key no menu lateral esquerdo antes de clicar em buscar.")
    else:
        # Configura a IA com a senha que você colou no site
        genai.configure(api_key=chave_api)
        modelo_ia = genai.GenerativeModel('gemini-1.5-flash')
        
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
                
                # ==========================================
                # 3. A IA ENTRA EM AÇÃO LENDO DIÁRIO POR DIÁRIO
                # ==========================================
                st.info("🧠 A IA começou a ler e estruturar os diários. Isso pode levar alguns minutos...")
                
                for i, diario in enumerate(lista_diarios):
                    data_pub = diario["date"]
                    url_txt = diario["txt_url"]
                    
                    try:
                        # Baixa o texto inteiro e bagunçado
                        texto_completo = requests.get(url_txt).text
                        
                        # O comando mestre que passamos para a IA
                        prompt = f"""
                        Você é um especialista em análise de Diários Oficiais.
                        Abaixo está o texto cru do Diário Oficial do Município de Salvador.
                        
                        Sua tarefa:
                        1. Encontre e extraia EXATAMENTE todo o conteúdo da seção "DECRETOS NUMERADOS".
                        2. Se houver anexos ou tabelas pertencentes a esses decretos, reorganize o texto em formato de tabela Markdown (para ficar legível).
                        3. Se houver texto referente a organogramas no anexo, liste os cargos e hierarquias de forma lógica em texto (listas em marcadores).
                        4. Ignore decretos simples, outras secretarias, ou o resto do diário que não faça parte dos Decretos Numerados.
                        5. Retorne APENAS o conteúdo extraído. Se não achar "DECRETOS NUMERADOS" (ou se a seção estiver vazia), retorne EXATAMENTE a palavra "NADA".
                        
                        Texto do Diário:
                        {texto_completo}
                        """
                        
                        # A IA pensa e responde
                        resposta = modelo_ia.generate_content(prompt)
                        conteudo_inteligente = resposta.text.strip()
                        
                        # Se a IA encontrou a seção, salvamos no arquivo
                        if conteudo_inteligente != "NADA":
                            texto_para_salvar += "🟥"*30 + "\n"
                            texto_para_salvar += f"📅 DATA DA PUBLICAÇÃO: {data_pub}\n"
                            texto_para_salvar += "🟥"*30 + "\n\n"
                            texto_para_salvar += conteudo_inteligente + "\n\n\n\n"
                            
                        # Pequena pausa de segurança para a IA não travar
                        time.sleep(3)
                        
                    except Exception as e:
                        pass # Pula se houver erro pontual em um diário
                    
                    progresso.progress((i + 1) / total)

                st.success(f"✅ Análise concluída pela IA! Diários processados: {total}")
                
                nome_arquivo = f"Decretos_Numerados_IA_{str_inicio}_a_{str_fim}.txt"
                st.download_button("📥 Baixar Relatório Estruturado", data=texto_para_salvar, file_name=nome_arquivo, mime="text/plain")

            else:
                st.warning("Nenhum diário encontrado no período.")
