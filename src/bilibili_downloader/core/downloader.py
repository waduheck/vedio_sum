#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
B站视频下载器核心功能
"""
from typing import Dict, Optional, Tuple, Any
import hashlib
import time
import urllib.parse
import requests
from .models import VideoInfo
from ..exceptions import DownloadError, APIError

class BiliVideoDownloader:
    """B站视频下载器核心类"""
    
    def __init__(self, cookie: Optional[str] = None):
        """
        初始化下载器
        
        Args:
            cookie: 用户登录Cookie，可选
        """
        self.cookie = cookie
        self.session = requests.Session()
        self._setup_headers()

    def _setup_headers(self) -> None:
        """配置请求头"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/'
        }
        if self.cookie:
            headers['Cookie'] = self.cookie
        self.session.headers.update(headers)

    def get_video_info(self, bvid: str) -> VideoInfo:
        """
        获取视频元数据
        
        Args:
            bvid: 视频BV号
            
        Returns:
            VideoInfo: 视频信息对象
            
        Raises:
            APIError: API请求失败时抛出
        """
        url = "https://api.bilibili.com/x/web-interface/view"
        params = {'bvid': bvid}
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data['code'] != 0:
                raise APIError(f"API Error: {data['message']}")
                
            return VideoInfo(
                title=data['data']['title'],
                cid=data['data']['cid'],
                pages=data['data']['pages']
            )
            
        except requests.RequestException as e:
            raise APIError(f"请求失败: {str(e)}") from e
            
    def get_download_url(self, bvid: str, cid: int, quality: int = 80) -> str:
        """
        获取视频下载地址
        
        Args:
            bvid: 视频BV号
            cid: 视频分P的cid
            quality: 视频质量，默认80
            
        Returns:
            str: 视频下载地址
            
        Raises:
            APIError: API请求失败时抛出
        """
        base_url = "https://api.bilibili.com/x/player/wbi/playurl"
        
        params = {
            'bvid': bvid,
            'cid': cid,
            'qn': quality,
            'fnval': 1,
            'fourk': 1
        }
        
        try:
            response = self.session.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data['code'] != 0:
                raise APIError(f"获取下载地址失败: {data['message']}")
                
            return data['data']['durl'][0]['url']
        except requests.RequestException as e:
            raise APIError(f"获取下载地址失败: {str(e)}") from e
        except (KeyError, IndexError) as e:
            raise APIError(f"解析下载地址失败: {str(e)}") from e

    def download_video(self, url: str, save_path: str, chunk_size: int = 1024*1024) -> str:
        """
        下载视频文件
        
        Args:
            url: 视频下载地址
            save_path: 保存路径
            chunk_size: 块大小，默认1MB
            
        Returns:
            str: 保存的文件路径
            
        Raises:
            DownloadError: 下载失败时抛出
        """
        headers = {'Referer': 'https://www.bilibili.com'}
        try:
            response = self.session.get(url, headers=headers, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # 添加下载进度显示
                        print(f"\r下载进度: {downloaded}/{total_size} bytes ({downloaded/total_size:.2%})", end='')
            print("\n下载完成！")
            return save_path
        except KeyboardInterrupt:
            raise DownloadError("用户中断下载")
        except Exception as e:
            raise DownloadError(f"下载失败: {str(e)}", original_error=e) 