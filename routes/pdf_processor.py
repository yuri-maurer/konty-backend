# routes/pdf_processor.py
import fitz  # PyMuPDF
import io
import zipfile
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from werkzeug.utils import secure_filename

# Cria um "roteador" específico para este módulo.
# Todas as rotas definidas aqui terão o prefixo que definirmos no main.py.
router = APIRouter()

@router.post("/processar-pdf", tags=["Módulos"])
async def processar_pdf(pdf_file: UploadFile = File(...)):
    """
    Recebe um ficheiro PDF, divide-o em páginas individuais baseadas no nome do condomínio
    e retorna um ficheiro .zip com os PDFs resultantes.
    """
    # Verifica se o ficheiro é realmente um PDF
    if pdf_file.content_type != 'application/pdf':
        raise HTTPException(status_code=400, detail="Formato de ficheiro inválido. Apenas PDFs são aceites.")

    try:
        # Lê o conteúdo do ficheiro enviado para a memória
        pdf_bytes = await pdf_file.read()
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # Prepara para criar um ficheiro ZIP na memória
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Itera por cada página do PDF
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                
                # Extrai o texto para encontrar o nome do condomínio
                text = page.get_text("text")
                lines = text.split('\n')
                
                condominio_name = f"recibo_pag_{page_num + 1}" # Nome padrão
                for line in lines:
                    if "CONDOMINIO" in line.upper():
                        potential_name = line.replace("CONDOMINIO", "").strip()
                        if len(potential_name) > 3:
                            condominio_name = potential_name
                            break
                
                # Limpa o nome para ser um nome de ficheiro válido
                safe_filename = secure_filename(f"{condominio_name.replace(' ', '_')}.pdf")

                # Cria um novo PDF com apenas a página atual
                new_pdf = fitz.open()
                new_pdf.insert_pdf(pdf_document, from_page=page_num, to_page=page_num)
                
                pdf_output_bytes = new_pdf.tobytes()
                new_pdf.close()
                
                # Adiciona o novo PDF ao ficheiro ZIP
                zipf.writestr(safe_filename, pdf_output_bytes)

        pdf_document.close()
        zip_buffer.seek(0)
        
        # Envia o ficheiro ZIP como resposta
        return StreamingResponse(
            zip_buffer,
            media_type='application/zip',
            headers={'Content-Disposition': 'attachment; filename=recibos_processados.zip'}
        )

    except Exception as e:
        # Em caso de erro, retorna uma mensagem clara
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno ao processar o PDF: {str(e)}")
