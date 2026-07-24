"""Extraction of embedded PDF images."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app import strings


def extract_page_images(
    document: Any,
    page: Any,
    page_number: int,
    staging_dir: Path,
    link_directory: str,
) -> tuple[list[str], list[Path], list[str]]:
    """Extract unique embedded images and return relative Markdown links."""

    links: list[str] = []
    files: list[Path] = []
    warnings: list[str] = []
    seen_xrefs: set[int] = set()
    skipped_warning = strings.WARNING_IMAGE_SKIPPED.format(page=page_number)

    try:
        image_infos = page.get_images(full=True)
    except Exception:
        return [], [], [skipped_warning]

    for image_number, image_info in enumerate(image_infos, start=1):
        try:
            xref = int(image_info[0])
        except (IndexError, TypeError, ValueError):
            if skipped_warning not in warnings:
                warnings.append(skipped_warning)
            continue
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)

        try:
            image = document.extract_image(xref)
            image_bytes = image["image"]
            if not isinstance(image_bytes, bytes):
                raise TypeError
        except Exception:
            if skipped_warning not in warnings:
                warnings.append(skipped_warning)
            continue

        extension = re.sub(r"[^a-z0-9]", "", str(image.get("ext", "png")).lower())
        extension = extension or "bin"
        filename = f"page-{page_number:04d}-image-{image_number:02d}.{extension}"
        destination = staging_dir / filename
        destination.write_bytes(image_bytes)
        alt_text = strings.IMAGE_ALT_TEXT.format(page=page_number)
        links.append(f"![{alt_text}]({link_directory}/{filename})")
        files.append(destination)

    return links, files, warnings
