"""engine/events.py — Real-time thread-safe EventBus for EduEvidence.

Provides event publishing and subscription across orchestrator, engine modules,
and dashboard SSE streams with bounded ring-buffer history.
"""
from __future__ import annotations

import collections
import json
import threading
import time
from typing import Any, Callable, Deque, Dict, List, Optional


class EventBus:
    _instance: Optional[EventBus] = None
    _lock = threading.Lock()

    def __new__(cls) -> EventBus:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventBus, cls).__new__(cls)
                cls._instance._subscribers = []
                cls._instance._history = collections.deque(maxlen=500)
                cls._instance._bus_lock = threading.RLock()
            return cls._instance

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        with self._bus_lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        with self._bus_lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def publish(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        event = {
            "type": event_type,
            "payload": payload,
            "timestamp": time.time(),
            "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with self._bus_lock:
            self._history.append(event)
            subs = list(self._subscribers)
            
        for sub in subs:
            try:
                sub(event)
            except Exception:
                pass
        return event

    def get_history(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._bus_lock:
            if event_type:
                return [e for e in self._history if e["type"] == event_type]
            return list(self._history)

    def clear(self) -> None:
        with self._bus_lock:
            self._history.clear()


event_bus = EventBus()
