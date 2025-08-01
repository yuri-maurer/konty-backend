from fastapi import APIRouter, Depends, HTTPException, status
from ..auth import get_current_user # Importa a dependência de autenticação
from ..utils.run_script import run_script # Importa a função para executar scripts

router = APIRouter()

@router.post("/cobranca")
async def execute_cobranca(current_user: dict = Depends(get_current_user)):
    """
    Rota protegida para executar o sistema de cobrança.
    Esta rota requer um usuário autenticado e verifica permissão (mock inicialmente).
    """
    # A lista de acessos disponíveis viria do banco de dados para o usuário atual.
    # Por enquanto, usamos uma lista mock para simular a verificação de permissão.
    user_acessos_mock = ["cobranca", "relatorios", "financeiro"] # Acessos mockados para este exemplo
    
    # Verifica se o usuário tem permissão para executar o sistema 'cobranca'
    if "cobranca" not in user_acessos_mock:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, # Retorna 403 Forbidden se não tiver permissão
            detail="Você não tem permissão para executar o sistema de cobrança."
        )

    try:
        # Chama a função 'run_script' para simular a execução do script de cobrança.
        # No futuro, 'run_script' executará o script Python real.
        result = await run_script("cobranca")
        return result
    except Exception as e:
        # Captura qualquer erro durante a execução do script e retorna um erro 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao executar o sistema de cobrança: {e}"
        )
