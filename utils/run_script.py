import asyncio
import subprocess

async def run_script(script_name: str):
    """
    Função para executar um script Python via subprocess.run().
    Atualmente, é um mock que simula a execução de um script.

    No futuro, esta função será substituída para chamar os scripts Python reais
    localizados no ambiente do escritório.

    Exemplo de como a implementação real poderia ser:
    ```python
    # Caminho base para os seus scripts Python reais
    scripts_base_path = "/caminho/para/seus/scripts/" 
    script_path = os.path.join(scripts_base_path, f"{script_name}.py")

    # Executa o script Python como um subprocesso
    process = await asyncio.create_subprocess_exec(
        "python", script_path,
        stdout=subprocess.PIPE, # Captura a saída padrão
        stderr=subprocess.PIPE  # Captura a saída de erro padrão
    )
    
    # Aguarda a conclusão do subprocesso e obtém as saídas
    stdout, stderr = await process.communicate()
    
    # Verifica o código de retorno do subprocesso
    if process.returncode != 0:
        # Se o script retornou um erro, retorna o status de erro e a mensagem de erro
        return {"status": "error", "message": stderr.decode('utf-8').strip()}
    else:
        # Se o script foi executado com sucesso, retorna o status ok e a saída padrão
        return {"status": "ok", "message": stdout.decode('utf-8').strip()}
    ```
    """
    await asyncio.sleep(2) # Simula um atraso de 2 segundos na execução do script
    return {"status": "ok", "sistema": f"{script_name} executado com sucesso (mock)!"}
