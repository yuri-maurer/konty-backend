from fastapi import APIRouter, Depends
# CORREÇÃO: Usando import absoluto para a dependência de autenticação
from auth import get_current_user 

router = APIRouter()

@router.get("/")
async def read_painel(current_user: dict = Depends(get_current_user)):
    """
    Rota protegida para o painel do usuário.
    Esta rota requer um usuário autenticado para ser acessada.
    Retorna informações básicas do usuário logado e uma lista de acessos disponíveis (mock).
    """
    # 'current_user' contém os dados do usuário decodificados do token JWT,
    # fornecidos pela função get_current_user.
    
    # Exemplo de dados de acessos disponíveis (mock inicialmente).
    # No futuro, esta lista virá do seu banco de dados, baseada nas permissões do usuário.
    mock_acessos = ["cobranca", "relatorios", "financeiro", "auditoria"] 

    return {
        "message": f"Bem-vindo ao painel, {current_user['email']}!",
        "user_id": current_user['id'],
        "user_email": current_user['email'],
        "acessos_disponiveis": mock_acessos # Retorna a lista de sistemas que o usuário pode acessar
    }
