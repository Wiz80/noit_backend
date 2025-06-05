import os
from typing import Any
from urllib.parse import urljoin
from datetime import datetime, UTC

import httpx
from taskiq import TaskiqMiddleware, TaskiqResult, TaskiqMessage
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend


class TaskiqAdminMiddleware(TaskiqMiddleware):
    """Middleware to integrate with taskiq-admin dashboard"""
    
    def __init__(
        self,
        url: str,
        api_token: str,
        taskiq_broker_name: str | None = None,
    ):
        super().__init__()
        self.url = url
        self.api_token = api_token
        self.__ta_broker_name = taskiq_broker_name

    async def post_send(self, message):
        """Called after sending a task to the queue"""
        now = datetime.now(UTC).replace(tzinfo=None).isoformat()
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    headers={"access-token": self.api_token},
                    url=urljoin(self.url, f"/api/tasks/{message.task_id}/queued"),
                    json={
                        "args": message.args,
                        "kwargs": message.kwargs,
                        "taskName": message.task_name,
                        "worker": self.__ta_broker_name,
                        "queuedAt": now,
                    },
                )
        except Exception as e:
            print(f"Error sending queued status to taskiq-admin: {e}")
        return super().post_send(message)

    async def pre_execute(self, message: TaskiqMessage):
        """Called before executing a task"""
        now = datetime.now(UTC).replace(tzinfo=None).isoformat()
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    headers={"access-token": self.api_token},
                    url=urljoin(self.url, f"/api/tasks/{message.task_id}/started"),
                    json={
                        "startedAt": now,
                        "args": message.args,
                        "kwargs": message.kwargs,
                        "taskName": message.task_name,
                        "worker": self.__ta_broker_name,
                    },
                )
        except Exception as e:
            print(f"Error sending started status to taskiq-admin: {e}")
        return super().pre_execute(message)

    async def post_execute(
        self,
        message: TaskiqMessage,
        result: TaskiqResult[Any],
    ):
        """Called after executing a task"""
        now = datetime.now(UTC).replace(tzinfo=None).isoformat()
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    headers={"access-token": self.api_token},
                    url=urljoin(
                        self.url,
                        f"/api/tasks/{message.task_id}/executed",
                    ),
                    json={
                        "finishedAt": now,
                        "error": result.error
                        if result.error is None
                        else repr(result.error),
                        "executionTime": result.execution_time,
                        "returnValue": {"return_value": result.return_value},
                    },
                )
        except Exception as e:
            print(f"Error sending executed status to taskiq-admin: {e}")
        return super().post_execute(message, result)


# Configuration - Use localhost for local development
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TASKIQ_ADMIN_URL = os.getenv("TASKIQ_ADMIN_URL", "http://localhost:3000")
TASKIQ_ADMIN_API_TOKEN = os.getenv("TASKIQ_ADMIN_API_TOKEN", "supersecret")
BROKER_NAME = os.getenv("TASKIQ_BROKER_NAME", "noit_backend_local")

# Create result backend
result_backend = RedisAsyncResultBackend(REDIS_URL)

# Create broker with Redis
broker = (
    ListQueueBroker(
        url=REDIS_URL,
        queue_name="noit_backend_queue",
    )
    .with_result_backend(result_backend)
    .with_middlewares(
        TaskiqAdminMiddleware(
            url=TASKIQ_ADMIN_URL,
            api_token=TASKIQ_ADMIN_API_TOKEN,
            taskiq_broker_name=BROKER_NAME,
        )
    )
)

print(f"🚀 Taskiq broker configured with Redis: {REDIS_URL}")
print(f"📊 Taskiq Admin URL: {TASKIQ_ADMIN_URL}")
print(f"🏷️  Broker Name: {BROKER_NAME}")

# Note: Tasks will be imported when the tasks module is imported
# This avoids circular import issues 