#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
视频摘要Demo

这个脚本整合了以下功能：
1. 输入B站视频BV号或BV号列表文件
2. 下载视频
3. 将视频上传到OSS获取临时URL
4. 将URL传给通义千悟API
5. 获取并解析返回的JSON结果
"""
import os
import sys
import json
import time
import argparse
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
from dotenv import load_dotenv

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 导入自定义模块
from src.bilibili_downloader.core import TaskManager, VideoProcessor
from src.bilibili_downloader.services import OSSService, OSSConfig, TingwuService, TingwuConfig
from src.bilibili_downloader.services import StatusDisplayService, PipelineService
from src.bilibili_downloader.exceptions import BilibiliDownloaderError, OSSError, APIError


def parse_arguments() -> argparse.Namespace:
    """
    解析命令行参数
    
    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(description='B站视频摘要Demo')
    
    # 视频来源参数组（互斥）
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument('--bvid', help='单个视频BV号')
    source_group.add_argument('--bvid-file', help='包含BV号列表的文件路径，每行一个BV号')
    
    # 配置和输出参数
    parser.add_argument('-c', '--config', help='配置文件路径', 
                        default=str(Path(__file__).parent / 'config' / 'config.yaml'))
    parser.add_argument('-o', '--output', help='输出文件路径模板，使用{bvid}作为占位符', default='video_{bvid}.mp4')
    parser.add_argument('-q', '--quality', help='视频质量', type=int, default=80)
    parser.add_argument('--cookie', help='B站Cookie')
    parser.add_argument('--keep', help='保留本地文件', action='store_true')
    parser.add_argument('--language-type', help='语言类型', default='auto')
    parser.add_argument('--interval', help='查询间隔(秒)', type=float, default=5.0)
    parser.add_argument('--output-dir', help='输出目录', default='output')
    parser.add_argument('--enable-diarization', help='启用角色分离', action='store_true', default=True)
    parser.add_argument('--speaker-count', help='说话人数量', type=int, default=2)
    parser.add_argument('--enable-chapters', help='启用章节速览', action='store_true', default=True)
    parser.add_argument('--enable-meeting', help='启用智能纪要', action='store_true', default=True)
    parser.add_argument('--enable-ppt', help='启用PPT提取', action='store_true', default=False)
    parser.add_argument('--enable-polish', help='启用口语书面化', action='store_true', default=True)
    parser.add_argument('--continue-on-error', help='批处理时遇到错误继续执行', action='store_true', default=True)
    
    # 并发处理参数
    parser.add_argument('--max-concurrent', help='最大并发上传任务数', type=int, default=1)
    parser.add_argument('--pipeline', help='启用流水线处理模式', action='store_true', default=True)
    parser.add_argument('--no-status-display', help='禁用状态显示', action='store_true')
    parser.add_argument('--refresh-interval', help='状态刷新间隔(秒)', type=float, default=2.0)
    
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
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config
        else:
            print(f"配置文件不存在: {config_path}，将使用默认配置")
            return {}
    except Exception as e:
        print(f"加载配置文件失败: {str(e)}")
        return {}


def read_bvid_list(file_path: str) -> List[str]:
    """
    从文件中读取BV号列表
    
    Args:
        file_path: 文件路径，每行包含一个BV号
        
    Returns:
        List[str]: BV号列表
        
    Raises:
        FileNotFoundError: 文件不存在时抛出
        Exception: 读取或解析出错时抛出
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"BV号列表文件不存在: {file_path}")
    
    bvids = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # 清理每行并检查非空
                bvid = line.strip()
                if bvid and not bvid.startswith('#'):  # 忽略空行和注释行
                    bvids.append(bvid)
        
        # 去重
        unique_bvids = []
        seen = set()
        for bvid in bvids:
            if bvid not in seen:
                seen.add(bvid)
                unique_bvids.append(bvid)
        
        if not unique_bvids:
            raise ValueError(f"BV号列表文件为空或格式不正确: {file_path}")
            
        return unique_bvids
    except Exception as e:
        raise Exception(f"读取BV号列表文件失败: {str(e)}") from e


def setup_oss(config: Dict[str, Any]) -> Optional[OSSService]:
    """
    设置OSS服务
    
    Args:
        config: 配置字典
        
    Returns:
        Optional[OSSService]: OSS服务对象
    """
    try:
        # 处理环境变量占位符
        oss_config = config.get('oss', {}).copy()
        for key, value in oss_config.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                oss_config[key] = os.environ.get(env_var, '')
        
        # 检查必要的配置
        access_key_id = oss_config.get('access_key_id', os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID', ''))
        access_key_secret = oss_config.get('access_key_secret', os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET', ''))
        endpoint = oss_config.get('endpoint', os.environ.get('OSS_ENDPOINT', 'oss-cn-beijing.aliyuncs.com'))
        bucket_name = oss_config.get('bucket_name', os.environ.get('OSS_BUCKET_NAME', 'auto-scrip'))
        region = oss_config.get('region', os.environ.get('OSS_REGION', 'cn-beijing'))
        
        if not access_key_id or not access_key_secret:
            print("阿里云访问密钥未设置，请确保ALIBABA_CLOUD_ACCESS_KEY_ID和ALIBABA_CLOUD_ACCESS_KEY_SECRET环境变量已配置")
            return None
            
        # 创建OSS服务
        oss_config_obj = OSSConfig(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            endpoint=endpoint,
            bucket_name=bucket_name,
            region=region
        )
        return OSSService(oss_config_obj)
    except Exception as e:
        print(f"设置OSS失败: {str(e)}")
        return None


def setup_tingwu(config: Dict[str, Any]) -> Optional[TingwuService]:
    """
    设置通义听悟服务
    
    Args:
        config: 配置字典
        
    Returns:
        Optional[TingwuService]: 通义听悟服务对象
    """
    try:
        # 处理环境变量占位符
        tingwu_config = config.get('tingwu', {}).copy()
        for key, value in tingwu_config.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                tingwu_config[key] = os.environ.get(env_var, '')
        
        # 检查必要的配置
        access_key_id = tingwu_config.get('access_key_id', os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID', ''))
        access_key_secret = tingwu_config.get('access_key_secret', os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET', ''))
        app_key = tingwu_config.get('app_key', os.environ.get('TINGWU_APP_KEY', ''))
        region_id = tingwu_config.get('region_id', os.environ.get('TINGWU_REGION_ID', 'cn-beijing'))
        
        if not access_key_id or not access_key_secret:
            print("阿里云访问密钥未设置，请确保ALIBABA_CLOUD_ACCESS_KEY_ID和ALIBABA_CLOUD_ACCESS_KEY_SECRET环境变量已配置")
            return None
            
        if not app_key:
            print("通义听悟AppKey未设置，请确保TINGWU_APP_KEY环境变量已配置或在配置文件中设置")
            return None
        
        # 创建通义听悟服务
        tingwu_config_obj = TingwuConfig(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            app_key=app_key,
            region_id=region_id
        )
        return TingwuService(tingwu_config_obj)
    except Exception as e:
        print(f"设置通义听悟失败: {str(e)}")
        return None


def process_single_video(bvid: str, args: argparse.Namespace, 
                         video_processor: VideoProcessor) -> bool:
    """
    处理单个视频
    
    Args:
        bvid: 视频BV号
        args: 命令行参数
        video_processor: 视频处理器
        
    Returns:
        bool: 处理成功返回True，否则返回False
    """
    # 创建单个视频的任务管理器
    task_manager = TaskManager([bvid])
    task = task_manager.tasks[0]
    
    # 处理视频
    return video_processor.process_video(task, args)


def main() -> None:
    """主程序入口"""
    # 加载环境变量
    load_dotenv()
    
    # 解析命令行参数
    args = parse_arguments()
    
    # 加载配置
    config = load_config(args.config)
    
    # 获取BV号列表
    bvids = []
    if args.bvid:
        bvids = [args.bvid]
    elif args.bvid_file:
        try:
            bvids = read_bvid_list(args.bvid_file)
            print(f"从文件加载了 {len(bvids)} 个BV号")
        except Exception as e:
            print(f"加载BV号列表失败: {str(e)}")
            sys.exit(1)
    
    # 准备通用资源
    cookie = args.cookie or os.environ.get('BILIBILI_COOKIE', '') or config.get('bilibili', {}).get('cookie', '')
    chunk_size = config.get('bilibili', {}).get('chunk_size', 1024*1024)
    
    # 设置OSS服务
    print("设置OSS服务...")
    oss_service = setup_oss(config)
    if not oss_service:
        print("OSS服务设置失败，无法继续")
        sys.exit(1)
    
    # 设置通义听悟服务
    print("设置通义听悟服务...")
    tingwu_service = setup_tingwu(config)
    if not tingwu_service:
        print("通义听悟服务设置失败，无法继续")
        sys.exit(1)
    
    # 创建视频处理器
    video_processor = VideoProcessor(
        oss_service=oss_service,
        tingwu_service=tingwu_service,
        cookie=cookie,
        chunk_size=chunk_size
    )
    
    # 批量处理视频
    if len(bvids) == 1 and not args.pipeline:
        # 如果只有一个视频且不使用流水线模式，直接处理
        print(f"\n开始处理视频: {bvids[0]}")
        success = process_single_video(bvids[0], args, video_processor)
        print(f"\n处理完成: {'成功' if success else '失败'}")
    else:
        # 批量处理多个视频
        print(f"\n开始批量处理 {len(bvids)} 个视频...")
        
        # 创建任务管理器
        task_manager = TaskManager(bvids)
        
        # 创建状态显示服务
        display_service = StatusDisplayService(
            task_manager=task_manager,
            refresh_interval=args.refresh_interval,
            no_status_display=args.no_status_display
        )
        
        # 创建流水线服务
        pipeline_service = PipelineService(
            task_manager=task_manager,
            video_processor=video_processor,
            max_workers=args.max_concurrent,
            use_pipeline=args.pipeline
        )
        
        try:
            # 启动状态显示
            display_service.start()
            
            # 运行流水线处理
            pipeline_service.run(args)
            
        except KeyboardInterrupt:
            print("\n用户中断批处理")
        finally:
            # 停止状态显示
            display_service.stop()
            
        # 打印处理摘要
        display_service.print_summary(args.output_dir, os.path.basename(__file__))


if __name__ == "__main__":
    main() 