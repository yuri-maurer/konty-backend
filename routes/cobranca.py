# konty-backend/routes/cobranca.py
from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any
from modules.cobranca.core import engine

# Cria um "roteador" para agrupar todos os endpoints deste módulo.
# O prefixo "/cobranca" será adicionado a todas as URLs definidas aqui.
# A tag agrupa os endpoints na documentação automática da API (ex: /docs).
router = APIRouter(
    prefix="/cobranca",
    tags=["Sistema de Cobrança"]
)

# --- Rotas de Clientes ---

@router.get("/clients", response_model=List[Dict[str, Any]])
async def get_clients():
    """Endpoint para obter a lista de todos os clientes."""
    return engine.get_all_clients()

@router.post("/clients", response_model=Dict[str, Any], status_code=201)
async def create_client(client_data: Dict[str, Any] = Body(...)):
    """Endpoint para adicionar um novo cliente."""
    # Validação básica de entrada
    if not client_data.get("name") or not client_data.get("phone") or not client_data.get("email"):
        raise HTTPException(status_code=400, detail="Nome, telefone e email são obrigatórios.")
    return engine.add_client(client_data)

@router.put("/clients/{client_id}", response_model=Dict[str, Any])
async def update_client_route(client_id: str, updated_fields: Dict[str, Any] = Body(...)):
    """Endpoint para atualizar um cliente existente pelo seu ID."""
    updated_client = engine.update_client(client_id, updated_fields)
    if not updated_client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return updated_client

@router.delete("/clients/{client_id}")
async def delete_client_route(client_id: str):
    """Endpoint para deletar um cliente pelo seu ID."""
    success = engine.delete_client(client_id)
    if not success:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return {"message": "Cliente deletado com sucesso"}

@router.delete("/clients", summary="Limpar todos os clientes")
async def clear_clients_route():
    """Endpoint para remover todos os clientes da base de dados."""
    engine.clear_all_clients()
    return {"message": "Todos os clientes foram removidos com sucesso"}

# --- Rota de Envio de Mensagem ---

@router.post("/send_whatsapp", summary="Enviar mensagem de WhatsApp")
async def send_whatsapp_message_route(data: Dict[str, str] = Body(...)):
    """Endpoint para enviar uma única mensagem de WhatsApp via Z-API."""
    phone = data.get("phoneNumber")
    message = data.get("messageContent")
    
    if not phone or not message:
        raise HTTPException(status_code=400, detail="Os campos 'phoneNumber' e 'messageContent' são obrigatórios.")
    
    result = engine.send_whatsapp_message(phone, message)
    
    # Se o engine retornar um erro, converte-o para uma resposta HTTP de erro
    if "Erro" in result.get("status", ""):
        # Usamos 409 (Conflict) para erros de negócio/configuração e 500 para falhas de conexão
        status_code = 409 if "Configuração" in result.get("status", "") else 500
        raise HTTPException(status_code=status_code, detail=result.get("message", "Erro desconhecido"))
        
    return result

# NOTA: As outras rotas para Cobranças, Logs, Configurações e Recorrências
# seriam adicionadas aqui, seguindo exatamente o mesmo padrão:
# 1. Definir a rota com @router.<metodo>("/url").
# 2. Chamar a função correspondente do `engine`.
# 3. Tratar o retorno e levantar HTTPException em caso de erro.

