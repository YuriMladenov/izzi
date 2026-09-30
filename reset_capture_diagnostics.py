from pathlib import Path
from config import STATE_DIR
for name in ("capture_observed.json","capture_session.json","active_lesson.json"):
    p=STATE_DIR/name
    if p.exists():
        p.unlink()
        print("Removed",p)
print("Archive and media_map were preserved.")
