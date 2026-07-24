"""Runtime offline guarantee tests."""

from __future__ import annotations

import ast
import socket
from pathlib import Path

import pymupdf

from engine import ConversionOptions, convert


def _offline_fixture(path: Path) -> Path:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Offline conversion works")
    document.save(path)
    document.close()
    return path


def test_full_conversion_never_opens_a_socket(monkeypatch, tmp_path: Path) -> None:
    source = _offline_fixture(tmp_path / "offline.pdf")

    def network_is_forbidden(*args, **kwargs):
        raise AssertionError("Conversion attempted to create a network socket")

    monkeypatch.setattr(socket, "socket", network_is_forbidden)

    result = convert(
        source,
        ConversionOptions(
            include_images=False,
            ocr_enabled=False,
            output_dir=tmp_path / "out",
        ),
    )

    assert result.error is None
    assert "Offline conversion works" in result.markdown


def test_source_tree_has_no_network_library_imports() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src"
    forbidden = {"requests", "urllib", "http", "socket"}
    violations: list[str] = []

    for source_file in source_root.rglob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.split(".", maxsplit=1)[0] in forbidden:
                    violations.append(f"{source_file.relative_to(source_root)} imports {name}")

    assert violations == []


def test_engine_and_ui_dependency_boundary() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src"
    violations: list[str] = []

    for area, forbidden in (("engine", {"PySide6"}), ("app", {"pymupdf", "pymupdf4llm"})):
        for source_file in (source_root / area).rglob("*.py"):
            tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if name.split(".", maxsplit=1)[0] in forbidden:
                        violations.append(f"{source_file.name} imports {name}")

    assert violations == []
