"""Create deterministic PDFs for packaged-application release testing."""

from __future__ import annotations

import argparse
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont


def create_fixtures(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Marklift packaged E2E verification", fontsize=18)
    page.insert_text((72, 110), "This text must appear in the Markdown output.")
    page.insert_text((72, 140), "First bullet")
    page.insert_text((72, 165), "Second bullet")
    document.save(output_dir / "release-text.pdf")
    document.close()

    image = Image.new("RGB", (1600, 900), "white")
    drawing = ImageDraw.Draw(image)
    font = ImageFont.truetype("arial.ttf", 64)
    drawing.text((120, 180), "MARKLIFT OCR E2E 101", fill="black", font=font)
    drawing.text(
        (120, 280),
        "Offline scanned page verification",
        fill="black",
        font=font,
    )
    image_path = output_dir / "scan-source.png"
    image.save(image_path)

    document = pymupdf.open()
    page = document.new_page(width=800, height=450)
    page.insert_image(page.rect, filename=str(image_path))
    document.save(output_dir / "release-scan.pdf")
    document.close()
    image_path.unlink()

    (output_dir / "corrupt.pdf").write_bytes(b"%PDF-corrupt-release-fixture")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    arguments = parser.parse_args()
    create_fixtures(arguments.output_dir)
    for path in sorted(arguments.output_dir.iterdir()):
        print(f"{path.name}: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
