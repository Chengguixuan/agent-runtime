import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List


@dataclass
class SessionData:
    session_id: str
    messages: List[Dict] = field(default_factory=list)
    todo_list: List[str] = field(default_factory=list)
    turn_count: int = 0
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SessionData":
        return cls(**data)


class SessionManager:
    def __init__(self, storage_file: str = "sessions.json"):
        self.storage_file = storage_file
        self._sessions: Dict[str, SessionData] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.storage_file):
            with open(self.storage_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self._sessions = {
                sid: SessionData.from_dict(data)
                for sid, data in raw.items()
            }
        else:
            self._sessions = {}

    def get_or_create(self, session_id: str) -> SessionData:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionData(session_id=session_id)
        return self._sessions[session_id]

    def save_all(self):
        data = {
            sid: session.to_dict()
            for sid, session in self._sessions.items()
        }
        with open(self.storage_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_all_sessions(self) -> List[str]:
        return list(self._sessions.keys())
