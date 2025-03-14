#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OSSService 服务功能测试模块
"""
from typing import Dict, Any, TYPE_CHECKING
import pytest
import os
from unittest.mock import MagicMock, patch

import oss2
from src.bilibili_downloader.services import OSSService, OSSConfig
from src.bilibili_downloader.exceptions import OSSError

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


@pytest.fixture
def oss_config() -> OSSConfig:
    """
    创建OSS配置
    
    Returns:
        OSSConfig: OSS配置对象
    """
    return OSSConfig(
        access_key_id="test_key_id",
        access_key_secret="test_key_secret",
        endpoint="oss-cn-test.aliyuncs.com",
        bucket_name="test-bucket"
    )


@pytest.fixture
def mock_bucket(mocker: "MockerFixture") -> MagicMock:
    """
    模拟OSS Bucket
    
    Args:
        mocker: pytest-mock插件
        
    Returns:
        MagicMock: 模拟的Bucket对象
    """
    mock = MagicMock()
    mock.put_object_from_file = MagicMock()
    mock.sign_url = MagicMock(return_value="https://test-url.com/object")
    mock.delete_object = MagicMock()
    
    # 模拟oss2.Bucket类
    mocker.patch("oss2.Bucket", return_value=mock)
    # 模拟oss2.Auth类
    mocker.patch("oss2.Auth", return_value=MagicMock())
    
    return mock


def test_init(oss_config: OSSConfig, mock_bucket: MagicMock) -> None:
    """
    测试OSS服务初始化
    
    Args:
        oss_config: OSS配置
        mock_bucket: 模拟的Bucket对象
    """
    # 创建服务
    service = OSSService(oss_config)
    
    # 验证初始化
    assert service.config == oss_config
    assert service.bucket == mock_bucket
    
    # 验证Auth调用
    oss2.Auth.assert_called_once_with(
        oss_config.access_key_id,
        oss_config.access_key_secret
    )
    
    # 验证Bucket调用
    oss2.Bucket.assert_called_once()
    args, kwargs = oss2.Bucket.call_args
    assert args[2] == oss_config.bucket_name
    assert f"https://{oss_config.endpoint}" in str(args[1])


def test_upload_file_success(
    oss_config: OSSConfig, 
    mock_bucket: MagicMock,
    tmp_path: "pytest.Path"
) -> None:
    """
    测试成功上传文件
    
    Args:
        oss_config: OSS配置
        mock_bucket: 模拟的Bucket对象
        tmp_path: pytest临时路径
    """
    # 创建测试文件
    test_file = tmp_path / "test.txt"
    with open(test_file, "w") as f:
        f.write("测试内容")
    
    # 创建服务
    service = OSSService(oss_config)
    
    # 自定义对象名
    object_name = "custom/path/test.txt"
    
    # 测试上传
    url = service.upload_file(str(test_file), object_name, expire_seconds=600)
    
    # 验证结果
    assert url == "https://test-url.com/object"
    
    # 验证调用
    mock_bucket.put_object_from_file.assert_called_once_with(
        object_name, str(test_file)
    )
    mock_bucket.sign_url.assert_called_once_with(
        'GET', object_name, 600, slash_safe=True
    )


def test_upload_file_not_exists(oss_config: OSSConfig) -> None:
    """
    测试上传不存在的文件
    
    Args:
        oss_config: OSS配置
    """
    service = OSSService(oss_config)
    
    with pytest.raises(OSSError) as exc_info:
        service.upload_file("/not/exists/file.txt")
    
    assert "文件不存在" in str(exc_info.value)


def test_upload_file_oss_error(
    oss_config: OSSConfig, 
    mock_bucket: MagicMock,
    tmp_path: "pytest.Path"
) -> None:
    """
    测试上传文件OSS错误
    
    Args:
        oss_config: OSS配置
        mock_bucket: 模拟的Bucket对象
        tmp_path: pytest临时路径
    """
    # 创建测试文件
    test_file = tmp_path / "test.txt"
    with open(test_file, "w") as f:
        f.write("测试内容")
    
    # 设置模拟错误
    mock_bucket.put_object_from_file.side_effect = oss2.exceptions.OssError("测试OSS错误")
    
    # 创建服务
    service = OSSService(oss_config)
    
    # 测试错误
    with pytest.raises(OSSError) as exc_info:
        service.upload_file(str(test_file))
    
    assert "OSS操作失败" in str(exc_info.value)
    assert "测试OSS错误" in str(exc_info.value) 