from pathlib import Path

from src.services.docker_service import DockerService


def test_download_dir_diagnostics_reports_usable_directory(tmp_path: Path) -> None:
    service = DockerService("unix:///var/run/docker.sock", tmp_path)

    diagnostics = service._download_dir_diagnostics()

    assert diagnostics["download_dir"] == str(tmp_path)
    assert diagnostics["download_dir_exists"] is True
    assert diagnostics["download_dir_is_directory"] is True
    assert diagnostics["download_dir_writable"] is True
    assert diagnostics["download_dir_free_bytes"] > 0
    assert diagnostics["download_dir_free_inodes"] > 0
