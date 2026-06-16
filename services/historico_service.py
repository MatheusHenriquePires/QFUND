import json
import time
from pathlib import Path
import uuid


class HistoricoService:

    def __init__(self):
        self._path = Path(__file__).resolve().parent.parent / "generated" / "history.json"
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        self._data = []
        self._load()

    def _load(self):
        try:
            if self._path.exists():
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            else:
                self._data = []
        except Exception:
            self._data = []

    def _save(self):
        try:
            self._path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


    def add_record(self, tipo: str, arquivo: str, meta: dict, responsavel: str | None = None):
        rec = {
            "id": str(uuid.uuid4()),
            "tipo": tipo or "default",
            "responsavel": responsavel,
            "arquivo": arquivo,
            "meta": meta or {},
            "ts": int(time.time())
        }

        # prepend para ordem decrescente
        self._data.insert(0, rec)
        self._save()
        return rec

    def list(self, tipo: str | None = None, responsavel: str | None = None):
        if not tipo and not responsavel:
            return self._data

        if tipo and responsavel:
            return [r for r in self._data if r.get("tipo") == tipo and r.get("responsavel") == responsavel]

        if tipo:
            return [r for r in self._data if r.get("tipo") == tipo]

        return [r for r in self._data if r.get("responsavel") == responsavel]

    def get(self, arquivo: str):
        for r in self._data:
            if r.get("arquivo") == arquivo:
                return r
        return None
