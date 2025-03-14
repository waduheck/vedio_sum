#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BiliVideoDownloader 核心功能测试模块
"""
from typing import Dict, Any, TYPE_CHECKING
import pytest
import json
import hashlib
from unittest.mock import MagicMock, patch

from src.bilibili_downloader.core.downloader import BiliVideoDownloader
from src.bilibili_downloader.core.models import VideoInfo
from src.bilibili_downloader.exceptions import APIError, DownloadError

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


@pytest.fixture
def mock_response() -> MagicMock:
    """
    创建模拟的请求响应
    
    Returns:
        MagicMock: 模拟的响应对象
    """
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    return mock


@pytest.fixture
def video_downloader() -> BiliVideoDownloader:
    """
    创建视频下载器实例
    
    Returns:
        BiliVideoDownloader: 下载器实例
    """
    return BiliVideoDownloader(cookie="test_cookie")


def test_init(video_downloader: BiliVideoDownloader) -> None:
    """
    测试下载器初始化
    
    Args:
        video_downloader: 下载器实例
    """
    assert video_downloader.cookie == "test_cookie"
    assert "User-Agent" in video_downloader.session.headers
    assert "Referer" in video_downloader.session.headers
    assert "Cookie" in video_downloader.session.headers
    assert video_downloader.session.headers["Cookie"] == "test_cookie"


def test_get_video_info_success(
    video_downloader: BiliVideoDownloader, 
    mocker: "MockerFixture"
) -> None:
    """
    测试成功获取视频信息
    
    Args:
        video_downloader: 下载器实例
        mocker: pytest-mock插件
    """
    # 准备模拟数据
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 0,
        "data": {
            "title": "测试视频",
            "cid": 12345,
            "pages": [{"part": "P1", "cid": 12345}]
        }
    }
    
    # 模拟session.get方法
    mocker.patch.object(
        video_downloader.session,
        "get",
        return_value=mock_response
    )
    
    # 调用测试方法
    result = video_downloader.get_video_info("BV12345")
    
    # 验证结果
    assert isinstance(result, VideoInfo)
    assert result.title == "测试视频"
    assert result.cid == 12345
    assert len(result.pages) == 1
    
    # 验证API调用
    video_downloader.session.get.assert_called_once()
    args, kwargs = video_downloader.session.get.call_args
    assert args[0] == "https://api.bilibili.com/x/web-interface/view"
    assert kwargs["params"] == {"bvid": "BV12345"}


def test_get_video_info_api_error(
    video_downloader: BiliVideoDownloader, 
    mocker: "MockerFixture"
) -> None:
    """
    测试API错误时获取视频信息
    
    Args:
        video_downloader: 下载器实例
        mocker: pytest-mock插件
    """
    # 准备模拟数据
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": -403,
        "message": "访问权限不足"
    }
    
    # 模拟session.get方法
    mocker.patch.object(
        video_downloader.session,
        "get",
        return_value=mock_response
    )
    
    # 测试API错误
    with pytest.raises(APIError) as exc_info:
        video_downloader.get_video_info("BV12345")
    
    # 验证错误信息
    assert "API Error: 访问权限不足" in str(exc_info.value)


@pytest.mark.parametrize("chunk_size", [1024, 2048])
def test_download_video(
    video_downloader: BiliVideoDownloader, 
    mocker: "MockerFixture",
    tmp_path: "pytest.Path",
    chunk_size: int
) -> None:
    """
    测试视频下载功能
    
    Args:
        video_downloader: 下载器实例
        mocker: pytest-mock插件
        tmp_path: pytest临时路径
        chunk_size: 分块大小
    """
    # 模拟响应
    mock_response = MagicMock()
    mock_response.headers.get.return_value = "1024"
    mock_content = [b"test_data"] * 2
    mock_response.iter_content.return_value = mock_content
    
    # 模拟session.get
    mocker.patch.object(
        video_downloader.session,
        "get",
        return_value=mock_response
    )
    
    # 创建临时文件路径
    file_path = tmp_path / "test_video.mp4"
    
    # 测试下载
    result = video_downloader.download_video(
        "http://test.url", 
        str(file_path),
        chunk_size
    )
    
    # 验证结果
    assert result == str(file_path)
    assert file_path.exists()
    
    # 验证内容正确写入
    with open(file_path, "rb") as f:
        content = f.read()
        assert content == b"test_data" * 2
    
    # 验证参数传递
    mock_response.iter_content.assert_called_once_with(chunk_size=chunk_size)
