"""rate_limiter.py — SEC-05: анти-абьюз без утечек памяти.

Отличие от прежнего лимита только по `user_id`:
- ключом может быть что угодно (мы лимитируем и по IP — ротация `user_id`
  больше не обходит защиту);
- есть отдельный глобальный бюджет запросов в минуту — потолок расходов;
- словари не растут бесконечно: ключи, молчащие сутки, вычищаются, а при
  превышении потолка режутся самые старые.

Состояние in-memory и подходит для текущего single-instance деплоя.
"""

import time
from collections import deque
from typing import Callable, Deque, Dict


class RateLimitExceeded(Exception):
    """Лимит исчерпан. `retry_after` — секунды для заголовка Retry-After."""

    def __init__(self, detail: str, retry_after: int = 60):
        super().__init__(detail)
        self.detail = detail
        self.retry_after = retry_after


class RateLimiter:
    """Лимит по ключу: N запросов в минуту и M в сутки."""

    def __init__(
        self,
        per_minute: int,
        per_day: int,
        *,
        max_keys: int = 20000,
        sweep_interval: int = 300,
        clock: Callable[[], float] = time.time,
    ):
        self.per_minute = per_minute
        self.per_day = per_day
        self.max_keys = max_keys
        self.sweep_interval = sweep_interval
        self._clock = clock
        self._hits: Dict[str, Deque[float]] = {}
        self._day_count: Dict[str, int] = {}
        self._day: Dict[str, str] = {}
        self._last_sweep = clock()

    @staticmethod
    def _day_key(now: float) -> str:
        return time.strftime("%Y-%m-%d", time.localtime(now))

    def _drop(self, key: str) -> None:
        self._hits.pop(key, None)
        self._day_count.pop(key, None)
        self._day.pop(key, None)

    def _evict_oldest(self, count: int) -> None:
        oldest = sorted(
            self._hits, key=lambda k: self._hits[k][-1] if self._hits[k] else 0.0
        )
        for key in oldest[:count]:
            self._drop(key)

    def _enforce_cap(self) -> None:
        if len(self._hits) > self.max_keys:
            self._evict_oldest(len(self._hits) - self.max_keys)

    def _sweep(self, now: float) -> None:
        if now - self._last_sweep < self.sweep_interval and len(self._hits) <= self.max_keys:
            return
        cutoff = now - 86400
        for key in [k for k, dq in self._hits.items() if not dq or dq[-1] < cutoff]:
            self._drop(key)
        self._last_sweep = now

    def hit(self, key: str) -> None:
        now = self._clock()
        self._sweep(now)

        dq = self._hits.get(key)
        if dq is None:
            dq = self._hits[key] = deque()
        dq.append(now)
        while dq and dq[0] <= now - 60:
            dq.popleft()
        self._enforce_cap()
        if len(dq) > self.per_minute:
            raise RateLimitExceeded(
                "Too many requests. Please wait a minute.", retry_after=60
            )

        day = self._day_key(now)
        if self._day.get(key) != day:
            self._day[key] = day
            self._day_count[key] = 0
        self._day_count[key] += 1
        if self._day_count[key] > self.per_day:
            raise RateLimitExceeded(
                "Daily limit exceeded. Try again tomorrow.", retry_after=3600
            )

    def tracked_keys(self) -> int:
        """Текущее число ключей — для тестов и метрик."""
        return len(self._hits)


class GlobalMinuteBudget:
    """Общий потолок запросов в минуту по всему инстансу."""

    def __init__(self, per_minute: int, *, clock: Callable[[], float] = time.time):
        self.per_minute = per_minute
        self._clock = clock
        self._hits: Deque[float] = deque()

    def hit(self) -> None:
        now = self._clock()
        self._hits.append(now)
        while self._hits and self._hits[0] <= now - 60:
            self._hits.popleft()
        if len(self._hits) > self.per_minute:
            raise RateLimitExceeded(
                "Service is busy. Please try again in a minute.", retry_after=60
            )
