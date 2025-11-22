import json
from pathlib import Path
from typing import Any, Dict


class Persistence:
    def __init__(self, path: str = "zfeiq_state.json"):
        self.path = Path(path)
        if not self.path.exists():
            self._write({})

    def _write(self, data: Dict[str, Any]):
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def read(self) -> Dict[str, Any]:
        return json.loads(self.path.read_text())

    def write(self, data: Dict[str, Any]) -> None:
        self._write(data)
