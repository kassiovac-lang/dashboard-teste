"""
Versao de TESTE do sincronizador, usando Google Sheets em vez do Azure/
Microsoft Graph (util enquanto o acesso ao Azure nao esta disponivel).

Roda dentro do GitHub Actions, le a planilha do Google Sheets via uma
"conta de servico" (service account) e atualiza o dashboard HTML.

As credenciais vem de um Secret do GitHub (o JSON da conta de servico
inteiro, como texto) -- nunca ficam escritas no codigo.

Requisitos: pip install gspread google-auth openpyxl
"""

import json
import os
import re
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

# ============================== CONFIG ==============================

# ID da planilha do Google Sheets (esta na URL entre /d/ e /edit)
# Ex: https://docs.google.com/spreadsheets/d/AQUI_O_ID/edit
SHEET_ID = os.environ["GOOGLE_SHEET_ID"]

# Nome da aba dentro da planilha
WORKSHEET_NAME = os.environ.get("GOOGLE_WORKSHEET_NAME", "Sheet1")

# Caminho do HTML dentro do repositório
HTML_PATH = Path("dashboard_v10.html")

# Mesmo mapeamento de colunas usado nas outras versões
COLUMN_MAP = {
    "Seq.": "seq",
    "TAG": "tag",
    "Equipamento/Modelo": "equipamento",
    "Fabricante": "fabricante",
    "Funciona?": "funciona",
    "Obsoleto?": "obsoleto",
    "Análise/Teste": "analise",
    "Série": "serie",
    "Local": "local",
    "Potência": "potencia",
    "Tensão": "tensao",
    "Amperagem": "amperagem",
    "Última calibração": "ultimaCal",
    "Próxima calibração": "proximaCal",
    "Executante": "executante",
    "Patrimônio": "patrimonio",
    "Contrato CAL.": "contratoCal",
}

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# =====================================================================


def get_client():
    """Autentica com a conta de serviço a partir do Secret do GitHub."""
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def sheet_to_records(client) -> list:
    sheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)
    rows = sheet.get_all_values()
    headers = [h.strip() for h in rows[0]]

    records = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        record = {}
        for header, value in zip(headers, row):
            key = COLUMN_MAP.get(header)
            if key is None:
                continue
            record[key] = value.strip()
        if record.get("seq") or record.get("tag"):
            records.append(record)
    return records


def update_html(html_path: Path, records: list) -> bool:
    html = html_path.read_text(encoding="utf-8")
    new_array = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    new_line = f"const equipmentData = {new_array};"

    pattern = re.compile(r"const equipmentData = \[.*?\];", re.DOTALL)
    if not pattern.search(html):
        raise RuntimeError("Não encontrei 'const equipmentData = [...]' no HTML.")

    updated = pattern.sub(new_line, html, count=1)
    if updated == html:
        print("Sem mudanças nos dados.")
        return False

    html_path.write_text(updated, encoding="utf-8")
    print(f"HTML atualizado com {len(records)} equipamentos.")
    return True


def main():
    client = get_client()
    records = sheet_to_records(client)
    changed = update_html(HTML_PATH, records)

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")


if __name__ == "__main__":
    main()
