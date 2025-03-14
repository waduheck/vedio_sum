#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
阿里云OSS上传示例
"""
import os
import sys
import argparse
from typing import Dict, Any, Optional
from pathlib import Path

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
    parser = argparse.ArgumentParser(description='阿里云OSS上传示例')
    parser.add_argument('file_path', help='要上传的文件路径')
    parser.add_argument('-o', '--object', help='OSS对象名称，默认使用文件名')
    parser.add_argument('-e', '--expire', help='URL有效期(秒)', type=int, default=3600)
    return parser.parse_args()


def main() -> None:
    """主程序入口"""
    # 解析命令行参数
    args = parse_arguments()
    
    # 从环境变量获取OSS配置
    access_key_id = os.environ.get('OSS_ACCESS_KEY_ID')
    access_key_secret = os.environ.get('OSS_ACCESS_KEY_SECRET')
    endpoint = os.environ.get('OSS_ENDPOINT', 'oss-cn-beijing.aliyuncs.com')
    bucket_name = os.environ.get('OSS_BUCKET', 'auto-scrip')
    
    # 检查必要的环境变量
    if not access_key_id or not access_key_secret:
        print("错误: 请设置环境变量 OSS_ACCESS_KEY_ID 和 OSS_ACCESS_KEY_SECRET")
        sys.exit(1)
    
    # 检查文件是否存在
    if not os.path.exists(args.file_path):
        print(f"错误: 文件不存在: {args.file_path}")
        sys.exit(1)
    
    try:
        # 创建OSS配置
        oss_config = OSSConfig(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            endpoint=endpoint,
            bucket_name=bucket_name
        )
        
        # 创建OSS服务
        oss_service = OSSService(oss_config)
        
        # 上传文件
        print(f"正在上传文件: {args.file_path}")
        object_name = args.object or os.path.basename(args.file_path)
        url = oss_service.upload_file(
            args.file_path, 
            object_name,
            expire_seconds=args.expire
        )
        
        print(f"上传成功！")
        print(f"OSS对象名称: {object_name}")
        print(f"临时访问地址 ({args.expire}秒有效): {url}")
        
    except OSSError as e:
        print(f"OSS错误: {e.message}")
        if hasattr(e, 'original_error') and e.original_error:
            print(f"原始错误: {str(e.original_error)}")
        sys.exit(1)
    except Exception as e:
        print(f"未处理异常: {str(e)}")
        sys.exit(3)


if __name__ == "__main__":
    main() 