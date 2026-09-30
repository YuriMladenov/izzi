from config import STATE_DIR
p=STATE_DIR/"missing_resources.jsonl"
if p.exists():p.unlink();print("Missing-resource report cleared.")
else:print("No missing-resource report yet.")
