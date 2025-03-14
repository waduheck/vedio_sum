#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
通用工具函数
"""
from typing import Optional, Dict, Any, Callable, TypeVar, Union
import os
import time
import requests
from ..exceptions import APIError

T = TypeVar('T')

def retry_request(
    func: Callable[[], T], 
    max_retries: int = 3, 
    retry_delay: int = 1,
    exceptions_to_catch: tuple = (requests.RequestException,),
    should_retry_func: Optional[Callable[[T], bool]] = None
) -> T:
    """
    带重试的请求函数装饰器
    
    Args:
        func: 要执行的函数
        max_retries: 最大重试次数
        retry_delay: 重试延迟(秒)
        exceptions_to_catch: 捕获的异常类型
        should_retry_func: 判断是否应该重试的函数
        
    Returns:
        T: 函数结果
        
    Raises:
        APIError: 重试失败时抛出
    """
    retry_count = 0
    while True:
        try:
            result = func()
            if should_retry_func and should_retry_func(result):
                if retry_count >= max_retries:
                    return result
                retry_count += 1
            else:
                return result
        except exceptions_to_catch as e:
            retry_count += 1
            if retry_count > max_retries:
                raise APIError(f"请求失败，已重试{max_retries}次: {str(e)}") from e
            
            # 指数退避
            sleep_time = retry_delay * (2 ** (retry_count - 1))
            print(f"请求失败，{sleep_time}秒后重试 ({retry_count}/{max_retries})...")
            time.sleep(sleep_time)

def ensure_dir(file_path: str) -> None:
    """
    确保目录存在，如果不存在则创建
    
    Args:
        file_path: 文件路径
    """
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

def format_file_size(size_bytes: Union[int, float]) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 文件大小(字节)
        
    Returns:
        str: 格式化后的文件大小
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.2f} MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.2f} GB" 