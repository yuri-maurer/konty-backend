# konty-backend/modules/cobranca/core/engine.py
import os
import json
import uuid
import requests
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# --- Configuração de Paths ---
try:
    MODULE_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.abspath(os.path.join(MODULE_BASE_DIR, '..', 'data'))
except NameError:
    DATA_DIR = 'modules/cobranca/data'

CLIENTS_FILE = os.path.join(DATA_DIR, 'clients.json')
CHARGES_FILE = os.path.join(DATA_DIR, 'charges.json')
LOGS_FILE = os.path.join(DATA_DIR, 'logs.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
RECURRING_CHARGES_FILE = os.path.join(DATA_DIR, 'recurring_charges.json')

os.makedirs(DATA_DIR, exist_ok=True)

# --- Funções de Leitura/Escrita (Banco de Dados JSON) ---
def _load_data(filepath: str, default_value: Any) -> Any:
    if not os.path.exists(filepath) or os.stat(filepath).st_size == 0:
        _save_data(filepath, default_value)
        return default_value
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        _save_data(filepath, default_value)
        return default_value

def _save_data(filepath: str, data: Any):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- Funções de Validação ---
def is_valid_phone_number(phone: str) -> bool:
    if not phone: return False
    phone_str = str(phone).replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    return re.fullmatch(r'^\+?\d{8,15}$', phone_str) is not None

def is_valid_email(email: str) -> bool:
    if not email: return False
    email_str = str(email).strip()
    return re.fullmatch(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email_str) is not None

# --- Lógica de Negócio: Clientes ---
def get_all_clients() -> List[Dict[str, Any]]:
    return _load_data(CLIENTS_FILE, [])

def add_client(new_client_data: Dict[str, Any]) -> Dict[str, Any]:
    clients = get_all_clients()
    new_client_data['id'] = str(uuid.uuid4())
    clients.append(new_client_data)
    _save_data(CLIENTS_FILE, clients)
    return new_client_data

def update_client(client_id: str, updated_fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    clients = get_all_clients()
    for client in clients:
        if client.get('id') == client_id:
            client.update(updated_fields)
            _save_data(CLIENTS_FILE, clients)
            return client
    return None

def delete_client(client_id: str) -> bool:
    clients = get_all_clients()
    initial_len = len(clients)
    clients = [c for c in clients if c.get('id') != client_id]
    if len(clients) < initial_len:
        _save_data(CLIENTS_FILE, clients)
        return True
    return False

def clear_all_clients():
    _save_data(CLIENTS_FILE, [])
    return True

# --- Lógica de Negócio: Cobranças Mensais ---
def get_all_charges() -> List[Dict[str, Any]]:
    return _load_data(CHARGES_FILE, [])

def add_charge(new_charge_data: Dict[str, Any]) -> Dict[str, Any]:
    charges = get_all_charges()
    new_charge_data['id'] = str(uuid.uuid4())
    charges.append(new_charge_data)
    _save_data(CHARGES_FILE, charges)
    return new_charge_data

def update_charge(charge_id: str, updated_fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    charges = get_all_charges()
    for charge in charges:
        if charge.get('id') == charge_id:
            charge.update(updated_fields)
            _save_data(CHARGES_FILE, charges)
            return charge
    return None

def delete_charge(charge_id: str) -> bool:
    charges = get_all_charges()
    initial_len = len(charges)
    charges = [c for c in charges if c.get('id') != charge_id]
    if len(charges) < initial_len:
        _save_data(CHARGES_FILE, charges)
        return True
    return False

def clear_all_charges():
    _save_data(CHARGES_FILE, [])
    return True

# --- Lógica de Negócio: Logs ---
def get_all_logs() -> List[Dict[str, Any]]:
    return _load_data(LOGS_FILE, [])

def add_log(new_log_data: Dict[str, Any]) -> Dict[str, Any]:
    logs = get_all_logs()
    new_log_data['id'] = str(uuid.uuid4())
    new_log_data['timestamp'] = datetime.now().isoformat()
    logs.insert(0, new_log_data) # Insere no início para manter os mais recentes primeiro
    _save_data(LOGS_FILE, logs)
    return new_log_data

def clear_all_logs():
    _save_data(LOGS_FILE, [])
    return True

# --- Lógica de Negócio: Configurações ---
def get_settings() -> Dict[str, Any]:
    return _load_data(SETTINGS_FILE, {
        "zapiInstanceId": "", "zapiToken": "", "zapiSecurityToken": "",
        "defaultMessage": "Prezado(a) (nome), \n\nLembramos que o boleto referente à competência (competencia), no valor de (valor), \nvence em (vencimento). \n\nPor favor, regularize sua situação para evitar juros e multas. \n\nAtenciosamente, \nSua Empresa",
        "dateFormat": "DD/MM/YYYY", "currencyFormat": "BRL"
    })

def update_settings(updated_fields: Dict[str, Any]) -> Dict[str, Any]:
    settings = get_settings()
    settings.update(updated_fields)
    _save_data(SETTINGS_FILE, settings)
    return settings

# --- Lógica de Negócio: Comunicação (Z-API) ---
def send_whatsapp_message(phone_number: str, message_content: str) -> Dict[str, str]:
    settings = get_settings()
    instance_id = settings.get('zapiInstanceId')
    token = settings.get('zapiToken')
    security_token = settings.get('zapiSecurityToken')

    if not all([instance_id, token, security_token]):
        return {"status": "Erro de Configuração", "message": "Credenciais da Z-API não configuradas."}

    if not is_valid_phone_number(phone_number):
        return {'status': 'Erro', 'message': 'Número de telefone inválido.'}

    cleaned_phone = ''.join(filter(str.isdigit, str(phone_number)))
    zapi_url = f"https://api.z-api.io/instances/{instance_id}/token/{token}/send-text"
    headers = {"Client-Token": security_token, "Content-Type": "application/json"}
    payload = {"phone": cleaned_phone, "message": message_content}

    try:
        response = requests.post(zapi_url, headers=headers, json=payload, timeout=20)
        if response.ok:
            response_json = response.json()
            if response_json.get('messageId') or response_json.get('id'):
                return {"status": "Enviado", "message": "Mensagem enviada com sucesso."}
            else:
                return {"status": "Erro", "message": f"Z-API OK, mas sem ID de msg: {response.text}"}
        else:
            return {"status": "Erro", "message": f"Falha Z-API (HTTP {response.status_code}): {response.text}"}
    except requests.Timeout:
        return {"status": "Erro", "message": "Timeout ao conectar com a Z-API."}
    except requests.RequestException as e:
        return {"status": "Erro", "message": f"Erro de conexão com a Z-API: {str(e)}"}

# --- Lógica de Negócio: Sincronização e Ações em Lote ---
def sync_charges_with_clients() -> Dict[str, Any]:
    charges = get_all_charges()
    clients = get_all_clients()
    clients_map = {client['name']: client for client in clients}
    updated_count = 0

    for charge in charges:
        client_data = clients_map.get(charge['clientName'])
        if client_data:
            charge['clientPhone'] = client_data.get('phone', '')
            charge['clientEmail'] = client_data.get('email', '')
            if is_valid_phone_number(charge['clientPhone']):
                charge['sendStatus'] = 'Pendente'
                charge['importError'] = ''
            else:
                charge['sendStatus'] = 'Erro'
                charge['importError'] = 'Telefone inválido na base de clientes.'
            updated_count += 1
        else:
            charge['sendStatus'] = 'Erro'
            charge['importError'] = 'Cliente não encontrado na base.'
    
    _save_data(CHARGES_FILE, charges)
    return {'message': f'Sincronização concluída. {updated_count} cobranças atualizadas.'}

def clear_all_data() -> bool:
    clear_all_clients()
    clear_all_charges()
    clear_all_logs()
    # Não limpa as configurações, apenas os dados
    _save_data(RECURRING_CHARGES_FILE, [])
    return True

# NOTA: A lógica de cobranças recorrentes é complexa e seria adicionada aqui.
# Para esta correção, focamos em ter as entidades principais funcionais.
