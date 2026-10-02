import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json,tempfile
from pathlib import Path
import media_mapping
with tempfile.TemporaryDirectory() as td:
    media_mapping.P=Path(td)/"media_map.json"
    media_mapping.P.write_text(json.dumps({"lessons":{"1408736/1408782":{"media":[
        {"url":"https://bg.izzi.digital/test.mp4","strict":True},
        {"url":"https://bg.izzi.digital/old.mp4","strict":False}
    ]}}}),encoding="utf-8")
    rows=media_mapping.lesson_media("1408736","1408782")
    assert len(rows)==1 and isinstance(rows[0],dict)
    urls=[x.get("url") for x in rows if isinstance(x,dict) and x.get("url")]
    assert urls==["https://bg.izzi.digital/test.mp4"]
print("PASS: media_mapping/server contract is compatible.")
