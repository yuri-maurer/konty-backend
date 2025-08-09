import os
import time
import uuid
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Importa os roteadores das funcionalidades
from routes import painel, sistemas
from auth import router as auth_router

# Carrega as variáveis de ambiente
load_dotenv()

# -------------------------
# Configuração básica de logs
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("konty")

app = FastAPI(
    title="Konty API",
    description="API para centralizar o acesso aos sistemas internos da Kontymax.",
    version="1.0.0",
)

# -------------------------
# CORS dinâmico por ambiente
# -------------------------
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
if allowed_origins_env:
    origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    origins = [os.getenv("FRONTEND_URL", "http://localhost:3000")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Middleware de logging
# -------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    rid = str(uuid.uuid4())
    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "rid=%s method=%s path=%s status=%s duration_ms=%s ua=%s",
            rid,
            request.method,
            request.url.path,
            getattr(response, "status_code", "unknown"),
            duration_ms,
            request.headers.get("user-agent", "-"),
        )
        response.headers["X-Request-ID"] = rid
        response.headers["X-Response-Time"] = f"{duration_ms}ms"
        return response
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.exception(
            "rid=%s method=%s path=%s status=500 duration_ms=%s error=%s",
            rid, request.method, request.url.path, duration_ms, repr(exc)
        )
        raise

# -------------------------
# Middleware de segurança (headers)
# -------------------------
ENABLE_HSTS = os.getenv("ENABLE_HSTS", "1") == "1"

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)

    # Headers seguros padrão
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Bloqueia APIs de hardware por padrão
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # Isola a página de outras janelas (mitiga ataques de cross-origin)
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

    # HSTS apenas em HTTPS
    if ENABLE_HSTS and request.url.scheme == "https":
        # 2 anos; aplica a subdomínios (api.konty.com.br). Não usamos 'preload' por segurança.
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"

    return response

# Rotas
app.include_router(auth_router, prefix="/auth", tags=["Autenticação"])
app.include_router(painel.router, prefix="/painel", tags=["Painel"])
app.include_router(sistemas.router, prefix="/sistemas", tags=["Sistemas"])

@app.get("/")
async def read_root():
    return {"message": "Konty API está online!"}
