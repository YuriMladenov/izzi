import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
from config import PROGRESS_DIR
from progress_journal import summarize

def main():
    report=summarize(PROGRESS_DIR)
    print('Local request journal — no server-side progress emulation')
    for book in report['books']:
        print('BOOK',book['book'],'records=',book['records'],'invalid_lines=',book['invalid_lines'],
              'legacy_records=',book['legacy_records'],'bytes=',book['bytes'])
        for endpoint,count in book['endpoints'].items():print(' ',count,endpoint)
    print('Total valid records:',report['records'])
    print('Invalid lines:',report['invalid_lines'])
    return int(bool(report['invalid_lines']))

if __name__=='__main__':raise SystemExit(main())
