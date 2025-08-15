# routes/pdf_processor.py
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from modules.extrair-pdf.core.engine import process_pdf_file, PdfProcessingError

router = APIRouter()

@router.post("/processar-pdf", tags=["Módulos"])
async def processar_pdf_adapter(pdf_file: UploadFile = File(...)):
    """
    Adaptador de API: recebe o upload, chama o core e retorna o ZIP
    com o mesmo nome inteligente usado no sistema local.
    """
    if pdf_file.content_type != 'application/pdf':
        raise HTTPException(status_code=400, detail="Formato de ficheiro inválido. Apenas PDFs são aceites.")

    try:
        pdf_bytes = await pdf_file.read()
        zip_buffer, zip_filename = process_pdf_file(pdf_bytes)

        return StreamingResponse(
            zip_buffer,
            media_type='application/zip',
            headers={'Content-Disposition': f'attachment; filename="{zip_filename}"'}
        )

    except PdfProcessingError as e:
        raise HTTPException(status_code=409, detail=f"Erro na regra de negócio: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno: {str(e)}")