"""Read an uploaded CSV/XLSX into (headers, rows). No validation of values here."""

import csv
import io
import re
from datetime import date, datetime

import openpyxl


class ImportFileError(Exception):
    pass


def normalize_header(value):
    """Case-insensitive, trimmed; inner spaces become underscores ("Customer Name" -> customer_name)."""
    return re.sub(r"\s+", "_", str(value or "").strip().lower())


def cell_to_text(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))  # Excel stores mobiles as numbers
    text = str(value).strip()
    # Undo the CSV-injection escape our own exports/templates add ("'+91..." -> "+91..."),
    # so files we produce can be re-imported.
    if len(text) > 1 and text[0] == "'" and text[1] in "=+-@":
        text = text[1:]
    return text


def _iter_csv(uploaded_file):
    raw = uploaded_file.read()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ImportFileError("Could not read the CSV file. Save it as UTF-8 and try again.")
    try:
        yield from csv.reader(io.StringIO(text, newline=""))
    except csv.Error:
        raise ImportFileError("The CSV file is not formatted correctly.")


def _iter_xlsx(uploaded_file):
    try:
        workbook = openpyxl.load_workbook(uploaded_file, read_only=True, data_only=True)
    except Exception:
        raise ImportFileError("Could not read the Excel file. Save it as .xlsx and try again.")
    try:
        sheet = workbook.worksheets[0]
        for row in sheet.iter_rows(values_only=True):
            yield list(row)
    finally:
        workbook.close()


def read_rows(uploaded_file, extension, max_rows):
    """Return (headers, [(row_number, {header: text})]). Blank rows are skipped."""
    iterator = _iter_csv(uploaded_file) if extension == ".csv" else _iter_xlsx(uploaded_file)

    headers = None
    rows = []
    for index, raw_row in enumerate(iterator, start=1):
        cells = [cell_to_text(v) for v in raw_row]
        if headers is None:
            if not any(cells):
                continue  # leading blank lines before the header
            headers = [normalize_header(c) for c in cells]
            continue
        if not any(cells):
            continue
        if len(rows) >= max_rows:
            raise ImportFileError(f"The file has more than {max_rows} data rows. Split it into smaller files.")
        record = {}
        for position, header in enumerate(headers):
            if header and header not in record:
                record[header] = cells[position] if position < len(cells) else ""
        rows.append((index, record))

    if headers is None:
        raise ImportFileError("The file is empty.")
    return [h for h in headers if h], rows
