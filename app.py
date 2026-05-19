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
# Caixinha segura para a senha no menu lateral:
chave_api = st.sidebar.text_input("🔑 Cole sua API Key aqui:", type="password")
st.sidebar.markdown("[Clique aqui para criar/ver sua API Key grátis](https://aistudio.google.com/)")

st.title("🤖 Extrator Inteligente: Decretos Numerados")

# Avisos visuais da página principal
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
    
    # Trava de segurança: só roda se a chave foi preenchida
    if not chave_api:
        st.error("⚠️ Por favor, cole a sua API Key no menu lateral esquerdo antes de clicar em buscar.")
    else:
        # Configura a IA com a senha colada
        genai.configure(api_key=chave_api)
        # Usamos o modelo 2.0-flash homologado para a sua conta
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
                
                st.info("🧠 A IA começou a ler e estruturar os diários. Isso pode levar alguns minutos...")
                
                for i, diario in enumerate(lista_diarios):
                    data_pub = diario["date"]
                    url_txt = diario["txt_url"]
                    
                    try:
                        # 1. Baixa o texto completo do diário
                        texto_completo = requests.get(url_txt).text
                        
                        # 2. CORTE DINÂMICO: Localiza o bloco exato da seção
                        match_inicio = re.search(r"DECRETOS\s+NUMERADOS", texto_completo, re.IGNORECASE)
                        if not match_inicio:
                            continue # Pula se não houver a seção neste diário
                            
                        inicio_idx = match_inicio.start()
                        
                        # Definição do fim do bloco (adicionado 'CONTRATOS' conforme solicitado)
                        match_fim = re.search(r"\n\s*(?:CONTRATOS|LICITAÇÕES|EDITAIS|CONCURSOS|ATOS DAS SECRETARIAS)\b", texto_completo[inicio_idx:], re.IGNORECASE)
                        
                        if match_fim:
                            texto_secao = texto_completo[inicio_idx : inicio_idx + match_fim.start()]
                        else:
                            # Caso não encontre um limitador claro, extrai até o final por segurança
                            texto_secao = texto_completo[inicio_idx:]
                        
                        # 3. FATIAMENTO INTELIGENTE (CHUNK LOGIC):
                        # Divide o bloco em pedaços de 100 mil caracteres para evitar o erro 429 de cota do Google
                        tamanho_fatia = 100000
                        fatias = [texto_secao[k:k+tamanho_fatia] for k in range(0, len(texto_secao), tamanho_fatia)]
                        
                        conteudo_acumulado_diario = ""
                        
                        # Envia fatia por fatia para a IA
                        for idx, fatia_texto in enumerate(fatias):
                            prompt = f"""
                            Você é um specialist em análise de Diários Oficiais.
                            Abaixo está a PARTE {idx + 1} de um trecho do Diário Oficial de Salvador contendo leis do executivo.
                            
                            Sua tarefa:
                            1. Extraia o conteúdo desta fatia que pertença à seção "DECRETOS NUMERADOS" ou seus anexos.
                            2. Se houver tabelas nesta fatia, reorganize-as perfeitamente em formato Markdown (usando barras |).
                            3. Se houver organogramas, liste as hierarquias de forma lógica usando marcadores (bolinhas).
                            4. Se esta fatia contiver apenas o final de um decreto anterior, assinaturas ou o início de uma tabela, continue a formatação de onde parou.
                            5. Ignore decretos simples ou outras seções alheias.
                            6. Retorne APENAS o conteúdo extraído. Se não houver nada de relevante nesta fatia específica, retorne EXATAMENTE a palavra "NADA".
                            
                            Texto da Parte {idx + 1}:
                            {fatia_texto}
                            """
                            
                            resposta = modelo_ia.generate_content(prompt)
                            resposta_texto = response.text.strip()
                            
                            if resposta_texto != "NADA" and resposta_texto != "":
                                conteudo_acumulado_diario += resposta_texto + "\n\n"
                            
                            # Intervalo de segurança obrigatório para o plano gratuito do Google
                            time.sleep(5)
                        
                        # Se as fatias trouxeram conteúdo válido, consolidamos no relatório
                        if conteudo_acumulado_diario.strip():
                            texto_para_salvar += "🟥"*30 + "\n"
                            texto_para_salvar += f"📅 DATA DA PUBLICAÇÃO: {data_pub}\n"
                            texto_para_salvar += "🟥"*30 + "\n\n"
                            texto_para_salvar += conteudo_acumulado_diario + "\n\n"
                        
                    except Exception as e:
                        # Exibe alertas vermelhos detalhados caso ocorra erro em algum dia específico
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
