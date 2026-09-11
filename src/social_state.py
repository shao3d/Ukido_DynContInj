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
    # Последний уверенно определённый язык пользователя (ru/uk/en).
    # None = язык сессии ещё не установлен (пока не было уверенных реплик).
    # Нужен, чтобы неоднозначные реплики (эмодзи, "ok") не переключали язык диалога.
    language: str = None


class SocialStateManager:
    def __init__(self, ttl_sec: int = DEFAULT_TTL_SEC, max_sessions: int = 20000):
        self._store: Dict[str, SessionSocialState] = {}
        self._expires: Dict[str, float] = {}
        self._ttl = ttl_sec
        # SEC-05: ротация id не должна раздувать память — держим потолок и
        # вычищаем истёкшие сессии, которые больше не трогают.
        self._max_sessions = max_sessions

    def _now(self) -> float:
        return time.time()

    def _sweep(self, now: float) -> None:
        if len(self._store) <= self._max_sessions:
            return
        expired = [sid for sid, exp in self._expires.items() if now > exp]
        for sid in expired:
            self._store.pop(sid, None)
            self._expires.pop(sid, None)
        if len(self._store) > self._max_sessions:
            oldest = sorted(self._expires, key=self._expires.get)
            for sid in oldest[: len(self._store) - self._max_sessions]:
                self._store.pop(sid, None)
                self._expires.pop(sid, None)

    def _ensure(self, session_id: str) -> SessionSocialState:
        now = self._now()
        exp = self._expires.get(session_id, 0)
        if session_id not in self._store or now > exp:
            self._store[session_id] = SessionSocialState()
        self._expires[session_id] = now + self._ttl
        self._sweep(now)
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
        st.last_social_at = self._now()

    def get_language(self, session_id: str):
        """Язык сессии (ru/uk/en) или None, если ещё не установлен."""
        return self._ensure(session_id).language

    def set_language(self, session_id: str, language: str):
        """Запоминает язык сессии для неоднозначных будущих реплик."""
        if language in ("ru", "uk", "en"):
            st = self._ensure(session_id)
            st.language = language
            st.last_social_at = self._now()
