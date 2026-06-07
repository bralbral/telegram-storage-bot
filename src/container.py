from __future__ import annotations

from dependency_injector import containers, providers

from src.db.database import Database
from src.models.config import Config
from src.services.compression_service import CompressionService
from src.services.docker_service import DockerService
from src.services.file_service import FileService
from src.services.user_service import UserService


class Container(containers.DeclarativeContainer):
    """Dependency injection container for the application."""

    # Configuration
    config = providers.Configuration()

    # Pydantic Config
    pydantic_config = providers.Singleton(Config)

    # Database
    database = providers.Singleton(
        Database,
        path=providers.Attribute(pydantic_config, "db_path"),
    )

    # Services
    compression_service = providers.Singleton(CompressionService)

    user_service = providers.Singleton(
        UserService,
        db=database,
    )

    file_service = providers.Singleton(
        FileService,
        compression_service=compression_service,
        download_dir=providers.Attribute(pydantic_config, "download_dir"),
    )

    docker_service = providers.Singleton(
        DockerService,
        docker_host=providers.Attribute(pydantic_config, "docker_host"),
        download_dir=providers.Attribute(pydantic_config, "download_dir"),
    )
