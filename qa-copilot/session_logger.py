# -*- coding: utf-8 -*-
import os
import json
import asyncio
import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Beijing timezone (UTC+8)
BEIJING_TZ = datetime.timezone(datetime.timedelta(hours=8))


BASE_LOG_DIR = Path(
    os.getenv("DJ_COPILOT_LOG_DIR") or (Path(__file__).parent / "logs")
)

# Check if logging is enabled (default: True for backward compatibility)
ENABLE_SESSION_LOGGING = os.getenv("DJ_COPILOT_ENABLE_LOGGING", "true").lower() in ("true", "1", "yes", "on")


class SessionLogger:
    """Session-level logger writing JSON lines asynchronously."""

    def __init__(
        self,
        session_id: str,
        user_id: str,
        base_dir: Optional[Path] = None,
    ) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.enabled = ENABLE_SESSION_LOGGING
        
        if not self.enabled:
            # Skip file creation if logging is disabled
            return
            
        self.base_dir = base_dir or BASE_LOG_DIR

        now = datetime.datetime.now(BEIJING_TZ)
        date_str = now.strftime("%Y%m%d")  # directory by date
        time_str = now.strftime("%H%M%S_%f")  # file name by time

        self.log_dir = self.base_dir / date_str / session_id
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.file_path = self.log_dir / f"{time_str}.log"

    async def log_event(self, data: Dict[str, Any]) -> None:
        """Append one JSON line event asynchronously (fire-and-forget)."""
        if not self.enabled:
            return
            
        record = dict(data)
        # Ensure common fields
        record.setdefault(
            "timestamp",
            datetime.datetime.now(BEIJING_TZ).isoformat(timespec="milliseconds"),
        )
        record.setdefault("session_id", self.session_id)
        record.setdefault("user_id", self.user_id)

        line = json.dumps(record, ensure_ascii=False)
        # Fire-and-forget to avoid blocking main coroutine
        asyncio.create_task(self._async_write(line))

    def _write_line(self, line: str) -> None:
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    async def _async_write(self, line: str) -> None:
        try:
            await asyncio.to_thread(self._write_line, line)
        except Exception as e:
            print(f"[SessionLogger] Failed to write log: {e}")


