"""Release packaging configuration tests."""

from __future__ import annotations

import runpy
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGING = runpy.run_path(PROJECT_ROOT / "src" / "packaging" / "build.py")


def test_release_versions_and_required_assets_are_synchronized() -> None:
    version = PACKAGING["project_version"]()

    assert PACKAGING["validate_configuration"]() == version


def test_generated_windows_version_info_matches_project_version() -> None:
    version = PACKAGING["project_version"]()
    version_file = PACKAGING["write_version_info"](version)
    contents = version_file.read_text(encoding="utf-8")

    assert f"StringStruct('FileVersion', '{version}')" in contents
    assert f"StringStruct('ProductVersion', '{version}')" in contents
    assert "StringStruct('OriginalFilename', 'Marklift.exe')" in contents
