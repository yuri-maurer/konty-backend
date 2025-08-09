import os
import httpx
from fastapi import Depends, HTTPException, status, Request, APIRouter
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("Variáveis de ambiente SUPABASE_URL e SUPABASE_ANON_KEY devem ser definidas.")

# Cache simples do JWKS por KID
_jwks_cache = {"keys": []}

async def _fetch_jwks():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json", timeout=10.0)
        resp.raise_for_status()
        return resp.json()

def _find_key_by_kid(jwks, kid: str):
    for k in jwks.get("keys", []):
        if k.get("kid") == kid:
            return k
    return None

async def get_supabase_key_for_token(token: str):
    """Seleciona a chave pública correta do JWKS com base no 'kid' do token."""
    try:
        # Decodifica apenas o header do JWT (sem validar) para extrair o KID
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token sem KID. Faça login novamente."
            )

        # Procura no cache primeiro
        key = _find_key_by_kid(_jwks_cache, kid)
        if key:
            return key

        # Atualiza JWKS e tenta novamente
        jwks = await _fetch_jwks()
        _jwks_cache.clear()
        _jwks_cache.update(jwks)

        key = _find_key_by_kid(jwks, kid)
        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Chave pública não encontrada para o token. Faça login novamente."
            )
        return key
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao buscar JWKS no Supabase: {exc}",
        )

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Valida o JWT do Supabase usando a chave correta por KID e retorna dados básicos do usuário."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas. Por favor, faça login novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        key = await get_supabase_key_for_token(token)

        # Valida o token com a chave correta
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience="authenticated",
            issuer=f"{SUPABASE_URL}/auth/v1",
            options={"verify_aud": True, "verify_iss": True},
        )

        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception

        return {"id": user_id, "email": payload.get("email")}
    except JWTError:
        raise credentials_exception
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno na validação do token: {e}",
        )

router = APIRouter()
