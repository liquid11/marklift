"""All user-facing application and conversion text.

Keeping copy in one dependency-light module lets the engine return the exact
same plain-language messages that the desktop UI displays.
"""

APP_NAME = "Marklift"
APP_TITLE = "Marklift"
APP_SUBTITLE = "Lift PDFs into clean Markdown — entirely on this computer."
OFFLINE_BADGE = "● Works fully offline"

DROP_ZONE = "Drop PDF files or a folder here\nor choose an option below"
ADD_PDFS = "Add PDFs"
ADD_FOLDER = "Add folder"
OPEN_FILES = ADD_PDFS
OPEN_DIALOG_TITLE = "Choose PDF files"
FOLDER_DIALOG_TITLE = "Choose a folder containing PDFs"
PDF_FILE_FILTER = "PDF files (*.pdf)"
SKIP_IMAGES = "Exclude images"
SKIP_IMAGES_HELP = "Creates smaller Markdown exports without extracted image files."
QUEUE_TITLE = "Conversion queue"
QUEUE_SUMMARY_EMPTY = "No files"
QUEUE_SUMMARY = "{completed} of {total} completed"
QUEUE_EMPTY_TITLE = "No PDFs in the queue"
QUEUE_EMPTY_HELP = "Add individual PDF files or choose a folder to begin."
QUEUE_FILE = "File"
QUEUE_STATUS = "Status"
QUEUE_ACTION = "Action"
STATUS_WAITING = "Waiting"
STATUS_CONVERTING = "Converting {percent}%"
STATUS_DONE = "Ready"
STATUS_SAVED = "Saved"
STATUS_SAVE_FAILED = "Save failed — retry"
STATUS_FAILED = "Failed: {message}"
STATUS_CANCELLED = "Cancelled"
STATUS_CANCELLING = "Cancelling"
CANCEL = "Cancel"
SOURCE_PREVIEW = "Source page"
MARKDOWN_PREVIEW = "Markdown preview"
NO_FILE_SELECTED = "No file selected"
NO_SOURCE_PREVIEW = "No source page selected"
NO_MARKDOWN_PREVIEW = "Converted Markdown will appear here"
SAVE = "Save next to PDF"
SAVE_AS = "Save as…"
COPY = "Copy Markdown"
SAVE_ALL = "Save all"
SAVE_ALL_COUNT = "Save all ({count})"
MARKDOWN_FILE_FILTER = "Markdown files (*.md)"
SAVE_AS_TITLE = "Save Markdown as"
OVERWRITE_TITLE = "Replace existing file?"
OVERWRITE_MESSAGE = "Existing output for {filename} was found. Do you want to replace it?"
REPLACE_EXISTING = "Replace existing"
SKIP_EXISTING = "Skip existing"
BATCH_CONFLICT_TITLE = "Existing output files found"
BATCH_CONFLICT_MESSAGE = (
    "{count} completed PDF(s) already have Markdown output or an asset folder:\n\n"
    "{filenames}\n\nChoose whether to replace or skip those existing outputs."
)
SAVE_FAILED_TITLE = "Couldn't save the file"
SAVE_FAILED_MESSAGE = "The Markdown file couldn't be saved. Choose another location and try again."
SAVE_SUCCESS = "Saved Markdown to {destination}"
COPY_SUCCESS = "Markdown copied to the clipboard."
BATCH_SAVE_SUMMARY = "Batch save finished: {saved} saved, {skipped} skipped, {failed} failed."
NO_PDFS_FOUND = "No PDF files were found."
FILES_ADDED = "Added {count} PDF file(s) to the queue."
DUPLICATES_SKIPPED = "{count} duplicate PDF file(s) were already in the queue."
STATUSBAR_READY = "Ready"
ERROR_INVALID_DESTINATION = "The Markdown output can't replace the source PDF."
OFFLINE_TRUST = "Works fully offline — your files never leave this computer."
ACCESSIBLE_QUEUE = "PDF conversion queue"
ACCESSIBLE_DROP_ZONE = "Drop PDF files or activate to choose PDF files"
ACCESSIBLE_SOURCE_PREVIEW = "Preview of the first source PDF page"
ACCESSIBLE_MARKDOWN_PREVIEW = "Rendered Markdown preview"
ACCESSIBLE_WARNINGS = "Conversion warnings"

ERROR_ENCRYPTED = "This PDF is password-protected and can't be converted."
ERROR_CORRUPT = "This file appears to be damaged and can't be read."
ERROR_NOT_PDF = "This file isn't a PDF. Please choose a .pdf file."
ERROR_CANCELLED = "Conversion was cancelled."
ERROR_PAGE_RANGE = "The selected page range isn't valid for this PDF."
ERROR_OUTPUT_EXISTS = (
    "A Markdown file with this name already exists. Choose another location "
    "or allow replacement."
)
ERROR_UNKNOWN = "This PDF couldn't be converted."

NOTICE_OCR_USED = (
    "This looked like a scanned document, so text was read using OCR — accuracy may vary."
)
WARNING_OCR_UNAVAILABLE = "OCR isn't available on this computer, so scanned pages were skipped."
WARNING_LOW_CONFIDENCE_TABLE = (
    "Table on page {page} had low confidence and was left as plain text."
)
WARNING_IMAGE_SKIPPED = (
    "One or more images on page {page} couldn't be extracted and were skipped."
)
IMAGE_ALT_TEXT = "Image from page {page}"
