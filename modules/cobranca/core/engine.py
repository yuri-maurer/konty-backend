
# engine.py
# Camada de REGRA DE NEGÓCIO (pura). Sem FastAPI/HTTP.
# Mantém paridade com o backend local (Flask), mas separada do adapter.

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import json
import os
import re
import uuid
import requests

# ---------- Persistência em JSON (paridade com local) ----------

DATA_DIR = os.environ.get("COBRANCA_DATA_DIR", "data")
CLIENTS_FILE = os.path.join(DATA_DIR, "clients.json")
CHARGES_FILE = os.path.join(DATA_DIR, "charges.json")
LOGS_FILE = os.path.join(DATA_DIR, "logs.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
RECURRING_CHARGES_FILE = os.path.join(DATA_DIR, "recurring_charges.json")

DEFAULT_SETTINGS = {
    "zapiInstanceId": "",
    "zapiToken": "",
    "zapiSecurityToken": "",
    "defaultMessage": "Prezado(a) (nome), \\n\\nLembramos que o boleto referente à competência (competencia), no valor de (valor), \\nvence em (vencimento). \\n\\nPor favor, regularize sua situação para evitar juros e multas. \\n\\nAtenciosamente, \\nSua Empresa",
    "dateFormat": "DD/MM/YYYY",
    "currencyFormat": "BRL"
}

os.makedirs(DATA_DIR, exist_ok=True)

def _load_data(filepath: str, default_value):
    if not os.path.exists(filepath) or os.stat(filepath).st_size == 0:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(default_value, f, ensure_ascii=False, indent=4)
        return default_value
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_data(filepath: str, data) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Carrega ao importar (memória)
clients: List[Dict[str, Any]] = _load_data(CLIENTS_FILE, [])
charges: List[Dict[str, Any]] = _load_data(CHARGES_FILE, [])
logs: List[Dict[str, Any]] = _load_data(LOGS_FILE, [])
settings: Dict[str, Any] = _load_data(SETTINGS_FILE, DEFAULT_SETTINGS)
recurrents: List[Dict[str, Any]] = _load_data(RECURRING_CHARGES_FILE, [])

# ---------- Validações simples ----------

def is_valid_phone_number(phone: Optional[str]) -> bool:
    if not phone:
        return False
    phone_str = str(phone).replace(" ", "").replace("-", "")
    return re.fullmatch(r"^\+?\d{8,15}$", phone_str) is not None

def is_valid_email(email: Optional[str]) -> bool:
    if not email:
        return False
    email_str = str(email).strip()
    return re.fullmatch(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email_str) is not None

# ---------- Helpers de data/moeda ----------

def format_currency_backend(value: Any, currency_format: str) -> str:
    if value is None:
        return "N/A"
    try:
        v = float(value)
        if currency_format == "BRL":
            return f"R$ {v:,.2f}".replace(".", "X").replace(",", ".").replace("X", ",")
        if currency_format == "USD":
            return f"${v:,.2f}"
        return f"{v:,.2f}"
    except (ValueError, TypeError):
        return "N/A"

def format_date_backend(date_obj: Any, date_format: str) -> str:
    if date_obj is None:
        return "N/A"
    if not isinstance(date_obj, datetime):
        try:
            date_obj = datetime.fromisoformat(str(date_obj).replace("Z", "+00:00"))
        except Exception:
            return "N/A"
    if date_format == "DD/MM/YYYY":
        return date_obj.strftime("%d/%m/%Y")
    if date_format == "YYYY-MM-DD":
        return date_obj.strftime("%Y-%m-%d")
    return date_obj.strftime("%d/%m/%Y")

# ---------- Recorrência ----------

def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

def calculate_next_send_date(rc: Dict[str, Any]) -> Optional[datetime]:
    start_date = _parse_dt(rc.get("startDate"))
    end_date = _parse_dt(rc.get("endDate"))
    last_sent_date = _parse_dt(rc.get("lastSentDate"))
    now = datetime.now()
    next_send_date: Optional[datetime] = None

    if rc.get("status") == "Paused":
        return None

    if rc.get("recurrenceType") == "once":
        due_date = _parse_dt(rc.get("dueDate"))
        if due_date and (last_sent_date is None or last_sent_date < due_date):
            if due_date >= now:
                next_send_date = due_date
            elif last_sent_date is None:
                next_send_date = now
        elif not due_date and (last_sent_date is None or last_sent_date < now):
            next_send_date = start_date if start_date and start_date >= now else now
        if next_send_date and end_date and next_send_date > end_date:
            return None
        return next_send_date

    current_date_for_calc = last_sent_date or start_date
    if not current_date_for_calc:
        return None

    if current_date_for_calc > now and not last_sent_date:
        next_send_date = current_date_for_calc
    else:
        temp_date = max(current_date_for_calc, now)
        while True:
            rtype = rc.get("recurrenceType")
            interval = int(rc.get("recurrenceInterval", 1) or 1)
            if rtype == "daily":
                temp_date = temp_date + timedelta(days=interval)
            elif rtype == "weekly":
                day_map = {
                    "segunda": 0, "terça": 1, "terca":1, "quarta": 2,
                    "quinta": 3, "sexta": 4, "sábado": 5, "sabado":5, "domingo": 6
                }
                days = rc.get("recurrenceDaysOfWeek", [])
                if isinstance(days, str):
                    try:
                        import json as _json
                        days = _json.loads(days)
                    except Exception:
                        days = []
                target_weekdays = sorted([day_map.get(str(d).lower()) for d in days if str(d).lower() in day_map])
                if not target_weekdays:
                    return None
                search_start = (temp_date + timedelta(days=1)) if last_sent_date else temp_date
                found = False
                for i in range(7 * interval + 1):
                    check = search_start + timedelta(days=i)
                    if check.weekday() in target_weekdays:
                        next_send_date = check
                        found = True
                        break
                if not found:
                    temp_date = temp_date + timedelta(weeks=interval)
                    while temp_date.weekday() not in target_weekdays:
                        temp_date = temp_date + timedelta(days=1)
                    next_send_date = temp_date
            elif rtype == "monthly":
                interval = max(1, interval)
                year = temp_date.year
                month = temp_date.month + interval
                while month > 12:
                    month -= 12
                    year += 1
                day = int(rc.get("recurrenceDayOfMonth", 1) or 1)
                # último dia do mês alvo
                if month < 12:
                    last_day = (datetime(year, month+1, 1) - timedelta(days=1)).day
                else:
                    last_day = 31
                day = min(day, last_day)
                temp_date = datetime(year, month, day)
                next_send_date = temp_date
            elif rtype == "yearly":
                interval = max(1, interval)
                year = temp_date.year + interval
                month = int(rc.get("recurrenceMonthOfYear", temp_date.month) or temp_date.month)
                day = int(rc.get("recurrenceDayOfMonth", temp_date.day) or temp_date.day)
                if month < 12:
                    last_day = (datetime(year, month+1, 1) - timedelta(days=1)).day
                else:
                    last_day = 31
                day = min(day, last_day)
                temp_date = datetime(year, month, day)
                next_send_date = temp_date
            else:
                return None

            if next_send_date and next_send_date > now:
                break

    if next_send_date and end_date and next_send_date > end_date:
        return None
    return next_send_date

# ---------- CRUD / Operações ----------

def list_clients() -> List[Dict[str, Any]]:
    return clients

def add_client(data: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(data)
    data.setdefault("id", str(uuid.uuid4()))
    clients.append(data)
    _save_data(CLIENTS_FILE, clients)
    return data

def update_client(client_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for c in clients:
        if c.get("id") == client_id:
            c.update(fields)
            _save_data(CLIENTS_FILE, clients)
            return c
    return None

def delete_client(client_id: str) -> bool:
    global clients
    before = len(clients)
    clients[:] = [c for c in clients if c.get("id") != client_id]
    _save_data(CLIENTS_FILE, clients)
    return len(clients) != before

def clear_clients() -> None:
    clients.clear()
    _save_data(CLIENTS_FILE, clients)

def list_charges() -> List[Dict[str, Any]]:
    return charges

def _normalize_charge_mutation(payload: Dict[str, Any]) -> Dict[str, Any]:
    p = dict(payload)
    # dueDate ISO (se presente)
    dd = p.get("dueDate")
    if dd:
        try:
            p["dueDate"] = datetime.fromisoformat(str(dd).replace("Z", "+00:00")).isoformat()
        except Exception:
            pass
    # competence string
    if p.get("competence") is not None:
        p["competence"] = str(p["competence"])
    return p

def add_charge(payload: Dict[str, Any]) -> Dict[str, Any]:
    p = _normalize_charge_mutation(payload)
    p.setdefault("id", str(uuid.uuid4()))
    charges.append(p)
    _save_data(CHARGES_FILE, charges)
    return p

def update_charge(charge_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fields = _normalize_charge_mutation(fields)
    for ch in charges:
        if ch.get("id") == charge_id:
            ch.update(fields)
            _save_data(CHARGES_FILE, charges)
            return ch
    return None

def delete_charge(charge_id: str) -> bool:
    before = len(charges)
    charges[:] = [ch for ch in charges if ch.get("id") != charge_id]
    _save_data(CHARGES_FILE, charges)
    return len(charges) != before

def clear_charges() -> None:
    charges.clear()
    _save_data(CHARGES_FILE, charges)

def list_logs() -> List[Dict[str, Any]]:
    return logs

def add_log(entry: Dict[str, Any]) -> Dict[str, Any]:
    e = dict(entry)
    e.setdefault("id", str(uuid.uuid4()))
    e.setdefault("timestamp", datetime.now().isoformat())
    logs.append(e)
    _save_data(LOGS_FILE, logs)
    return e

def clear_logs() -> None:
    logs.clear()
    _save_data(LOGS_FILE, logs)

def get_settings() -> Dict[str, Any]:
    return settings

def update_settings(fields: Dict[str, Any]) -> Dict[str, Any]:
    settings.update(fields)
    _save_data(SETTINGS_FILE, settings)
    return settings

# ---------- Recorrentes ----------

def list_recurrents() -> List[Dict[str, Any]]:
    # recalcula nextSendDate on-read (paridade)
    for rc in recurrents:
        # casting para datetime
        for key in ("dueDate", "startDate", "endDate", "lastSentDate"):
            if isinstance(rc.get(key), str) or rc.get(key) is None:
                pass  # calculate_next_send_date já trata
        rc["nextSendDate"] = None
        nsd = calculate_next_send_date(rc)
        rc["nextSendDate"] = nsd.isoformat() if nsd else None
    _save_data(RECURRING_CHARGES_FILE, recurrents)
    return recurrents

def add_recurrent(payload: Dict[str, Any]) -> Dict[str, Any]:
    rc = dict(payload)
    rc.setdefault("id", str(uuid.uuid4()))
    rc["lastSentDate"] = None
    rc["lastAttemptStatus"] = None
    rc["lastAttemptMessage"] = None
    nsd = calculate_next_send_date(rc)
    rc["nextSendDate"] = nsd.isoformat() if nsd else None
    recurrents.append(rc)
    _save_data(RECURRING_CHARGES_FILE, recurrents)
    return rc

def update_recurrent(rc_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for rc in recurrents:
        if rc.get("id") == rc_id:
            rc.update(fields)
            nsd = calculate_next_send_date(rc)
            rc["nextSendDate"] = nsd.isoformat() if nsd else None
            _save_data(RECURRING_CHARGES_FILE, recurrents)
            return rc
    return None

def delete_recurrent(rc_id: str) -> bool:
    before = len(recurrents)
    recurrents[:] = [r for r in recurrents if r.get("id") != rc_id]
    _save_data(RECURRING_CHARGES_FILE, recurrents)
    return len(recurrents) != before

def clear_recurrents() -> None:
    recurrents.clear()
    _save_data(RECURRING_CHARGES_FILE, recurrents)

def sync_charges_with_clients() -> int:
    updated = 0
    for ch in charges:
        client = next((c for c in clients if c.get("name") == ch.get("clientName")), None)
        if client:
            if (ch.get("clientPhone") != client.get("phone")) or (ch.get("clientEmail") != client.get("email")) or (ch.get("importError") == "Dados de contato do cliente inválidos na base."):
                ch["clientPhone"] = client.get("phone", "")
                ch["clientEmail"] = client.get("email", "")
                if is_valid_phone_number(ch["clientPhone"]) and is_valid_email(ch["clientEmail"]):
                    ch["sendStatus"] = "Pendente"
                    ch["whatsappStatus"] = "Aguardando Envio"
                    ch["importError"] = ""
                else:
                    ch["sendStatus"] = "Erro"
                    ch["whatsappStatus"] = "Telefone Inválido"
                    ch["importError"] = "Dados de contato do cliente inválidos na base."
                updated += 1
            if ch.get("importError") == "Cliente não encontrado na base de clientes.":
                ch["clientFound"] = True
                ch["sendStatus"] = "Pendente"
                ch["whatsappStatus"] = "Aguardando Envio"
                ch["importError"] = ""
                updated += 1
        else:
            if ch.get("clientFound") or ch.get("importError") != "Cliente não encontrado na base de clientes.":
                ch["clientFound"] = False
                ch["sendStatus"] = "Erro"
                ch["whatsappStatus"] = "Cliente Não Encontrado"
                ch["importError"] = "Cliente não encontrado na base de clientes."
                updated += 1
    _save_data(CHARGES_FILE, charges)
    return updated

def send_whatsapp_message(phone_number: str, message_content: str) -> Dict[str, Any]:
    # Paridade com local: lê settings do disco a cada envio
    cfg = _load_data(SETTINGS_FILE, DEFAULT_SETTINGS)
    instance_id = cfg.get("zapiInstanceId")
    token = cfg.get("zapiToken")
    security_token = cfg.get("zapiSecurityToken")
    if not instance_id or not token or not security_token:
        return {"status": "Erro de Configuração", "message": "Credenciais Z-API ausentes no backend."}

    cleaned = "".join([c for c in str(phone_number) if c.isdigit()])
    if cleaned.startswith("0"):
        cleaned = cleaned[1:]

    url = f"https://api.z-api.io/instances/{instance_id}/token/{token}/send-text"
    headers = {"Client-Token": security_token, "Content-Type": "application/json"}
    payload = {"phone": cleaned, "message": message_content}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.ok:
            try:
                data = resp.json()
                if data.get("messageId") or data.get("id") or data.get("success") is True:
                    return {"status": "Enviado", "message": "Mensagem enviada com sucesso via Z-API."}
                else:
                    return {"status": "Erro", "message": f"Erro Z-API (2xx): {data.get('message') or data.get('error') or 'Falha lógica'}"}
            except Exception:
                return {"status": "Erro", "message": f"Erro Z-API: Resposta inválida. Status {resp.status_code}"}
        else:
            try:
                data = resp.json()
                em = data.get("message") or data.get("error") or f"Erro HTTP {resp.status_code}"
            except Exception:
                em = f"Erro HTTP {resp.status_code} sem JSON."
            return {"status": "Erro", "message": f"Erro Z-API: {em}"}
    except requests.exceptions.Timeout:
        return {"status": "Erro", "message": "Erro Z-API: Tempo limite excedido."}
    except requests.exceptions.ConnectionError as e:
        return {"status": "Erro", "message": f"Erro Z-API (conexão): {e}"}
    except requests.exceptions.RequestException as e:
        return {"status": "Erro", "message": f"Erro geral Z-API: {e}"}

def process_recurrents() -> int:
    processed = 0
    now = datetime.now()
    cfg = _load_data(SETTINGS_FILE, DEFAULT_SETTINGS)
    for rc in recurrents:
        nsd = calculate_next_send_date(rc)
        rc["nextSendDate"] = nsd.isoformat() if nsd else None
        if rc.get("status") == "Active" and rc.get("nextSendDate") and _parse_dt(rc["nextSendDate"]) <= now and (not _parse_dt(rc.get("endDate")) or _parse_dt(rc["endDate"]) >= now):
            client = next((c for c in clients if c.get("name") == rc.get("clientName")), None)
            if not client:
                msg = f"Cliente '{rc.get('clientName')}' não encontrado para recorrência."
                rc["lastAttemptStatus"] = "Erro"
                rc["lastAttemptMessage"] = msg
                add_log({"clientName": rc.get("clientName"), "whatsapp": rc.get("clientPhone", "N/A"), "status": "Erro", "message": msg, "origin": "Recorrente"})
                continue

            msg = rc.get("messageTemplate") or cfg.get("defaultMessage", "")
            msg = msg.replace("(nome)", rc.get("clientName") or "")
            msg = msg.replace("(valor)", format_currency_backend(rc.get("value"), cfg.get("currencyFormat", "BRL")))
            msg = msg.replace("(vencimento)", format_date_backend(_parse_dt(rc.get("dueDate")), cfg.get("dateFormat", "DD/MM/YYYY")))

            result = send_whatsapp_message(client.get("phone"), msg)

            rc["lastSentDate"] = now.isoformat()
            rc["lastAttemptStatus"] = result["status"]
            rc["lastAttemptMessage"] = result["message"]

            add_log({"clientName": rc.get("clientName"), "whatsapp": client.get("phone", "N/A"), "status": result["status"], "message": result["message"], "origin": "Recorrente"})
            if rc.get("recurrenceType") == "once" and result["status"] == "Enviado":
                rc["status"] = "Completed"
                rc["nextSendDate"] = None
            else:
                nsd2 = calculate_next_send_date(rc)
                rc["nextSendDate"] = nsd2.isoformat() if nsd2 else None
            processed += 1
    _save_data(RECURRING_CHARGES_FILE, recurrents)
    return processed

def clear_all_data() -> None:
    clients.clear()
    charges.clear()
    logs.clear()
    recurrents.clear()
    settings.clear()
    settings.update(DEFAULT_SETTINGS)
    _save_data(CLIENTS_FILE, clients)
    _save_data(CHARGES_FILE, charges)
    _save_data(LOGS_FILE, logs)
    _save_data(RECURRING_CHARGES_FILE, recurrents)
    _save_data(SETTINGS_FILE, settings)
