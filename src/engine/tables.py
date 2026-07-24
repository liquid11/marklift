"""Conversion of detected PDF tables to GitHub-flavored Markdown."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app import strings


@dataclass(slots=True)
class PageTables:
    markdown: list[str]
    warnings: list[str]


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip().replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def table_to_gfm(rows: list[list[object]]) -> str | None:
    """Serialize rectangular, sufficiently populated rows as a GFM table."""

    if len(rows) < 2:
        return None

    width = len(rows[0])
    if width < 2 or any(len(row) != width for row in rows):
        return None

    cells = [[_cell_text(value) for value in row] for row in rows]
    non_empty = sum(bool(cell) for row in cells for cell in row)
    if non_empty / (len(cells) * width) < 0.5:
        return None

    header = f"| {' | '.join(cells[0])} |"
    separator = f"| {' | '.join('---' for _ in range(width))} |"
    body = [f"| {' | '.join(row)} |" for row in cells[1:]]
    return "\n".join([header, separator, *body])


def extract_page_tables(page: Any, page_number: int) -> PageTables:
    """Detect tables on a PyMuPDF page without exposing PyMuPDF to the UI."""

    markdown: list[str] = []
    warnings: list[str] = []

    try:
        detected = page.find_tables()
    except Exception:
        return PageTables(markdown=[], warnings=[])

    low_confidence_warning = strings.WARNING_LOW_CONFIDENCE_TABLE.format(page=page_number)
    for table in detected.tables:
        try:
            table_markdown = table_to_gfm(table.extract())
        except Exception:
            table_markdown = None
        if table_markdown is None:
            if low_confidence_warning not in warnings:
                warnings.append(low_confidence_warning)
        else:
            markdown.append(table_markdown)
    return PageTables(markdown=markdown, warnings=warnings)
