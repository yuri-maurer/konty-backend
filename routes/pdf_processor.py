# routes/pdf_processor.py
import io
import re
import zipfile
import logging
from datetime import datetime

import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from unidecode import unidecode

# Configuração básica de logging para depuração no servidor
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

router = APIRouter()

# --- Funções de Extração e Limpeza: REPLICADAS do script backend_unificado.py ---

def extrair_competencia(text):
    """
    Extrai a competência do texto. Lógica idêntica ao script local.
    """
    # Regex para MM.AAAA ou MM/AAAA
    match = re.search(r'\b(0[1-9]|1[0-2])[./](20\d{2})\b', text)
    if match:
        # Retorna no formato padronizado MM.AAAA
        return f"{match.group(1)}.{match.group(2)}"

    # Regex para "Mês de AAAA"
    match = re.search(r'(?:(Jan|Fev|Mar|Abr|Mai|Jun|Jul|Ago|Set|Out|Nov|Dez)[a-z]*)\s+de\s+(\d{4})', text, re.IGNORECASE)
    if match:
        meses_map = {
            'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04', 'mai': '05',
            'jun': '06', 'jul': '07', 'ago': '08', 'set': '09', 'out': '10',
            'nov': '11', 'dez': '12'
        }
        mes_nome = match.group(1).lower()
        mes_num = meses_map.get(mes_nome, 'XX')
        ano = match.group(2)
        return f"{mes_num}.{ano}"
        
    return "DataDesconhecida"

def clean_condominio_name(name):
    """
    Limpa o nome do condomínio. Lógica idêntica ao script local.
    """
    if not name:
        return "CondominioDesconhecido"

    # Remove termos irrelevantes, CNPJ, etc.
    name = re.sub(r'folha mensal|recibo de pagamento', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'CNPJ:\s*.*', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'\s+', ' ', name).strip()
    return unidecode(name).upper()

def find_condominio_name(text):
    """
    Encontra o nome do condomínio de forma robusta. Lógica adaptada do script local.
    """
    # Tenta encontrar o nome do Condomínio antes do CNPJ
    match_condominio = re.search(r'^(.*?)\s*(?:CNPJ:|CC:)', text, re.MULTILINE | re.IGNORECASE)
    if match_condominio:
        condominio_bruto = match_condominio.group(1).strip()
        if condominio_bruto:
            return clean_condominio_name(condominio_bruto)
    
    # Fallback: Se não encontrar CNPJ, procura por linhas com "CONDOMINIO"
    lines = text.split('\n')
    for line in lines:
        if "CONDOMINIO" in unidecode(line).upper():
            cleaned_name = clean_condominio_name(line)
            # Evita pegar apenas a palavra "CONDOMINIO"
            if cleaned_name and len(cleaned_name) > 12:
                return cleaned_name

    # Fallback final: Pega a primeira linha não vazia
    for line in lines:
        if line.strip():
            return clean_condominio_name(line.strip())
            
    return "CondominioDesconhecido"


@router.post("/processar-pdf", tags=["Módulos"])
async def processar_pdf(pdf_file: UploadFile = File(...)):
    if pdf_file.content_type != 'application/pdf':
        raise HTTPException(status_code=400, detail="Formato de ficheiro inválido. Apenas PDFs são aceites.")

    try:
        pdf_bytes = await pdf_file.read()
        pdf_stream = io.BytesIO(pdf_bytes)
        
        reader = PdfReader(pdf_stream)
        plumber_pdf = pdfplumber.open(pdf_stream)
        
        # Dicionário para agrupar páginas E armazenar a competência de cada grupo
        condominios_agrupados = {}
        competencia_geral = "DataDesconhecida"

        # --- Lógica de Agrupamento (Idêntica à versão local) ---
        for i, page in enumerate(plumber_pdf.pages):
            text = page.extract_text()
            if not text:
                logging.warning(f"Página {i+1} sem texto.")
                continue

            nome_condominio = find_condominio_name(text)
            competencia_pagina = extrair_competencia(text)
            
            # Usa a primeira competência válida encontrada para o nome do ZIP
            if competencia_geral == "DataDesconhecida" and competencia_pagina != "DataDesconhecida":
                competencia_geral = competencia_pagina

            # Adiciona a página ao grupo do condomínio correspondente
            if nome_condominio not in condominios_agrupados:
                condominios_agrupados[nome_condominio] = {
                    'writer': PdfWriter(),
                    'competencia': competencia_pagina # Armazena a competência da primeira página do grupo
                }
            
            condominios_agrupados[nome_condominio]['writer'].add_page(reader.pages[i])
            logging.info(f"Página {i+1} adicionada ao grupo '{nome_condominio}'.")

        # --- Criação do ZIP (com nomenclatura EXATA) ---
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for nome_condominio, data in condominios_agrupados.items():
                writer = data['writer']
                competencia_grupo = data['competencia']

                # **AJUSTE CRÍTICO: Formato do nome do ficheiro idêntico ao sistema local**
                pdf_filename = f"Recibo de Pagamento {competencia_grupo} - {nome_condominio}.pdf"
                
                # Salva o PDF agrupado (com todas as suas páginas) num buffer
                page_buffer = io.BytesIO()
                writer.write(page_buffer)
                page_buffer.seek(0)
                
                # Adiciona o PDF do condomínio ao ZIP
                zipf.writestr(pdf_filename, page_buffer.getvalue())
                logging.info(f"Ficheiro '{pdf_filename}' adicionado ao ZIP.")

        zip_buffer.seek(0)
        
        # **AJUSTE CRÍTICO: Formato do nome do ZIP idêntico ao sistema local**
        zip_filename = f"Recibos de Pagamento {competencia_geral}.zip"
        
        return StreamingResponse(
            zip_buffer,
            media_type='application/zip',
            headers={'Content-Disposition': f'attachment; filename="{zip_filename}"'}
        )

    except Exception as e:
        logging.error(f"Erro ao processar PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno ao processar o PDF: {str(e)}")
