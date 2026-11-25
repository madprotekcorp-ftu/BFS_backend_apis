import csv

from django.http import StreamingHttpResponse
from django.utils.http import content_disposition_header

# Cells starting with these can be run as formulas by Excel (CSV injection).
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    if value is None:
        return ""
    text = str(value)
    if text and text[0] in _FORMULA_PREFIXES:
        return "'" + text
    return text


class _Echo:
    def write(self, value):
        return value


def csv_download(filename, header, rows):
    """Stream a UTF-8 CSV with BOM (so Excel opens it cleanly); every cell is escaped."""
    writer = csv.writer(_Echo())

    def stream():
        yield "﻿"
        yield writer.writerow([safe_cell(c) for c in header])
        for row in rows:
            yield writer.writerow([safe_cell(c) for c in row])

    response = StreamingHttpResponse(stream(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = content_disposition_header(True, filename)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
