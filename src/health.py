from __future__ import annotations

import logging
import os

import docker
from aiohttp import web

logger = logging.getLogger(__name__)


class HealthServer:
    """Simple HTTP server for health checks."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        self.host = host
        self.port = port
        self.app = web.Application()
        self.app.add_routes([web.get("/health", self.health_handler)])
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None

    async def health_handler(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        health_data: dict[str, str | dict[str, str]] = {
            "status": "healthy",
            "service": "storage-bot",
        }

        # Check Docker daemon status
        try:
            docker_host = os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
            os.environ["DOCKER_HOST"] = docker_host
            client = docker.DockerClient(base_url=docker_host)
            client.ping()
            health_data["docker"] = {
                "status": "healthy",
                "message": "Docker daemon is running",
            }
        except Exception as e:
            health_data["docker"] = {"status": "unhealthy", "message": str(e)}
            health_data["status"] = "degraded"

        return web.json_response(health_data)

    async def start(self) -> None:
        """Start the health check server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        logger.info(f"Health check server started on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the health check server."""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Health check server stopped")
