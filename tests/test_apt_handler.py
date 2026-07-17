import pytest

from src.handlers.apt import parse_apt_download
from src.services.apt_service import AptService


def test_parse_apt_download_defaults_to_debian_12() -> None:
    request = parse_apt_download("apt download curl", "user")

    assert request.debian_version == "12"
    assert request.packages == ["curl"]
    assert request.include_dependencies is True


def test_parse_apt_download_accepts_historical_target_and_no_deps() -> None:
    request = parse_apt_download(
        "apt download --no-deps —debian 10.2.0 curl=7.64.0-4+deb10u2",
        "",
    )

    assert request.debian_version == "10.2.0"
    assert request.snapshot is None
    assert request.include_dependencies is False
    assert request.packages == ["curl=7.64.0-4+deb10u2"]


def test_apt_archive_name_includes_target_and_pinned_package_version() -> None:
    archive_name = AptService._archive_name("user", "10.0.0", "curl=7.64.0-4")

    assert "debian10.0.0_curl-7.64.0-4_" in archive_name


def test_known_point_release_uses_its_catalog_snapshot() -> None:
    request = parse_apt_download("apt download --debian 10.0.0 curl", "")

    target = AptService._target(request)

    assert "20190707T000000Z" in target.repository


@pytest.mark.parametrize(
    "text",
    [
        "apt download --debian 9 curl",
        "apt download --debian 10.0.0 --option value curl",
        "apt download --debian 10.0.0 ../curl",
    ],
)
def test_parse_apt_download_rejects_invalid_input(text: str) -> None:
    with pytest.raises(Exception):
        parse_apt_download(text, "")


def test_unknown_point_release_is_rejected_by_target_resolver() -> None:
    request = parse_apt_download("apt download --debian 10.3.0 curl", "")

    with pytest.raises(ValueError, match="point-release catalog"):
        AptService._target(request)
