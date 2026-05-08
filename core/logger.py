import json
import os
import time
from datetime import datetime, timezone


class RunLogger:
    def __init__(self):
        os.makedirs("runs", exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        self._path = f"runs/{ts}.json"
        self._entries = []
        self._start = time.perf_counter()

    def log(self, agent: str, event: str, data: dict):
        self._entries.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "event": event,
            "data": data,
        })

    def finalize(self, summary: dict):
        summary["wall_time_seconds"] = round(time.perf_counter() - self._start, 2)
        with open(self._path, "w") as f:
            json.dump({"summary": summary, "events": self._entries}, f, indent=2)
        print(f"[RunLogger] Log written → {self._path}")
