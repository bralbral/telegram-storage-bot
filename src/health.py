from __future__ import annotations

import logging

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
        return web.json_response({"status": "healthy", "service": "storage-bot"})

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
