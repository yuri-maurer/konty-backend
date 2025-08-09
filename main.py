import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Importa os roteadores das funcionalidades
# CORREÇÃO: Usando imports absolutos para evitar o erro "ImportError" no deploy
from routes import painel, sistemas
from auth import router as auth_router

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = FastAPI(
    title="Konty API",
    description="API para centralizar o acesso aos sistemas internos da Kontymax.",
    version="1.0.0",
)

# -------------------------
# CORS dinâmico por ambiente
# -------------------------
# Lê ALLOWED_ORIGINS (separados por vírgula). Se não existir, cai no FRONTEND_URL (ou localhost)
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
if allowed_origins_env:
    origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    origins = [os.getenv("FRONTEND_URL", "http://localhost:3000")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # Permite requisições da(s) URL(s) definida(s)
    allow_credentials=True,       # Permite cookies de credenciais (se usados)
    allow_methods=["*"],          # Permite todos os métodos HTTP (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],          # Permite todos os cabeçalhos HTTP
)

# Inclui os roteadores das funcionalidades na aplicação FastAPI
app.include_router(auth_router, prefix="/auth", tags=["Autenticação"])
app.include_router(painel.router, prefix="/painel", tags=["Painel"])
app.include_router(sistemas.router, prefix="/sistemas", tags=["Sistemas"])

@app.get("/")
async def read_root():
    """
    Rota raiz para verificar o status da API.
    Retorna uma mensagem simples indicando que a API está online.
    """
    return {"message": "Konty API está online!"}
