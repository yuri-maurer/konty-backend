
# schemas.py
# Modelos Pydantic (contrato) usados pelo adapter FastAPI.

from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field

class Client(BaseModel):
    id: Optional[str] = None
    name: str
    phone: Optional[str] = ""
    email: Optional[str] = ""
    # Campos adicionais livres

class Charge(BaseModel):
    id: Optional[str] = None
    clientName: str
    clientPhone: Optional[str] = ""
    clientEmail: Optional[str] = ""
    competence: Optional[str] = None
    dueDate: Optional[str] = None
    value: Optional[float] = 0.0
    sendStatus: Optional[str] = None
    whatsappStatus: Optional[str] = None
    importError: Optional[str] = None
    clientFound: Optional[bool] = True

class Log(BaseModel):
    id: Optional[str] = None
    timestamp: Optional[str] = None
    clientName: Optional[str] = None
    whatsapp: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    origin: Optional[str] = "Manual"

class Settings(BaseModel):
    zapiInstanceId: str = ""
    zapiToken: str = ""
    zapiSecurityToken: str = ""
    defaultMessage: str = "Prezado(a) (nome)..."
    dateFormat: str = "DD/MM/YYYY"
    currencyFormat: str = "BRL"

class RecurringCharge(BaseModel):
    id: Optional[str] = None
    clientName: str
    clientPhone: Optional[str] = ""
    messageTemplate: str
    value: float
    status: str = "Active"            # Active | Paused | Completed
    recurrenceType: str               # once | daily | weekly | monthly | yearly
    recurrenceInterval: Optional[int] = 1
    recurrenceDaysOfWeek: Optional[List[str]] = None
    recurrenceDayOfMonth: Optional[int] = None
    recurrenceMonthOfYear: Optional[int] = None
    dueDate: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    lastSentDate: Optional[str] = None
    nextSendDate: Optional[str] = None
    lastAttemptStatus: Optional[str] = None
    lastAttemptMessage: Optional[str] = None

class SyncResult(BaseModel):
    message: str
