"""Global Generation Concurrency Lock and Crash Recovery (§5.5, §5.7, Criterion A-30).

Guarantees:
- Single process-wide asyncio.Lock for all generation/fix/variation operations
- HTTP 409 'busy' error with active_clip_id when locked
- try/finally lock release on completion, error, cancellation, or disconnect
- Startup crash recovery resetting stuck 'generating' clips to 'draft'
"""

from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator, Optional

from app.storage.db import get_connection

logger = logging.getLogger("h3studio.lock")

class GenerationBusyError(Exception):
    def __init__(self, active_clip_id: Optional[int]):
        self.active_clip_id = active_clip_id
        super().__init__(f"Generation engine is busy with clip {active_clip_id}")

class GenerationLock:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._active_clip_id: Optional[int] = None

    @property
    def active_clip_id(self) -> Optional[int]:
        return self._active_clip_id

    @property
    def is_locked(self) -> bool:
        return self._lock.locked()

    @asynccontextmanager
    async def hold(self, clip_id: int) -> AsyncGenerator[None, None]:
        """
        Acquire process-wide generation lock for clip_id.
        Raises GenerationBusyError (HTTP 409) if another generation is active.
        Guarantees release in finally block on error, cancel, or disconnect.
        """
        if self._lock.locked():
            raise GenerationBusyError(self._active_clip_id)

        await self._lock.acquire()
        self._active_clip_id = clip_id
        logger.info("Generation lock acquired for clip %d", clip_id)

        # Update DB clip status to 'generating'
        with get_connection() as conn:
            conn.execute("UPDATE clips SET status = 'generating' WHERE id = ?", (clip_id,))
            conn.commit()

        try:
            yield
        finally:
            self._active_clip_id = None
            self._lock.release()
            logger.info("Generation lock released for clip %d", clip_id)

global_generation_lock = GenerationLock()

def recover_generating_clips_on_startup() -> int:
    """
    Reset any clips left in 'generating' state due to an ungraceful crash back to 'draft' (§5.5, §5.7).
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE clips SET status = 'draft' WHERE status = 'generating'")
        reset_count = cur.rowcount
        conn.commit()
        if reset_count > 0:
            logger.warning("Startup crash recovery: reset %d clips from 'generating' to 'draft'", reset_count)
        return reset_count
