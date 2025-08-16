
# cobranca.py
# Adapter HTTP (FastAPI). Valida entrada/saída e chama engine.py.
from __future__ import annotations
from fastapi import APIRouter, Depends, Header, Request, Response, status
from typing import List, Optional
import time, uuid

import engine as core
from schemas import Client, Charge, Log, Settings, RecurringCharge, SyncResult

router = APIRouter(prefix="/api", tags=["cobranca"])

# --------- Observabilidade mínima (trace_id + duração) ----------

def with_trace(request: Request):
    trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
    start = time.perf_counter()
    try:
        yield trace_id
    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)
        # log simples em memória (poderia ir para Supabase futuramente)
        print({"event": "request_done", "path": request.url.path, "trace_id": trace_id, "duration_ms": duration_ms})

# -------------------- Clientes --------------------

@router.get("/clients", response_model=List[Client])
def get_clients(response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    return core.list_clients()

@router.post("/clients", response_model=Client, status_code=status.HTTP_201_CREATED)
def post_client(payload: Client, response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    return core.add_client(payload.model_dump())

@router.put("/clients/{client_id}", response_model=Client)
def put_client(client_id: str, payload: Client, response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    out = core.update_client(client_id, payload.model_dump(exclude_unset=True))
    if not out:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"id": client_id, "name": "NOT_FOUND"}
    return out

@router.delete("/clients/{client_id}")
def delete_client(client_id: str, response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    ok = core.delete_client(client_id)
    return {"deleted": ok}

@router.delete("/clients")
def clear_clients(response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    core.clear_clients()
    return {"message": "All clients cleared successfully"}

# -------------------- Cobranças --------------------

@router.get("/charges", response_model=List[Charge])
def get_charges(response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    return core.list_charges()

@router.post("/charges", response_model=Charge, status_code=status.HTTP_201_CREATED)
def post_charge(payload: Charge, response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    return core.add_charge(payload.model_dump())

@router.put("/charges/{charge_id}", response_model=Charge)
def put_charge(charge_id: str, payload: Charge, response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    out = core.update_charge(charge_id, payload.model_dump(exclude_unset=True))
    if not out:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"id": charge_id, "clientName": "NOT_FOUND"}
    return out

@router.delete("/charges/{charge_id}")
def delete_charge(charge_id: str, response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    ok = core.delete_charge(charge_id)
    return {"deleted": ok}

@router.delete("/charges")
def clear_charges(response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    core.clear_charges()
    return {"message": "All monthly charges cleared successfully"}

# -------------------- Logs --------------------

@router.get("/logs", response_model=List[Log])
def get_logs(response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    return core.list_logs()

@router.post("/logs", response_model=Log, status_code=status.HTTP_201_CREATED)
def post_log(payload: Log, response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    return core.add_log(payload.model_dump())

@router.delete("/logs")
def clear_logs(response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    core.clear_logs()
    return {"message": "All logs cleared successfully"}

# -------------------- Settings --------------------

@router.get("/settings", response_model=Settings)
def get_settings(response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    return core.get_settings()

@router.put("/settings", response_model=Settings)
def put_settings(payload: Settings, response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    return core.update_settings(payload.model_dump(exclude_unset=True))

# -------------------- Recorrentes --------------------

@router.get("/recurring_charges", response_model=List[RecurringCharge])
def get_recurrents(response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    return core.list_recurrents()

@router.post("/recurring_charges", response_model=RecurringCharge, status_code=status.HTTP_201_CREATED)
def post_recurrent(payload: RecurringCharge, response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    return core.add_recurrent(payload.model_dump())

@router.put("/recurring_charges/{rc_id}", response_model=RecurringCharge)
def put_recurrent(rc_id: str, payload: RecurringCharge, response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    out = core.update_recurrent(rc_id, payload.model_dump(exclude_unset=True))
    if not out:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"id": rc_id, "status": "NOT_FOUND"}
    return out

@router.delete("/recurring_charges/{rc_id}")
def delete_recurrent(rc_id: str, response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    ok = core.delete_recurrent(rc_id)
    return {"deleted": ok}

@router.delete("/recurring_charges")
def clear_recurrents(response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    core.clear_recurrents()
    return {"message": "All recurring charges cleared successfully"}

@router.post("/process_recurring_charges")
def process_recurrents(response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    count = core.process_recurrents()
    return {"message": f"Processamento concluído. {count} cobranças recorrentes processadas."}

# -------------------- Sincronização e Envio --------------------

@router.post("/sync_charges_with_clients", response_model=SyncResult)
def sync_with_clients(response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    updated = core.sync_charges_with_clients()
    return {"message": f"Sincronização concluída. {updated} cobranças atualizadas."}

@router.post("/send_whatsapp")
def send_whatsapp(payload: dict, response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    phone = payload.get("phoneNumber")
    message = payload.get("messageContent", "")
    if not core.is_valid_phone_number(phone):
        response.status_code = 400
        return {"status": "Erro", "error": "Número de telefone inválido."}
    return core.send_whatsapp_message(phone, message)

@router.post("/clear_all_data")
def clear_all(response: Response, trace_id: str = Depends(with_trace)):
    response.headers["X-Trace-Id"] = trace_id
    core.clear_all_data()
    return {"message": "All data cleared and settings reset successfully"}
