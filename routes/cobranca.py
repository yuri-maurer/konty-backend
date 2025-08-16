# konty-backend/routes/cobranca.py
from fastapi import APIRouter, HTTPException, Body, status
from typing import List, Dict, Any
from modules.cobranca.core import engine

router = APIRouter(
    prefix="/cobranca",
    tags=["Sistema de Cobrança"]
)

# --- Rotas de Clientes ---
@router.get("/clients", response_model=List[Dict[str, Any]])
async def get_clients():
    return engine.get_all_clients()

@router.post("/clients", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_client(client_data: Dict[str, Any] = Body(...)):
    if not all(k in client_data for k in ["name", "phone", "email"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome, telefone e email são obrigatórios.")
    return engine.add_client(client_data)

@router.put("/clients/{client_id}", response_model=Dict[str, Any])
async def update_client_route(client_id: str, updated_fields: Dict[str, Any] = Body(...)):
    updated_client = engine.update_client(client_id, updated_fields)
    if not updated_client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    return updated_client

@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client_route(client_id: str):
    if not engine.delete_client(client_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    return

@router.delete("/clients", status_code=status.HTTP_204_NO_CONTENT)
async def clear_clients_route():
    engine.clear_all_clients()
    return

# --- Rotas de Cobranças Mensais ---
@router.get("/charges", response_model=List[Dict[str, Any]])
async def get_charges():
    return engine.get_all_charges()

@router.post("/charges", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_charge(charge_data: Dict[str, Any] = Body(...)):
    return engine.add_charge(charge_data)

@router.put("/charges/{charge_id}", response_model=Dict[str, Any])
async def update_charge_route(charge_id: str, updated_fields: Dict[str, Any] = Body(...)):
    updated_charge = engine.update_charge(charge_id, updated_fields)
    if not updated_charge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cobrança não encontrada")
    return updated_charge

@router.delete("/charges/{charge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_charge_route(charge_id: str):
    if not engine.delete_charge(charge_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cobrança não encontrada")
    return

@router.delete("/charges", status_code=status.HTTP_204_NO_CONTENT)
async def clear_charges_route():
    engine.clear_all_charges()
    return

# --- Rotas de Logs ---
@router.get("/logs", response_model=List[Dict[str, Any]])
async def get_logs():
    return engine.get_all_logs()

@router.post("/logs", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_log(log_data: Dict[str, Any] = Body(...)):
    return engine.add_log(log_data)

@router.delete("/logs", status_code=status.HTTP_204_NO_CONTENT)
async def clear_logs_route():
    engine.clear_all_logs()
    return

# --- Rotas de Configurações ---
@router.get("/settings", response_model=Dict[str, Any])
async def get_settings_route():
    return engine.get_settings()

@router.put("/settings", response_model=Dict[str, Any])
async def update_settings_route(settings_data: Dict[str, Any] = Body(...)):
    return engine.update_settings(settings_data)

# --- Rotas de Ações ---
@router.post("/send_whatsapp", response_model=Dict[str, str])
async def send_whatsapp_message_route(data: Dict[str, str] = Body(...)):
    phone = data.get("phoneNumber")
    message = data.get("messageContent")
    if not phone or not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="phoneNumber e messageContent são obrigatórios.")
    
    result = engine.send_whatsapp_message(phone, message)
    if "Erro" in result.get("status", ""):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result.get("message"))
    return result

@router.post("/sync_charges", response_model=Dict[str, Any])
async def sync_charges_route():
    return engine.sync_charges_with_clients()

@router.post("/clear_all_data", response_model=Dict[str, str])
async def clear_all_data_route():
    engine.clear_all_data()
    return {"message": "Todos os dados foram limpos com sucesso."}

