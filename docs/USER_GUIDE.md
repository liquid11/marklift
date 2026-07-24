# Marklift User Guide

Marklift converts local PDF files into Markdown on your Windows computer. This
guide explains the complete user workflow and what to expect from the output.

## Contents

- [Before you start](#before-you-start)
- [Install Marklift](#1-install-marklift)
- [Add PDFs to the queue](#2-add-pdfs-to-the-queue)
- [Follow conversion progress](#3-follow-conversion-progress)
- [Review the result](#4-review-the-result)
- [Save or copy Markdown](#5-save-or-copy-markdown)
- [Understand OCR results](#6-understand-ocr-results)
- [Troubleshooting](#7-troubleshooting)
- [Privacy and safety](#8-privacy-and-safety)
- [Keyboard and accessibility](#9-keyboard-and-accessibility-use)

## Before you start

Marklift is intentionally simple: add local PDFs, review the result, then save
or copy the Markdown. It does not require an account or an internet connection.

For the best results, use a readable PDF and keep the Markdown file together
with its optional asset folder when extracted images are included.

![Marklift desktop interface](images/marklift-main-window.jpg)

The main window is organized around four areas: PDF intake, the conversion
queue, a source-page preview, and a rendered Markdown preview.

## 1. Install Marklift

Download the latest `Marklift-Setup-*.exe` installer from the repository's
GitHub Releases page and run it. The installer creates a Start Menu entry and
installs the application under `C:\Program Files\Marklift` by default.

The packaged application includes its English OCR runtime. End users do not
need to install Python, Tesseract, or any other separate tool.

> If you are testing the project from source, follow the developer setup in the
> [README](../README.md).

## 2. Add PDFs to the queue

When Marklift opens, use any of these intake methods:

- Select **Add PDFs** to choose one or more files.
- Select **Add folder** to add all PDFs in a folder.
- Drag PDFs or a folder onto the intake area.

Non-PDF files inside a selected folder are ignored. Adding the same PDF twice
does not create a duplicate queue item. A folder without PDFs produces a
message and leaves the current queue unchanged.

### Image handling

By default, Marklift attempts to extract embedded images and writes them beside
the Markdown file. Select **Exclude images** before adding a file when you want
a smaller text-focused export. The choice is captured when a file enters the
queue, so changing it later does not change jobs already queued.

## 3. Follow conversion progress

Marklift processes queued PDFs one at a time in the background. Each row can
show:

| Status | Meaning |
| --- | --- |
| Waiting | The PDF is queued but has not started. |
| Converting | The PDF is being processed and progress is shown. |
| Ready | Conversion finished and the result can be previewed or saved. |
| Saved | The Markdown result was written successfully. |
| Failed | The PDF could not be converted or the result could not be saved. |
| Cancelled | Processing was stopped and incomplete output was discarded. |

A failed file does not prevent later files in the queue from being processed.

### Recommended first run

For a quick confidence check, add one text-based PDF first. Confirm that the
preview looks right, then save it beside the source PDF. After that, add a
folder for batch conversion.

## 4. Review the result

Select a completed queue row to show two previews:

- **Source page** shows the first page of the original PDF.
- **Markdown preview** shows the converted document in a readable format.

The Markdown preview is read-only. Warnings appear below the previews when
Marklift used OCR, skipped an image, or could not confidently structure a
table.

Treat the preview as a review step, especially for scans, complex layouts, and
documents that will be used for high-consequence decisions.

## 5. Save or copy Markdown

Use the action buttons below the previews:

### Save next to PDF

For `report.pdf`, Marklift creates `report.md` beside the source PDF. If images
are included, they are placed in `report_assets` and referenced using relative
links.

### Save as…

Choose a different folder or filename. Marklift adds the `.md` extension when
needed and keeps extracted-image links relative to the chosen destination.

### Copy Markdown

Copies the selected result to the Windows clipboard. No file is created.

### Save all

Saves every completed result in the queue using its source location and name.
If one or more outputs already exist, Marklift shows a single preflight dialog
before writing anything. Choose one of:

- **Replace existing** — replace conflicting Markdown and asset output.
- **Skip existing** — leave conflicting output unchanged.
- **Cancel** — do not start the batch save.

Individual save failures are reported in the final batch summary.

### Suggested output practice

Keep each Markdown file beside its source PDF unless you have a reason to use a
separate output folder. When images are included, move the `.md` file and its
matching `_assets` folder together.

## 6. Understand OCR results

Marklift uses OCR when a page contains no usable text and OCR is available. OCR
is useful for scans and image-only PDFs, but its accuracy can vary with scan
quality, skew, handwriting, unusual fonts, and document layout.

When OCR was used, Marklift shows this notice:

> This looked like a scanned document, so text was read using OCR — accuracy
> may vary.

Review OCR output before relying on it for legal, financial, medical, or other
high-consequence work. The bundled runtime supports English OCR.

## 7. Troubleshooting

### The PDF is reported as damaged

Open the PDF in another reader to confirm that it is complete. Re-download or
re-export the source if necessary. Marklift isolates the failure so other
queued files can continue.

### The PDF is password-protected

Marklift does not convert password-protected PDFs. Open the document using its
password and export an unlocked copy if you are authorized to do so.

### Scanned pages contain no text

Confirm that the packaged application includes OCR, then try a clearer scan.
Low-resolution, rotated, compressed, handwritten, or non-English pages may
produce incomplete results. If OCR is unavailable, Marklift reports that the
scanned pages were skipped rather than creating misleading text.

### Existing output was not replaced

This is intentional. Marklift protects existing Markdown files and asset
folders. Use **Save as…** for a new destination, or explicitly choose
**Replace existing** when the conflict dialog is shown.

### The output looks different from the PDF

PDFs store layout rather than a semantic document structure. Complex columns,
decorative typography, unusual tables, and scans may need manual cleanup after
conversion. Use the preview and warnings to identify sections that need review.

## 8. Privacy and safety

Marklift is designed for offline use:

- PDFs, extracted text, OCR data, previews, and outputs remain on the local
  computer.
- The application does not require an account or upload documents.
- There are no runtime telemetry calls, update checks, or cloud conversion
  requests.
- Cancellation and failed saves discard incomplete output.
- Existing output is not silently overwritten.

Your operating system, antivirus software, backup tools, or other applications
may still access files according to their own settings; Marklift does not
control those services.

## 8.1 What Marklift does not do

Marklift does not provide cloud synchronization, collaborative editing,
automatic backups, password recovery, translation, or guaranteed semantic
reconstruction of complex PDF layouts. Those boundaries are deliberate: the
application focuses on dependable local conversion.

## 9. Keyboard and accessibility use

The intake area and primary actions can be reached using the keyboard. Use Tab
to move through controls and Enter or Space to activate the focused control.
Focus indicators and status text communicate the current action and result.

## 10. Developer and release references

Developers should use the root [README](../README.md) for source setup, tests,
packaging, and release verification. The implementation-aligned behavior is
documented in the [specification](Marklift_Specification_Driven_Development.md).
