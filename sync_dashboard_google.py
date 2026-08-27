import json
import os
import re
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials


SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
WORKSHEET_NAME = os.environ.get(
    "GOOGLE_WORKSHEET_NAME",
    "Equipamentos",
)
HTML_PATH = Path("dashboard_v10.html")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly"
]

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
    "Contrato CAL": "contratoCal",
    "Contrato CAL.": "contratoCal",
}


def get_client():
    """Autentica usando o JSON armazenado nos Secrets do GitHub."""
    credentials_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    credentials_info = json.loads(credentials_json)

    credentials = Credentials.from_service_account_info(
        credentials_info,
        scopes=SCOPES,
    )

    return gspread.authorize(credentials)


def sheet_to_records(client):
    """Lê a planilha e converte as linhas para o formato do dashboard."""
    worksheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)
    rows = worksheet.get_all_values()

    if not rows:
        raise RuntimeError("A planilha está vazia.")

    headers = [header.strip() for header in rows[0]]
    records = []

    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue

        record = {
            dashboard_name: ""
            for dashboard_name in dict.fromkeys(COLUMN_MAP.values())
        }

        for index, header in enumerate(headers):
            dashboard_name = COLUMN_MAP.get(header)

            if dashboard_name is None:
                continue

            value = row[index].strip() if index < len(row) else ""
            record[dashboard_name] = value

        if record["seq"] or record["tag"]:
            records.append(record)

    if not records:
        raise RuntimeError(
            "Nenhum equipamento válido foi encontrado. "
            "O dashboard não será esvaziado."
        )

    return records


def update_html(records):
    """Substitui somente o array equipmentData dentro do HTML."""
    if not HTML_PATH.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {HTML_PATH}"
        )

    html = HTML_PATH.read_text(encoding="utf-8")

    equipment_json = json.dumps(
        records,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    new_declaration = f"const equipmentData = {equipment_json};"

    pattern = re.compile(
        r"const\s+equipmentData\s*=\s*\[.*?\];",
        re.DOTALL,
    )

    if not pattern.search(html):
        raise RuntimeError(
            "Não encontrei 'const equipmentData = [...]' no dashboard."
        )

    updated_html = pattern.sub(
        lambda match: new_declaration,
        html,
        count=1,
    )

    if updated_html == html:
        print("A planilha não possui alterações.")
        return False

    HTML_PATH.write_text(updated_html, encoding="utf-8")
    print(f"Dashboard atualizado com {len(records)} equipamentos.")
    return True


def set_github_output(changed):
    output_path = os.environ.get("GITHUB_OUTPUT")

    if output_path:
        with open(output_path, "a", encoding="utf-8") as output_file:
            output_file.write(
                f"changed={'true' if changed else 'false'}\n"
            )


def main():
    client = get_client()
    records = sheet_to_records(client)
    changed = update_html(records)
    set_github_output(changed)


if __name__ == "__main__":
    main()
