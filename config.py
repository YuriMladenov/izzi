from pathlib import Path
ROOT=Path(__file__).resolve().parent
ARCHIVE_DIR=ROOT/"archive"
STATE_DIR=ROOT/"state"
CAPTURES_DIR=ROOT/"captures"
URL_MAP_FILE=STATE_DIR/"url_map.json"
BOOKS_FILE=STATE_DIR/"books.json"
IMPORTS_FILE=STATE_DIR/"imports.json"
PROGRESS_DIR=STATE_DIR/"progress"
SOURCE_HOST="bg.izzi.digital"
HOST="127.0.0.1"
PORT=8765

CAPTURE_PROXY_PORT=8877
