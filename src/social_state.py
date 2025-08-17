"""
social_state.py — простое in-memory состояние для социальных интентов.
"""
from dataclasses import dataclass, field
from typing import Dict
import time

DEFAULT_TTL_SEC = 12 * 60 * 60  # 12 часов


@dataclass
class SessionSocialState:
    greeting_exchanged: bool = False
    farewell_pending: bool = False
    last_social_at: float = field(default_factory=lambda: 0.0)


class SocialStateManager:
    def __init__(self, ttl_sec: int = DEFAULT_TTL_SEC):
        self._store: Dict[str, SessionSocialState] = {}
        self._expires: Dict[str, float] = {}
        self._ttl = ttl_sec

    def _now(self) -> float:
        return time.time()

    def _ensure(self, session_id: str) -> SessionSocialState:
        now = self._now()
        exp = self._expires.get(session_id, 0)
        if session_id not in self._store or now > exp:
            self._store[session_id] = SessionSocialState()
        self._expires[session_id] = now + self._ttl
        return self._store[session_id]

    def get(self, session_id: str) -> SessionSocialState:
        return self._ensure(session_id)

    def has_greeted(self, session_id: str) -> bool:
        """Проверяет, было ли уже приветствие в этой сессии"""
        st = self._ensure(session_id)
        return st.greeting_exchanged
    
    def mark_greeted(self, session_id: str):
        """Отмечает, что приветствие произошло (alias для mark_greeting)"""
        self.mark_greeting(session_id)
    
    def mark_greeting(self, session_id: str):
        st = self._ensure(session_id)
        st.greeting_exchanged = True
        st.last_social_at = self._now()

    def mark_farewell(self, session_id: str):
        st = self._ensure(session_id)
        st.farewell_pending = True
        st.last_social_at = self._now()

    def reset_farewell(self, session_id: str):
        st = self._ensure(session_id)
        st.farewell_pending = False
