import pytest

from src.handlers.pip import parse_pip_download
from src.services.pip_service import PipService


def test_parse_pip_download_includes_dependencies_by_default() -> None:
    request = parse_pip_download("pip download --python 3.12 requests==2.32.3", "user")

    assert request.python_version == "3.12"
    assert request.requirements == ["requests==2.32.3"]
    assert request.include_dependencies is True
    assert request.prefix == "user"


def test_parse_pip_download_accepts_no_deps_before_python_version() -> None:
    request = parse_pip_download("pip download --no-deps --python 3.11 requests", "")

    assert request.python_version == "3.11"
    assert request.requirements == ["requests"]
    assert request.include_dependencies is False


def test_parse_pip_download_accepts_only_binary() -> None:
    request = parse_pip_download(
        "pip download --python 3.12 --only-binary requests", ""
    )

    assert request.only_binary is True
    assert request.include_dependencies is True


def test_pip_archive_name_includes_pinned_package_version() -> None:
    archive_name = PipService._archive_name("user", "3.12", "pyspark==4.1.1")

    assert "python3.12_pyspark-4.1.1_" in archive_name


@pytest.mark.parametrize(
    "text",
    [
        "pip download requests",
        "pip download --python 3.12 --index-url https://example.test requests",
        "pip download --python 2.7 requests",
    ],
)
def test_parse_pip_download_rejects_invalid_input(text: str) -> None:
    with pytest.raises(Exception):
        parse_pip_download(text, "")


def test_parse_pip_download_accepts_python_37() -> None:
    request = parse_pip_download("pip download --python 3.7 requests", "")

    assert request.python_version == "3.7"
