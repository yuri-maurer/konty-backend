import os
import httpx
from fastapi import Depends, HTTPException, status, Request, APIRouter
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Define o esquema OAuth2 para o token Bearer.
# O tokenUrl aponta para onde o cliente obteria o token,
# mas para Supabase, a validação é feita diretamente aqui.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Variáveis de ambiente para o Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Verifica se as variáveis de ambiente essenciais estão definidas
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("Variáveis de ambiente SUPABASE_URL e SUPABASE_ANON_KEY devem ser definidas.")

# Cache para a chave pública do Supabase
_supabase_public_key = None

async def get_supabase_public_key():
    """
    Busca a chave pública do Supabase para validação do JWT.
    Armazena em cache para evitar múltiplas requisições à API do Supabase.
    """
    global _supabase_public_key
    if _supabase_public_key:
        return _supabase_public_key

    try:
        # Faz uma requisição HTTP para o endpoint JWKS do Supabase para obter a chave pública
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
            response.raise_for_status() # Levanta uma exceção para status de erro HTTP
            jwks = response.json()
            # Supabase geralmente usa a primeira chave na lista de chaves JWKS
            _supabase_public_key = jwks["keys"][0]
            return _supabase_public_key
    except httpx.RequestError as exc:
        # Captura erros de rede ou conexão ao Supabase
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Não foi possível conectar ao Supabase para obter a chave pública: {exc}"
        )
    except Exception as exc:
        # Captura outras exceções inesperadas durante a obtenção da chave
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter a chave pública do Supabase: {exc}"
        )

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Função de dependência para validar o token JWT do Supabase e retornar os dados do usuário.
    Esta função será usada para proteger as rotas da API.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas. Por favor, faça login novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        public_key = await get_supabase_public_key() # Obtém a chave pública do Supabase
        
        # Decodifica o token JWT usando a chave pública, algoritmo e audiência/emissor esperados.
        # O algoritmo para tokens Supabase é geralmente RS256.
        # A audiência (aud) é "authenticated" e o emissor (iss) é a URL do Supabase Auth.
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience="authenticated",
            issuer=f"{SUPABASE_URL}/auth/v1"
        )
        
        # Extrai o ID do usuário (subject) do payload do token
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        # Você pode adicionar mais validações aqui, como verificar a expiração do token (exp)
        # ou buscar informações adicionais do usuário no seu banco de dados Supabase se necessário.
        
        # Retorna um dicionário simples com o ID do usuário e email (se disponível no token)
        return {"id": user_id, "email": payload.get("email")}
    except JWTError:
        # Captura erros relacionados à validação do JWT (assinatura inválida, token expirado, etc.)
        raise credentials_exception
    except Exception as e:
        # Captura outras exceções inesperadas durante a validação do token
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno na validação do token: {e}"
        )

# O router de autenticação pode ser usado para rotas relacionadas à autenticação,
# embora neste projeto a autenticação seja gerenciada pelo Supabase e esta seja uma dependência.
router = APIRouter()
