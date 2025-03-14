#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OSS基础功能测试模块
"""
from typing import TYPE_CHECKING
import os
import pytest
import oss2
from oss2.credentials import EnvironmentVariableCredentialsProvider

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


@pytest.mark.skip(reason="需要环境变量配置才能运行")
def test_oss_connection() -> None:
    """
    测试OSS连接和签名URL生成
    
    需要设置环境变量:
    - OSS_ACCESS_KEY_ID
    - OSS_ACCESS_KEY_SECRET
    """
    # 从环境变量中获取访问凭证
    auth = oss2.ProviderAuthV4(EnvironmentVariableCredentialsProvider())

    # 填写Endpoint和Region信息
    endpoint = "https://oss-cn-beijing.aliyuncs.com"
    region = "cn-beijing"

    # 填写存储空间名称
    bucket = oss2.Bucket(auth, endpoint, "auto-scrip", region=region)

    # 测试文件
    object_name = 'example.txt'

    # 生成下载文件的预签名URL，有效时间为600秒
    url = bucket.sign_url('GET', object_name, 600, slash_safe=True)
    
    # 验证URL生成
    assert url is not None
    assert "auto-scrip" in url
    assert "example.txt" in url
    print(f'预签名URL的地址为: {url}') 