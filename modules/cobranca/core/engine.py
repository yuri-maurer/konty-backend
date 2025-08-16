# konty-backend/modules/cobranca/core/engine.py
import os
import json
import uuid
import requests
import re
from datetime import datetime, timedelta

# --- Configuração de Paths ---
# O DATA_DIR agora é relativo à localização deste ficheiro de engine.
# Isso garante que o módulo encontre seus dados, não importa de onde ele seja chamado.
try:
    # Caminho quando rodando no ambiente de produção/servidor
    MODULE_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.abspath(os.path.join(MODULE_BASE_DIR, '..', 'data'))
except NameError:
    # Fallback para ambientes onde __file__ não está definido (ex: alguns notebooks)
    DATA_DIR = 'modules/cobranca/data'

CLIENTS_FILE = os.path.join(DATA_DIR, 'clients.json')
CHARGES_FILE = os.path.join(DATA_DIR, 'charges.json')
LOGS_FILE = os.path.join(DATA_DIR, 'logs.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
RECURRING_CHARGES_FILE = os.path.join(DATA_DIR, 'recurring_charges.json')

# Garante que o diretório de dados exista
os.makedirs(DATA_DIR, exist_ok=True)

# --- Funções de Leitura/Escrita (Banco de Dados JSON) ---
def _load_data(filepath, default_value):
    """Carrega dados de um arquivo JSON. Se não existir, cria com valor padrão."""
    if not os.path.exists(filepath) or os.stat(filepath).st_size == 0:
        _save_data(filepath, default_value)
        return default_value
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        _save_data(filepath, default_value)
        return default_value

def _save_data(filepath, data):
    """Salva dados em um arquivo JSON."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- Funções de Validação ---
def is_valid_phone_number(phone):
    """Valida se o telefone contém apenas números e tem entre 8 e 15 dígitos."""
    if not phone: return False
    phone_str = str(phone).replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    return re.fullmatch(r'^\+?\d{8,15}$', phone_str) is not None

def is_valid_email(email):
    """Valida se o email tem um formato padrão."""
    if not email: return False
    email_str = str(email).strip()
    return re.fullmatch(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email_str) is not None

# --- Lógica de Negócio: Clientes ---
def get_all_clients():
    """Retorna a lista de todos os clientes."""
    return _load_data(CLIENTS_FILE, [])

def add_client(new_client_data):
    """Adiciona um novo cliente à base de dados."""
    clients = get_all_clients()
    new_client_data['id'] = str(uuid.uuid4())
    clients.append(new_client_data)
    _save_data(CLIENTS_FILE, clients)
    return new_client_data

def update_client(client_id, updated_fields):
    """Atualiza os dados de um cliente existente."""
    clients = get_all_clients()
    for client in clients:
        if client.get('id') == client_id:
            client.update(updated_fields)
            _save_data(CLIENTS_FILE, clients)
            return client
    return None # Retorna None se o cliente não for encontrado

def delete_client(client_id):
    """Deleta um cliente da base de dados."""
    clients = get_all_clients()
    initial_len = len(clients)
    clients = [c for c in clients if c.get('id') != client_id]
    if len(clients) < initial_len:
        _save_data(CLIENTS_FILE, clients)
        return True # Sucesso
    return False # Cliente não encontrado

def clear_all_clients():
    """Remove todos os clientes da base de dados."""
    _save_data(CLIENTS_FILE, [])
    return True

# --- Lógica de Negócio: Comunicação (Z-API) ---
def send_whatsapp_message(phone_number, message_content):
    """
    Coordena o envio de uma mensagem de WhatsApp, validando dados e chamando a Z-API.
    """
    settings = _load_data(SETTINGS_FILE, {})
    instance_id = settings.get('zapiInstanceId')
    token = settings.get('zapiToken')
    security_token = settings.get('zapiSecurityToken')

    if not all([instance_id, token, security_token]):
        return {"status": "Erro de Configuração", "message": "Credenciais da Z-API não configuradas no sistema."}

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
                 return {"status": "Enviado", "message": "Mensagem enviada com sucesso pela Z-API."}
            else:
                 return {"status": "Erro", "message": f"Z-API retornou sucesso, mas sem ID de mensagem: {response.text}"}
        else:
            return {"status": "Erro", "message": f"Falha na comunicação com a Z-API (HTTP {response.status_code}): {response.text}"}
            
    except requests.Timeout:
        return {"status": "Erro", "message": "Timeout ao tentar conectar com a Z-API."}
    except requests.RequestException as e:
        return {"status": "Erro", "message": f"Erro de conexão com a Z-API: {str(e)}"}

# NOTA: O restante da lógica de negócio (cobranças, logs, configurações, recorrências)
# seria movido para este ficheiro, seguindo exatamente o mesmo padrão de isolamento.
# Para manter a resposta focada no padrão, as funções adicionais foram omitidas,
# mas seriam adicionadas aqui.

