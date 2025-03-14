#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从OSS获取文件URL示例
"""
import os
import sys
import argparse
import yaml
from typing import Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# 添加上级目录到路径，方便直接运行示例
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bilibili_downloader.services import OSSService, OSSConfig
from src.bilibili_downloader.exceptions import OSSError


def parse_arguments() -> argparse.Namespace:
    """
    解析命令行参数
    
    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(description='从OSS获取文件URL')
    parser.add_argument('object_name', help='OSS对象名称，例如: videos/example.mp4')
    parser.add_argument('-c', '--config', help='配置文件路径', 
                        default=str(Path(__file__).parent.parent / 'config' / 'config.yaml'))
    parser.add_argument('-e', '--expire', help='URL有效期（秒）', type=int, default=3600)
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
    
    # 检查OSS配置
    if 'oss' not in config:
        print("未找到OSS配置")
        sys.exit(1)
    
    try:
        # 处理环境变量占位符
        oss_config = config['oss'].copy()
        for key, value in oss_config.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                oss_config[key] = os.environ.get(env_var, '')
        
        # 设置环境变量供OSS SDK使用
        os.environ['OSS_ACCESS_KEY_ID'] = oss_config['access_key_id']
        os.environ['OSS_ACCESS_KEY_SECRET'] = oss_config['access_key_secret']
        
        # 创建OSS服务
        oss_service = OSSService(OSSConfig(**oss_config))
        
        # 获取URL
        print(f"正在获取OSS对象URL: {args.object_name}")
        url = oss_service.get_file_url(args.object_name, args.expire)
        
        print(f"\n文件: {args.object_name}")
        print(f"有效期: {args.expire}秒")
        print(f"\nURL: {url}")
        
    except OSSError as e:
        print(f"错误: {e.message}")
        if hasattr(e, 'original_error') and e.original_error:
            print(f"原始错误: {str(e.original_error)}")
        sys.exit(1)
    except Exception as e:
        print(f"未处理异常: {str(e)}")
        sys.exit(2)


if __name__ == "__main__":
    main() 