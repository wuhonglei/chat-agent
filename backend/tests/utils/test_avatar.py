"""头像工具单元测试。"""

import pytest

from app.utils.avatar import (
    AVATAR_URL_PREFIX,
    InvalidAvatarError,
    avatar_filename_from_storage,
    avatar_storage_path,
    filename_from_cos_url,
    is_cos_avatar_url,
    is_valid_avatar_filename,
    normalize_avatar_for_storage,
)

_VALID_NAME = "3f2a1b4c-8d9e-4f5a-b6c7-1234567890ab.png"


def test_avatar_storage_path() -> None:
    assert avatar_storage_path(_VALID_NAME) == f"{AVATAR_URL_PREFIX}{_VALID_NAME}"


def test_avatar_filename_from_storage() -> None:
    path = avatar_storage_path(_VALID_NAME)
    assert avatar_filename_from_storage(path) == _VALID_NAME


def test_is_cos_avatar_url() -> None:
    url = (
        "https://ai-chat-1258352625.cos.ap-guangzhou.myqcloud.com/"
        f"avatars/{_VALID_NAME}"
    )
    assert is_cos_avatar_url(url)
    assert not is_cos_avatar_url("https://thirdwx.qlogo.cn/mmopen/abc")
    assert not is_cos_avatar_url(f"{AVATAR_URL_PREFIX}{_VALID_NAME}")


def test_filename_from_cos_url() -> None:
    url = (
        "https://ai-chat-1258352625.cos.ap-guangzhou.myqcloud.com/"
        f"avatars/{_VALID_NAME}"
    )
    assert filename_from_cos_url(url) == _VALID_NAME


def test_normalize_avatar_for_storage() -> None:
    path = avatar_storage_path(_VALID_NAME)
    assert normalize_avatar_for_storage(path) == path
    assert (
        normalize_avatar_for_storage("https://thirdwx.qlogo.cn/x")
        == "https://thirdwx.qlogo.cn/x"
    )
    with pytest.raises(InvalidAvatarError):
        normalize_avatar_for_storage(_VALID_NAME)
    cos_url = (
        "https://ai-chat-1258352625.cos.ap-guangzhou.myqcloud.com/"
        f"avatars/{_VALID_NAME}"
    )
    with pytest.raises(InvalidAvatarError):
        normalize_avatar_for_storage(cos_url)


def test_is_valid_avatar_filename() -> None:
    assert is_valid_avatar_filename(_VALID_NAME)
    assert not is_valid_avatar_filename("../../../etc/passwd")
    assert not is_valid_avatar_filename("upload.png")
