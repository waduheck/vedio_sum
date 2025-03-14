#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
B站视频下载示例
"""
import os
import sys
import argparse
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# 添加上级目录到路径，方便直接运行示例
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bilibili_downloader.core import BiliVideoDownloader
from src.bilibili_downloader.exceptions import BilibiliDownloaderError


def parse_arguments() -> argparse.Namespace:
    """
    解析命令行参数
    
    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(description='B站视频下载示例')
    parser.add_argument('bvid', help='视频BV号')
    parser.add_argument('-o', '--output', help='输出文件路径', default='video.mp4')
    parser.add_argument('-q', '--quality', help='视频质量', type=int, default=80)
    parser.add_argument('--cookie', help='B站Cookie')
    parser.add_argument('-c', '--config', help='配置文件路径', 
                        default=str(Path(__file__).parent.parent / 'config' / 'config.yaml'))
    return parser.parse_args()


def load_config(config_path: str) -> Dict[str, Any]:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        Dict[str, Any]: 配置字典
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"加载配置文件失败: {str(e)}")
        return {}


def main() -> None:
    """主程序入口"""
    # 加载环境变量
    load_dotenv()
    
    # 解析命令行参数
    args = parse_arguments()
    
    # 加载配置文件
    config = load_config(args.config)
    
    # 获取Cookie，优先级：命令行参数 > 环境变量 > 配置文件
    cookie = args.cookie or os.environ.get('BILIBILI_COOKIE', '') or config.get('bilibili', {}).get('cookie', '')
    
    # 处理环境变量占位符
    if cookie and cookie.startswith('${') and cookie.endswith('}'):
        env_var = cookie[2:-1]
        cookie = os.environ.get(env_var, '')
    
    try:
        # 初始化下载器
        downloader = BiliVideoDownloader(cookie=cookie)
        
        # 获取视频信息
        print(f"获取视频信息: {args.bvid}")
        video_info = downloader.get_video_info(args.bvid)
        print(f"视频标题: {video_info.title}")
        
        # 获取下载地址
        cid = video_info.cid
        quality = args.quality or config.get('bilibili', {}).get('default_quality', 80)
        print(f"获取下载地址, 质量: {quality}")
        url = downloader.get_download_url(args.bvid, cid, quality)
        # 下载视频
        chunk_size = config.get('bilibili', {}).get('chunk_size', 1024*1024*1024)
        print(f"开始下载到: {args.output}")
        local_path = downloader.download_video(url, args.output, chunk_size)
        
        print(f"下载完成！文件保存在: {local_path}")
        
    except BilibiliDownloaderError as e:
        print(f"错误: {e.message}")
        if hasattr(e, 'original_error') and e.original_error:
            print(f"原始错误: {str(e.original_error)}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n用户中断操作")
        sys.exit(2)
    except Exception as e:
        print(f"未处理异常: {str(e)}")
        sys.exit(3)


if __name__ == "__main__":
    main() 