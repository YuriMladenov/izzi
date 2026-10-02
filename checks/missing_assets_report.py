import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from readiness import assess
from config import ROOT

def main():
    report=assess(ROOT)
    for error in report["errors"]:print("STATE ERROR",error)
    missing=set();warnings=set()
    for book in report["books"]:
        missing.update(book["gaps"]);missing.update(book["missing_lessons"]);missing.update(book["incomplete_media"])
        warnings.update(book["warnings"])
    for url in sorted(missing):print("MISSING",url)
    for url in sorted(warnings):print("UPSTREAM 404 WARNING",url)
    print("Missing known resources:",len(missing))
    print("Upstream 404 warnings:",len(warnings))
    if not report["books"]:print("No books found; no completeness established.")
    return int(bool(missing or report["errors"] or not report["books"]))

if __name__=="__main__":raise SystemExit(main())
