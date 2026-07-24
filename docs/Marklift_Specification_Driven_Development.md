# Marklift — Specification-Driven Development Document

**Version:** 1.0  
**Status:** Implementation-aligned baseline specification  
**Product:** Marklift offline Windows PDF-to-Markdown desktop application  
**Runtime target:** Windows 10/11 x64; Python 3.11 during development  
**Source of truth:** Current implementation, `README.md`, `AGENTS.md`, and automated tests

## Executive summary

Marklift is an offline Windows desktop application that converts text PDFs, scanned PDFs, tables, and embedded images into clean Markdown. The implementation prioritizes privacy, predictable local behavior, recoverable file operations, and a focused user experience over cloud features or broad extensibility.

| Executive question | Answer |
|---|---|
| What problem is solved? | Users can turn local PDF content into editable, portable Markdown without uploading documents or managing a separate OCR service. |
| What is implemented? | End-to-end intake, sequential background conversion, OCR fallback, table/image extraction, previews, saving, batch conflict handling, copy-to-clipboard, packaging, and automated tests. |
| What is the strongest product promise? | Works fully offline: files stay on the computer and conversion does not depend on accounts, APIs, telemetry, or network availability. |
| What protects user data? | Validation before parsing, typed errors, cooperative cancellation, staging, atomic writes, conflict preflight, and no-overwrite defaults. |
| What remains before public distribution? | Complete installed-release verification, confirm the target Windows packaging environment, and sign the executable and installer with trusted Authenticode credentials. |

### Leadership decisions encoded in the implementation

- Privacy over convenience: conversion is local-only, with no runtime uploads or update checks.
- Reliability over partial recovery: cancellation and failed publication discard incomplete results rather than exposing misleading output.
- Controlled scope over extensibility: there is no plugin system and the product remains intentionally small.
- User control over automation: existing files are not replaced silently; batch conflicts require one explicit decision.
- Operational transparency over hidden heuristics: OCR use, OCR unavailability, low-confidence tables, and skipped images are surfaced as warnings.

### Business outcomes and success measures

| Outcome | How Marklift creates it | Evidence of success |
|---|---|---|
| Lower document handling friction | One workflow accepts files, folders, and drag-and-drop input. | A user can add a folder and obtain Markdown outputs without manual per-file conversion. |
| Protect sensitive documents | All processing and OCR occur locally; offline tests prohibit socket activity. | Conversion succeeds with networking disabled and no account or upload prompt. |
| Reduce rework from failed conversions | Queue isolation, typed errors, retryable saves, and continued batch processing. | One corrupt file does not stop later files; failed saves remain actionable. |
| Produce usable downstream content | Markdown normalization, GFM tables, relative image links, and read-only rendered preview. | Output is deterministic, structurally readable, and opens with assets intact. |
| Enable controlled Windows distribution | PyInstaller one-folder build and Inno Setup installer bundle the OCR runtime. | Installed `Marklift.exe` launches without a separate Tesseract installation. |

## 1. Product intent and scope

Marklift converts local PDF files into clean Markdown while preserving useful document structure, extracting embedded images when requested, and using bundled English OCR for image-only pages. The application is deliberately offline, single-window, and small.

### In scope

- Add individual PDFs, multiple PDFs, or all PDFs in a selected folder; support local drag and drop.
- Convert queued files sequentially in a background worker while exposing numeric progress and queue states.
- Convert text pages with PyMuPDF and `pymupdf4llm`; use OCR only when enabled and no usable page text exists.
- Detect rectangular tables and append valid GitHub-flavored Markdown tables.
- Extract embedded images into an asset folder with relative Markdown links.
- Preview the first source page and rendered Markdown.
- Save one result, save as another destination, save all results, or copy Markdown to the clipboard.
- Package a one-folder Windows application with bundled English Tesseract and an Inno Setup installer.

### Out of scope and hard constraints

- No runtime networking, uploads, telemetry, accounts, update checks, or cloud conversion.
- No plugin system or features outside the implementation brief.
- No PyMuPDF imports in the UI layer and no Qt imports in the engine layer.
- No partial output after cancellation or failed publication.
- Existing user files are never overwritten without explicit confirmation.

## 2. System map

The runtime is a local pipeline with a strict presentation/conversion boundary.

| Layer | Responsibilities | Primary modules |
|---|---|---|
| UI | Single-window interaction, queue, previews, save/copy actions, accessible status | `src/app/main_window.py`, `strings.py` |
| Worker | Runs one queued job outside the GUI thread; emits progress and completion | `src/app/worker.py` |
| Conversion engine | Validate, open, process pages, normalize, publish Markdown/assets | `src/engine/converter.py`, `models.py` |
| Extraction helpers | OCR fallback, table serialization, embedded image extraction | `src/engine/ocr.py`, `tables.py`, `images.py` |
| Theme and entry point | System light/dark theme, startup, branding | `src/app/theme.py`, `main.py` |
| Release | Bundle OCR runtime, build executable, compile installer | `src/packaging/build.py`, `installer.iss` |

### Primary workflow

1. The user selects or drops local PDF paths.
2. The UI filters folder input to PDFs, ignores duplicates, and captures the current image option in each `QueueJob`.
3. A single worker converts jobs sequentially; page progress updates the queue row.
4. The engine validates the file, converts each requested page, optionally adds tables and images, then atomically publishes the result.
5. The UI receives a complete `ConversionResult`, updates status, renders previews, and exposes save/copy actions only for successful results.
6. Save operations preflight conflicts and protect both Markdown and asset directories; failures remain retryable.

## 3. Functional specifications

### 3.1 Intake and queue

| ID | Requirement | Acceptance criteria |
|---|---|---|
| FR-INT-01 | Accept one or more PDFs or a folder. | Only local `.pdf` inputs enter the queue; non-PDF folder contents are ignored. |
| FR-INT-02 | Reject duplicates deterministically. | Adding the same resolved PDF twice creates one row and shows a duplicate notice. |
| FR-INT-03 | Capture conversion options per job. | Changing **Exclude images** after enqueue does not alter existing jobs. |
| FR-QUE-01 | Expose `Waiting`, `Converting`, `Ready`, `Saved`, `Failed`, and `Cancelled`. | Each row displays one approved state and numeric progress while converting. |
| FR-QUE-02 | Allow cancellation only for waiting or active jobs. | Cancellation is cooperative, checked between pages, and produces no partial output. |
| FR-QUE-03 | Continue after an individual conversion failure. | A failed row does not prevent later rows from completing. |

### 3.2 Conversion engine

| ID | Requirement | Acceptance criteria |
|---|---|---|
| FR-CON-01 | `convert()` never raises for expected conversion failures. | It returns `ConversionResult` with error text for missing, invalid, corrupt, encrypted, or cancelled input. |
| FR-CON-02 | Validate PDF signature before parsing. | Wrong extension or missing `%PDF-` signature maps to approved plain-language error. |
| FR-CON-03 | Process pages sequentially and deterministically. | Page range is one-based and inclusive; output line endings and trailing whitespace are normalized. |
| FR-CON-04 | Use OCR as a page-level fallback. | OCR runs only when enabled and page text is empty; warnings identify use or unavailability. |
| FR-CON-05 | Preserve tables when confidence is sufficient. | Rectangular populated rows become GFM; low-confidence/failed tables remain plain text with a warning. |
| FR-CON-06 | Publish images safely. | Unique embedded images are staged and published under `<stem>_assets` with relative links. |
| FR-CON-07 | Write atomically and protect existing output. | Default writes fail safely when Markdown/assets exist; explicit overwrite replaces as one logical operation. |

### 3.3 Save, preview, and copy

- The first source page is rendered as a read-only thumbnail and scales with the window while preserving aspect ratio.
- The Markdown preview is read-only and is shown for the selected completed result.
- **Save next to PDF** uses the source stem.
- **Save as** adds a `.md` extension when missing and renames asset links to match the destination stem.
- **Save all** performs one conflict preflight and applies one choice: Replace existing, Skip existing, or Cancel.
- Individual batch-save failures do not abort the batch.
- **Copy Markdown** places the selected result on the local clipboard and reports success through the status bar.

## 4. Behavioral scenarios

These scenarios are the executable intent of the specification. Each should remain represented by an automated test or documented release check.

### S-01 — Text PDF

**Given** a valid text PDF, **when** the user converts it, **then** headings, paragraphs, and lists are returned as Markdown, the row becomes Ready, and no network connection is attempted.

### S-02 — Scanned PDF

**Given** an image-only page and available bundled Tesseract, **when** conversion runs with OCR enabled, **then** OCR text is returned, `used_ocr` is true, and the OCR accuracy notice is visible.

### S-03 — Missing OCR runtime

**Given** an image-only page and no resolvable Tesseract binary, **when** conversion runs, **then** the page is skipped safely and the OCR-unavailable warning is returned.

### S-04 — Cancellation

**Given** a multi-page conversion, **when** cancellation is requested between pages, **then** the result is Cancelled and no Markdown or asset directory is left behind.

### S-05 — Existing output

**Given** an existing Markdown file or asset folder, **when** save occurs without overwrite consent, **then** no existing content changes and the failure remains retryable.

### S-06 — Batch save conflict

**Given** multiple Ready jobs with one or more destination conflicts, **when** Save all is selected, **then** one preflight choice is shown before any write.

### S-07 — Offline operation

**Given** the network adapter is disabled, **when** a text or scanned PDF is converted, **then** output behavior is unchanged and no account or upload prompt appears.

## 5. Data contracts and interfaces

### `ConversionOptions`

The engine accepts:

- `include_images` — default `True`.
- `page_range` — one-based inclusive tuple or `None`.
- `ocr_enabled` — default `True`.
- `output_dir` — optional destination directory.
- `overwrite_existing` — default `False`.
- `cancel_event` — cooperative cancellation signal.
- `progress_callback` — callback receiving completed and total page counts.

### `ConversionResult`

Every conversion returns:

- `source`
- `output_path`
- `markdown`
- `used_ocr`
- `warnings`
- `error`
- `pages` — page-level `PageStatus` records

Success is represented by `error=None`. Failure is represented by an empty Markdown payload and a user-facing error message.

### Persistence contract

| Artifact | Location / naming | Guarantee |
|---|---|---|
| Markdown | `<output_dir>/<source_stem>.md` | UTF-8, LF line endings, atomic replacement. |
| Image assets | `<output_dir>/<source_stem>_assets/` | Staged before publication; relative links remain valid. |
| Save As assets | `<destination_stem>_assets/` | Links are rewritten to the destination stem. |
| Preview thumbnail | Temporary per-window directory | Read-only UI preview; cleaned after workers finish on close. |

## 6. Non-functional specifications

| ID | Quality attribute | Specification |
|---|---|---|
| NFR-SEC-01 | Privacy | All PDF data, OCR, previews, and outputs stay local; no runtime network stack. |
| NFR-REL-01 | Reliability | Expected conversion errors are typed, mapped to approved copy, and returned without crashing the UI. |
| NFR-REL-02 | Data safety | Cancellation, conflict detection, atomic Markdown writes, and staged asset publication prevent partial results. |
| NFR-PERF-01 | Responsiveness | Conversion runs outside the GUI thread, one job at a time, with progress callbacks. |
| NFR-PERF-02 | Benchmark | The opt-in 100-page text conversion benchmark reports a warning rather than failing when the target is missed. |
| NFR-A11Y-01 | Accessibility | Primary intake and result actions are keyboard-operable, named, focus-visible, and status text is exposed. |
| NFR-COMP-01 | Compatibility | Development and packaging target Python 3.11 and Windows 10/11 x64. |
| NFR-MAINT-01 | Maintainability | Engine/UI dependency separation and centralized user-facing strings are preserved. |

## 7. Operating model and ownership

| Concern | Accountable role | Operating expectation |
|---|---|---|
| Product scope | Product owner | Keep Marklift focused on local PDF-to-Markdown conversion; approve cloud, plugin, or workflow expansion explicitly. |
| Engine correctness | Engineering owner | Maintain conversion contracts, deterministic output, cancellation semantics, and safe publication tests. |
| Desktop experience | UI owner | Maintain queue clarity, keyboard access, previews, theme behavior, and centralized copy. |
| Release quality | Release owner | Run lint, automated tests, performance check, packaging, installed-release matrix, and offline verification. |
| Distribution trust | Security/release owner | Review dependency licences and complete Authenticode signing before public release. |

## 8. Risk register

| Risk | Impact | Current control | Residual action |
|---|---|---|---|
| OCR accuracy varies by scan quality | Incorrect or incomplete Markdown text | OCR notice is shown; OCR is page-level and locally configurable. | Define a sample-document acceptance set and communicate that OCR may require review. |
| Complex PDF layouts convert imperfectly | Tables, columns, or visual structure may need cleanup | `pymupdf4llm` handles text structure; low-confidence tables remain plain text. | Expand representative fixtures before making a public quality claim. |
| Large PDFs consume time and memory | Long waits or reduced desktop responsiveness | Conversion is sequential and off the GUI thread; performance benchmark exists. | Measure representative workloads and publish practical size/page guidance. |
| Unsigned Windows binaries trigger SmartScreen warnings | Installation friction and reduced trust | Signing is identified as a release gate. | Sign executable and installer with a trusted certificate. |
| Native dependency drift | Build or runtime failure on release machines | Pinned versions and packaging validation check executable, OCR data, and icon. | Rebuild in a clean environment and retain release evidence. |
| User selects overwrite unexpectedly | Loss of prior Markdown/assets | No-overwrite defaults and one batch conflict decision. | Retain installed-release checks for single and batch conflict flows. |

## 9. Verification strategy

Verification is layered so engine guarantees can be tested headlessly and desktop behavior can be tested through Qt smoke tests and release checks.

| Layer | Command / evidence | Exit criterion |
|---|---|---|
| Static quality | `ruff check .` | No lint or import-order violations. |
| Automated regression | `pytest -q` | All non-performance tests pass. |
| Performance | `pytest -q -m performance` | Benchmark completes; target miss is reported as a warning. |
| Source UI smoke | Tests in `tests/test_ui.py` | Window launches, queue continues after failure, save/copy/conflict flows work. |
| Offline assurance | `tests/test_offline.py` | Socket calls are blocked in test and source tree has no network-library imports. |
| Packaging | `python src/packaging/build.py`; `ISCC.exe src/packaging/installer.iss` | `Marklift.exe`, bundled Tesseract, icon, and installer are present. |
| Installed release | Manual matrix in `README.md` | Installed app passes launch, text, scan, corrupt, folder, duplicate, batch, keyboard, and offline checks. |

### Current test coverage map

- Converter behavior: text, headings, lists, page ranges, cancellation, and determinism.
- Error behavior: wrong extension/signature, zero-byte, encrypted, truncated, missing file, and output conflict.
- OCR: fallback, 300 DPI rasterization, unavailable runtime, and disabled OCR.
- Tables and images: GFM escaping, confidence handling, relative links, skip/overwrite safety.
- UI: queue lifecycle, folder filtering, duplicate handling, option capture, responsive preview, batch save, clipboard, brand, and icon.

## 10. Recommended implementation-to-release sequence

1. **Baseline:** Keep the specification, implementation, and automated suite aligned.
2. **Evidence:** Run lint, standard tests, offline checks, and the opt-in performance test; record results with the build.
3. **Packaging:** Build the one-folder application, verify bundled OCR files and icon, then compile the installer.
4. **Acceptance:** Install on a clean Windows 10/11 x64 environment and execute the release matrix from `README.md`.
5. **Trust:** Review licences, sign `Marklift.exe` and the installer, and repeat launch/offline checks against signed artifacts.
6. **Release decision:** Approve only when no critical data-loss, offline, launch, or conversion-regression issue remains open.

## 11. Release gates

- `AGENTS.md` requirements remain satisfied.
- No generated `build`, `dist`, or `vendor` artifacts are committed.
- `ruff check .` and `pytest -q` pass from `pdf2md`.
- The Windows build stages only the Tesseract executable, required DLLs, and `eng.traineddata`.
- The installed application launches without a console, includes the Marklift icon, and remains offline during conversion.
- The code-signing TODO is resolved before public distribution: sign both `Marklift.exe` and the final installer with trusted Authenticode credentials.

## 12. Traceability to implementation

| Specification area | Implementation evidence |
|---|---|
| Engine contract | `src/engine/models.py`, `converter.py`, `errors.py` |
| OCR and extraction | `src/engine/ocr.py`, `tables.py`, `images.py` |
| Queue and UI behavior | `src/app/main_window.py`, `worker.py`, `strings.py` |
| Theme and branding | `src/app/theme.py`, `src/app/assets`, `main.py` |
| Packaging | `src/packaging/build.py`, `installer.iss` |
| Automated verification | `tests/test_converter.py`, `test_errors.py`, `test_ocr.py`, `test_offline.py`, `test_tables.py`, `test_ui.py`, `test_performance.py` |

## 13. Change-control rules

- Any change to `engine.convert()`, `ConversionResult`, or `save_conversion_result()` must preserve backward compatibility or update this specification and dependent tests in the same change.
- Any new user-visible copy belongs in `src/app/strings.py` and must be covered by a behavior or UI test.
- Any new network, account, telemetry, update, or plugin behavior is a scope change requiring an explicit product decision.
- Any output-writing change must include a failure-path test proving existing Markdown/assets are not partially overwritten.
- Any UI workflow change must preserve keyboard operation, visible focus, accessible names, and the queue state model.

> **Definition of done:** A Marklift change is complete when the relevant specification is updated, the implementation and tests agree, lint and tests pass, and the installed-release checks remain true for the affected workflow.
