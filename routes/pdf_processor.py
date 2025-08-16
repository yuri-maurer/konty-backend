# routes/pdf_processor.py
import os
import importlib.util
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter()

def _load_engine_module():
    """Carrega modules/extrair-pdf/core/engine.py mesmo com hífen na pasta."""
    here = os.path.dirname(os.path.abspath(__file__))
    engine_path = os.path.abspath(os.path.join(here, "..", "modules", "extrair-pdf", "core", "engine.py"))
    if not os.path.exists(engine_path):
        raise ImportError(f"engine.py não encontrado no caminho esperado: {engine_path}")
    spec = importlib.util.spec_from_file_location("extrair_pdf_engine", engine_path)
    if spec is None or spec.loader is None:
        raise ImportError("Não foi possível criar spec para o engine.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

@router.post("/processar-pdf", tags=["Módulos"])
async def processar_pdf_adapter(pdf_file: UploadFile = File(...)):
    """Adaptador de API: recebe upload, chama o core e retorna o ZIP com nome inteligente."""
    if pdf_file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Formato de ficheiro inválido. Apenas PDFs são aceites.")

    try:
        engine = _load_engine_module()
        pdf_bytes = await pdf_file.read()
        result = engine.process_pdf_file(pdf_bytes)  # pode retornar (zip_buffer, zip_filename) ou apenas buffer
        if isinstance(result, tuple) and len(result) == 2:
            zip_buffer, zip_filename = result
        else:
            zip_buffer, zip_filename = result, "recibos_processados.zip"

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'}
        )
    except Exception as e:
        try:
            engine = _load_engine_module()
            PdfProcessingError = getattr(engine, "PdfProcessingError", None)
            if PdfProcessingError and isinstance(e, PdfProcessingError):
                raise HTTPException(status_code=409, detail=f"Erro na regra de negócio: {str(e)}")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno: {str(e)}")