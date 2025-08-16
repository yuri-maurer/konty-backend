# modules/extrair-pdf/core/engine.py
import io
import re
import zipfile
from datetime import datetime

import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
from unidecode import unidecode

class PdfProcessingError(Exception):
    """Exceção personalizada para erros de processamento de PDF."""
    pass

# ----------------------
# Funções de extração
# ----------------------
def extrair_competencia(text: str) -> str:
    """
    Extrai competência no formato MM.AAAA ou por mês escrito ("Março de 2024")
    e padroniza para MM.AAAA. Retorna "DataDesconhecida" quando não identifica.
    """
    match = re.search(r'(0[1-9]|1[0-2])\.(20\d{2})', text)
    if match:
        return match.group(0)

    match2 = re.search(
        r'((?:Jan|Fev|Mar|Abr|Mai|Jun|Jul|Ago|Set|Out|Nov|Dez)[a-z]*|'
        r'janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|'
        r'setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})',
        text, flags=re.IGNORECASE
    )
    if match2:
        meses_map = {
            'janeiro': '01', 'fevereiro': '02', 'março': '03', 'marco': '03', 'abril': '04',
            'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08', 'setembro': '09',
            'outubro': '10', 'novembro': '11', 'dezembro': '12',
            'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04', 'mai': '05', 'jun': '06',
            'jul': '07', 'ago': '08', 'set': '09', 'out': '10', 'nov': '11', 'dez': '12'
        }
        mes_txt = match2.group(1).lower()
        ano = match2.group(2)
        mes_num = meses_map.get(mes_txt[:3], 'XX')
        return f"{mes_num}.{ano}"

    return "DataDesconhecida"

def extrair_codigo_nome_funcionario(text: str):
    """Extrai 'Código' e 'Nome do Funcionário' quando disponíveis."""
    codigo = "CodigoDesconhecido"
    nome = "NomeDesconhecido"

    m_cod = re.search(r'Código\s*\n?\s*(\d+)', text, re.IGNORECASE)
    if m_cod:
        codigo = m_cod.group(1).strip()

    m_nome = re.search(r'Nome\s+do\s+Funcionário\s*\n?\s*([A-Z\s\.-]+)', text, re.IGNORECASE)
    if m_nome:
        nome_completo = m_nome.group(1).strip()
        nome = re.sub(r'\s*(\(CBO:|\(A\)|[A-Z\s]*\d{4})\s*$', '', nome_completo).strip()
        nome = re.sub(r'\s*\n\s*', ' ', nome).strip()

    return codigo, nome

def extrair_condominio_cnpj(text: str):
    """Extrai nome bruto do condomínio (linha antes de CNPJ/CC ou primeira linha) e CNPJ."""
    condominio = "CondominioDesconhecido"
    cnpj = "CNPJDesconhecido"

    m_cnpj = re.search(r'CNPJ:\s*(\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2})', text)
    if m_cnpj:
        cnpj = m_cnpj.group(1).strip()

    m_cond = re.search(r'^(.*?)\s*(?:CNPJ:|CC:)', text, re.MULTILINE | re.IGNORECASE)
    if m_cond:
        condominio_bruto = m_cond.group(1).strip()
        condominio_bruto = re.sub(r'^Folha Mensal\s*', '', condominio_bruto, flags=re.IGNORECASE).strip()
        condominio = condominio_bruto if condominio_bruto else "CondominioDesconhecido"
    else:
        first_line_match = re.match(r'^\s*([^\n\r]+)', text)
        if first_line_match:
            condominio_bruto = first_line_match.group(1).strip()
            condominio_bruto = re.sub(r'\s*Folha Mensal$', '', condominio_bruto, flags=re.IGNORECASE).strip()
            condominio = condominio_bruto if condominio_bruto else "CondominioDesconhecido"

    return condominio, cnpj

def clean_condominio_name(name: str) -> str:
    """Normaliza o nome do condomínio removendo ruídos e acentos."""
    if not name:
        return "CONDOMINIO DESCONHECIDO"
    name = re.sub(r'\s*(?:CNPJ:|CC:)\s*.*?(?:Folha Mensal|$)', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'Folha Mensal$', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'CONDOMINIO\s+EDIFICIO\s+', 'CONDOMINIO ', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'\s+', ' ', name).strip()
    # Mantém espaços; só remove acentos e padroniza maiúsculas
    return unidecode(name).upper()

# ----------------------
# Função principal
# ----------------------
def process_pdf_file(pdf_bytes: bytes):
    """
    Processa o PDF, agrupa por condomínio e gera um ZIP.
    Retorna (zip_buffer: BytesIO, zip_filename: str).
    """
    try:
        pdf_file_bytes = io.BytesIO(pdf_bytes)

        with pdfplumber.open(pdf_file_bytes) as pdf:
            pdf_reader = PdfReader(pdf_file_bytes)
            condominios_agrupados = {}  # { nome_condominio: {'writer': PdfWriter(), 'competencia': str} }
            competencia_geral = "DataDesconhecida"

            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if not page_text:
                    continue

                competencia_str = extrair_competencia(page_text)
                condominio_bruto, _ = extrair_condominio_cnpj(page_text)
                nome_condominio_limpo = clean_condominio_name(condominio_bruto)

                if competencia_geral == "DataDesconhecida" and competencia_str != "DataDesconhecida":
                    competencia_geral = competencia_str

                if nome_condominio_limpo not in condominios_agrupados:
                    condominios_agrupados[nome_condominio_limpo] = {
                        'writer': PdfWriter(),
                        'competencia': competencia_str
                    }

                condominios_agrupados[nome_condominio_limpo]['writer'].add_page(pdf_reader.pages[i])

        # Monta ZIP em memória
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zf:
            zip_buffer.seek(0)

            for condominio_nome, data in condominios_agrupados.items():
                writer = data['writer']
                competencia_grupo = data.get('competencia', "DataDesconhecida")

                if competencia_grupo != "DataDesconhecida":
                    pdf_filename = f"Recibo de Pagamento {competencia_grupo} - {condominio_nome}.pdf")
                else:
                    pdf_filename = f"Recibo de Pagamento - {condominio_nome} - {datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

                grouped_pdf_buffer = io.BytesIO()
                writer.write(grouped_pdf_buffer)
                grouped_pdf_buffer.seek(0)

                # IMPORTANTE: não usar secure_filename — manter espaços e acentos
                zf.writestr(pdf_filename, grouped_pdf_buffer.getvalue())

        if competencia_geral != "DataDesconhecida":
            zip_filename = f"Recibos de Pagamento {competencia_geral}.zip"
        else:
            if condominios_agrupados:
                primeiro_condominio = next(iter(condominios_agrupados))
                zip_filename = f"Recibos de Pagamento - {primeiro_condominio}.zip"
            else:
                zip_filename = f"Recibos de Pagamento - {datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

        zip_buffer.seek(0)
        return zip_buffer, zip_filename

    except Exception as e:
        raise PdfProcessingError(f"Erro no processamento do PDF: {str(e)}")