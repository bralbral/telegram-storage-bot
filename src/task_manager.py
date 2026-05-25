from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable
from datetime import datetime

from aiogram.types import Message

logger = logging.getLogger(__name__)


class TaskManager:
    """Manage background tasks with queue and user notifications."""

    def __init__(self, max_concurrent_tasks: int = 3) -> None:
        self.max_concurrent_tasks = max_concurrent_tasks
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.user_queues: dict[int, asyncio.Queue] = defaultdict(asyncio.Queue)
        self.active_tasks: set[int] = set()

    async def add_task(
        self,
        user_id: int,
        task_func: Awaitable,
        message: Message,
        task_type: str = "task",
    ) -> None:
        """Add task to user queue and execute when slot available.

        Args:
            user_id: User ID
            task_func: Async function to execute
            message: Message for user notifications
            task_type: Type of task for notifications
        """
        is_queued = len(self.active_tasks) >= self.max_concurrent_tasks

        # Notify if task is queued due to worker limit
        if is_queued:
            await message.answer(
                f"⏳ All workers are busy. Your {task_type} is queued. "
                f"You'll be notified when it starts."
            )

        # Wait for semaphore slot
        await self.semaphore.acquire()
        self.active_tasks.add(user_id)

        try:
            # Notify user when task starts (only if it was queued)
            if is_queued:
                await message.answer(f"✅ Starting your {task_type}...")

            # Execute task
            await task_func

        except Exception as e:
            logger.error(f"Task failed for user {user_id}: {e}")
            await message.answer(f"❌ {task_type} failed: {e}")

        finally:
            # Clean up
            self.active_tasks.discard(user_id)
            self.semaphore.release()

    async def get_status(self, user_id: int) -> dict[str, int]:
        """Get queue status for user.

        Returns:
            Dict with queue position and active tasks info
        """
        queue_position = self.user_queues[user_id].qsize()
        is_active = user_id in self.active_tasks

        return {
            "queue_position": queue_position,
            "is_active": is_active,
            "max_concurrent": self.max_concurrent_tasks,
            "active_tasks": len(self.active_tasks),
        }

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Wait for active tasks to complete during shutdown.

        Args:
            timeout: Maximum time to wait for tasks to complete
        """
        logger.info("TaskManager shutdown initiated")
        logger.info(f"Active tasks: {len(self.active_tasks)}")
        logger.info(
            f"Total queue size: {sum(q.qsize() for q in self.user_queues.values())}"
        )

        # Wait for semaphore to release all slots
        start_time = datetime.now()

        while len(self.active_tasks) > 0:
            if (datetime.now() - start_time).total_seconds() > timeout:
                logger.warning(
                    f"Timeout waiting for {len(self.active_tasks)} active tasks"
                )
                break
            await asyncio.sleep(1)

        logger.info("TaskManager shutdown completed")
