# routes/pdf_processor.py
import io
import zipfile
import re
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from fuzzywuzzy import process
from unidecode import unidecode
from werkzeug.utils import secure_filename

router = APIRouter()

def find_condominio_name(text):
    """
    Usa uma lógica mais robusta para encontrar o nome do condomínio no texto de uma página.
    """
    lines = text.split('\n')
    # Procura por linhas que provavelmente contêm o nome do condomínio
    potential_names = [line for line in lines if 'CONDOMINIO' in unidecode(line).upper()]
    
    if not potential_names:
        # Tenta encontrar o CNPJ como um fallback para identificar um recibo
        cnpj_pattern = re.compile(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}')
        for line in lines:
            if cnpj_pattern.search(line):
                # Se encontrar um CNPJ, usa a linha acima como um candidato a nome
                try:
                    index = lines.index(line)
                    if index > 0:
                        potential_names.append(lines[index - 1])
                except ValueError:
                    continue

    if not potential_names:
        return None

    # Usa fuzzywuzzy para encontrar a correspondência mais provável, limpando o texto
    cleaned_names = [re.sub(r'CNPJ:.*', '', name).strip() for name in potential_names]
    best_match = process.extractOne("CONDOMINIO", cleaned_names, score_cutoff=60)
    
    return best_match[0] if best_match else None

@router.post("/processar-pdf", tags=["Módulos"])
async def processar_pdf(pdf_file: UploadFile = File(...)):
    """
    Recebe um ficheiro PDF, divide-o em recibos individuais de forma inteligente
    e retorna um ficheiro .zip com os PDFs resultantes.
    """
    if pdf_file.content_type != 'application/pdf':
        raise HTTPException(status_code=400, detail="Formato de ficheiro inválido. Apenas PDFs são aceites.")

    try:
        pdf_bytes = await pdf_file.read()
        pdf_stream = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_stream)
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            with pdfplumber.open(pdf_stream) as pdf:
                for i, page_content in enumerate(pdf.pages):
                    text = page_content.extract_text()
                    if not text:
                        continue

                    # Tenta encontrar o nome do condomínio na página
                    condominio_name = find_condominio_name(text) or f"recibo_desconhecido_{i+1}"
                    safe_filename = secure_filename(f"{condominio_name.replace(' ', '_')}.pdf")
                    
                    # Cria um novo PDF com a página atual usando PyPDF2
                    writer = PdfWriter()
                    writer.add_page(reader.pages[i])
                    
                    # Salva o novo PDF na memória
                    page_buffer = io.BytesIO()
                    writer.write(page_buffer)
                    page_buffer.seek(0)
                    
                    # Adiciona o novo PDF ao ficheiro ZIP
                    zipf.writestr(safe_filename, page_buffer.getvalue())

        zip_buffer.seek(0)
        
        return StreamingResponse(
            zip_buffer,
            media_type='application/zip',
            headers={'Content-Disposition': 'attachment; filename=recibos_processados.zip'}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno ao processar o PDF: {str(e)}")
