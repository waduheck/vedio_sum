#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将OSS上的视频提交给通义听悟API进行处理
"""
import os
import sys
import json
import argparse
import yaml
import time
import datetime
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from dotenv import load_dotenv
import traceback

# 添加上级目录到路径，方便直接运行示例
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bilibili_downloader.services.tingwu_service import TingwuService, TingwuConfig
from src.bilibili_downloader.services.oss_service import OSSService, OSSConfig
from src.bilibili_downloader.exceptions import APIError, OSSError


def parse_arguments() -> argparse.Namespace:
    """
    解析命令行参数
    
    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(description="OSS转写工具")
    parser.add_argument("--oss-bucket", type=str, help="OSS bucket名称")
    parser.add_argument("--oss-key", type=str, help="OSS key")
    parser.add_argument("--local-file", type=str, help="本地文件路径")
    parser.add_argument("--language-type", type=str, default="auto", help="语言类型")
    parser.add_argument("--track-task-id", type=str, help="要跟踪的任务ID")
    parser.add_argument("--interval", type=float, default=2.0, help="查询间隔(秒)")
    parser.add_argument("--output-dir", type=str, default="output", help="输出目录")
    parser.add_argument("--format", type=str, default="all", choices=["all", "json", "paragraph"])

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


def setup_oss(config: Dict[str, Any]) -> Optional[OSSService]:
    """
    设置OSS服务
    
    Args:
        config: 配置字典
        
    Returns:
        Optional[OSSService]: OSS服务对象
    """
    if 'oss' not in config:
        return None
        
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
        return OSSService(OSSConfig(**oss_config))
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
    if 'tingwu' not in config:
        print("未找到tingwu配置")
        return None
        
    try:
        # 处理环境变量占位符
        tingwu_config = config['tingwu'].copy()
        for key, value in tingwu_config.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                env_value = os.environ.get(env_var, '')
                tingwu_config[key] = env_value
                print(f"从环境变量获取 {key}: 长度 = {len(env_value) if env_value else 0}")
        
        # 检查必要的配置
        if not tingwu_config.get('access_key_id') or not tingwu_config.get('access_key_secret'):
            print("通义听悟访问密钥未设置，请确保TINGWU_ACCESS_KEY_ID和TINGWU_ACCESS_KEY_SECRET环境变量已配置")
            return None
        
        print(f"设置听悟服务: AK长度={len(tingwu_config['access_key_id'])}, SK长度={len(tingwu_config['access_key_secret'])}")
        
        # 创建通义听悟服务
        return TingwuService(TingwuConfig(**tingwu_config))
    except Exception as e:
        print(f"设置通义听悟失败: {str(e)}")
        return None


def get_video_url(oss_service: OSSService, object_name: str, expire_seconds: int) -> str:
    """
    获取OSS视频的URL
    
    Args:
        oss_service: OSS服务对象
        object_name: 对象名称
        expire_seconds: URL有效期（秒）
        
    Returns:
        str: 视频URL
        
    Raises:
        OSSError: 获取URL失败时抛出
    """
    try:
        url = oss_service.get_file_url(object_name, expire_seconds)
        print(f"已生成OSS临时访问URL，有效期{expire_seconds}秒")
        return url
    except OSSError as e:
        raise e


def track_task_status(tingwu_service: TingwuService, task_id: str, interval: int = 30) -> Dict[str, Any]:
    """
    定期查询任务状态直到任务完成
    
    Args:
        tingwu_service: 通义听悟服务对象
        task_id: 任务ID
        interval: 查询间隔（秒）
        
    Returns:
        Dict[str, Any]: 任务结果
        
    Raises:
        APIError: API请求失败时抛出
    """
    print(f"开始定期跟踪任务状态: TaskId={task_id}, 间隔={interval}秒")
    print("(按Ctrl+C可随时中断)")
    
    start_time = time.time()
    retry_count = 0
    max_retries = 5  # 增加最大重试次数
    base_backoff = 5  # 基础退避时间（秒）
    
    try:
        last_status = "UNKNOWN"
        
        while True:
            try:
                # 获取任务结果
                response = tingwu_service.get_task_result(task_id)
                
                # 检查响应格式
                if response.get("Code") != "0" or "success" not in response.get("Message", "").lower():
                    print(f"API响应异常: {json.dumps(response)}")
                    retry_count += 1
                    if retry_count >= max_retries:
                        raise APIError(f"连续{max_retries}次获取任务状态失败")
                        
                    # 指数退避
                    backoff_time = base_backoff * (2 ** (retry_count - 1))
                    print(f"将在 {backoff_time} 秒后重试 (尝试 {retry_count}/{max_retries})...")
                    time.sleep(backoff_time)
                    continue
                
                # 重置重试计数
                retry_count = 0
                
                # 提取任务数据和状态
                data = response.get("Data", {})
                status = data.get("TaskStatus", "UNKNOWN")
                
                # 如果状态有变化，打印更详细的信息
                if status != last_status:
                    print(f"任务状态变化: {last_status} -> {status}")
                    last_status = status
                
                # 格式化任务持续时间
                elapsed_time = int(time.time() - start_time)
                hours, remainder = divmod(elapsed_time, 3600)
                minutes, seconds = divmod(remainder, 60)
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                
                # 检查任务状态
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{current_time}] 任务状态: {status}, 已运行: {time_str}")
                
                # 通义听悟API返回的成功状态是"COMPLETED"，不是"FINISHED"
                if status.upper() == "COMPLETED" or status.upper() == "FINISHED":
                    print(f"任务处理完成! 总耗时: {time_str}")
                    
                    # 检查结果数据
                    if 'Results' in data:
                        result_types = [r.get('Type', 'Unknown') for r in data.get('Results', [])]
                        print(f"结果类型: {result_types}")
                    
                    return response
                elif status.upper() == "FAILED":
                    error_msg = data.get("ErrorMessage", "未知错误")
                    raise APIError(f"任务处理失败: {error_msg}")
                    
                # 等待下一次查询
                time.sleep(interval)
                
            except APIError:
                # 重新抛出API错误
                raise
            except (ConnectionError, ConnectionResetError, ConnectionAbortedError, ConnectionRefusedError) as e:
                # 网络连接错误，需要退避并重试
                retry_count += 1
                print(f"网络连接错误: {str(e)}")
                
                if retry_count >= max_retries:
                    raise APIError(f"连续{max_retries}次网络连接失败，请检查网络环境")
                
                # 指数退避
                backoff_time = base_backoff * (2 ** (retry_count - 1))
                print(f"将在 {backoff_time} 秒后重试 (尝试 {retry_count}/{max_retries})...")
                time.sleep(backoff_time)
            except Exception as e:
                # 记录其它错误但继续尝试
                print(f"查询过程中出错: {str(e)}")
                retry_count += 1
                
                if retry_count >= max_retries:
                    raise APIError(f"连续{max_retries}次查询出错")
                
                # 指数退避
                backoff_time = base_backoff * (2 ** (retry_count - 1))
                print(f"将在 {backoff_time} 秒后重试 (尝试 {retry_count}/{max_retries})...")
                time.sleep(backoff_time)
                
    except KeyboardInterrupt:
        # 用户中断，显示最后状态
        print("\n用户中断跟踪。最后已知状态信息:")
        try:
            response = tingwu_service.get_task_result(task_id)
            data = response.get("Data", {})
            status = data.get("TaskStatus", "UNKNOWN")
            
            # 格式化运行时间
            elapsed_time = int(time.time() - start_time)
            hours, remainder = divmod(elapsed_time, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            print(f"任务ID: {task_id}, 状态: {status}, 已运行: {time_str}")
            print("可以稍后使用以下命令继续跟踪:")
            print(f"python {os.path.basename(__file__)} --track-task-id {task_id}")
            return response
        except Exception as e:
            print(f"获取最终状态时出错: {str(e)}")
            raise APIError(f"任务跟踪被中断，最后状态未知: {str(e)}")


def submit_transcription_task(
    tingwu_service: TingwuService, 
    file_path: str, 
    language_type: str = "auto"
) -> str:
    """
    提交转写任务
    
    Args:
        tingwu_service: 通义听悟服务实例
        file_path: 文件路径或URL
        language_type: 语言类型
        
    Returns:
        str: 任务ID
    """
    print(f"正在提交转写任务: {file_path}")
    task_id = tingwu_service.submit_task(file_path, language_type=language_type)
    print(f"任务已提交，任务ID: {task_id}")
    return task_id


def process_transcription_results(
    tingwu_service: TingwuService, 
    task_id: str,
    output_dir: str,
    filename_prefix: str,
    formats: List[str]
) -> Optional[Dict[str, str]]:
    """
    处理转写结果
    
    Args:
        tingwu_service: 通义听悟服务实例
        task_id: 任务ID
        output_dir: 输出目录
        filename_prefix: 文件名前缀
        formats: 输出格式列表
        
    Returns:
        Optional[Dict[str, str]]: 格式到文件路径的映射，如果处理失败则返回None
    """
    try:
        print(f"正在处理任务 {task_id} 的结果")
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 使用服务的process_results方法处理结果
        result_files = tingwu_service.process_results(
            task_id=task_id,
            output_dir=output_dir,
            filename_prefix=filename_prefix,
            formats=formats
        )
        
        print("处理完成！")
        return result_files
        
    except Exception as e:
        print(f"处理转写结果时出错: {str(e)}")
        traceback.print_exc()
        return None


def get_file_info(args: argparse.Namespace, config: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    获取文件信息，包括文件路径和文件名前缀
    
    Args:
        args: 命令行参数
        config: 配置信息
        
    Returns:
        Tuple[Optional[str], Optional[str]]: (文件路径, 文件名前缀)，如果获取失败则返回(None, None)
    """
    # 从本地文件或OSS上传文件
    if args.local_file:
        print(f"使用本地文件: {args.local_file}")
        file_path = args.local_file
        filename = os.path.basename(args.local_file)
        filename_prefix = os.path.splitext(filename)[0]
        return file_path, filename_prefix
        
    elif args.oss_bucket and args.oss_key:
        print(f"使用OSS文件: {args.oss_bucket}/{args.oss_key}")
        # 获取临时URL
        oss_service = setup_oss(config)
        if not oss_service:
            print("未配置OSS服务，无法获取文件URL")
            return None, None
        
        # 获取视频URL
        print(f"正在从OSS获取对象: {args.oss_key}")
        file_path = get_video_url(oss_service, args.oss_key, 10800)
        filename = os.path.basename(args.oss_key)
        filename_prefix = os.path.splitext(filename)[0]
        return file_path, filename_prefix
        
    else:
        print("错误: 请提供本地文件路径或OSS文件信息")
        return None, None


def main() -> None:
    """主程序入口"""
    # 加载环境变量
    load_dotenv()
    
    # 解析命令行参数
    args = parse_arguments()
    
    # 加载配置文件
    config = load_config(str(Path(__file__).parent.parent / 'config' / 'config.yaml'))
    
    try:
        # 设置通义听悟服务
        tingwu_service = setup_tingwu(config)
        if not tingwu_service:
            print("未配置通义听悟服务，无法继续处理")
            sys.exit(1)
            
        # 确定输出格式
        formats = []
        if args.format == "all":
            formats = ["json", "transcription","paragraph"]
        else:
            formats = [args.format]
            
        # 如果是跟踪现有任务
        if args.track_task_id:
            print(f"跟踪现有任务: {args.track_task_id}")
            
            # 定期查询任务状态
            result = track_task_status(tingwu_service, args.track_task_id, args.interval)
            
            # 如果任务已完成，处理结果
            task_status = result.get("Data", {}).get("TaskStatus", "").upper()
            if task_status in ["COMPLETED", "FINISHED"]:
                # 处理并保存结果
                filename_prefix = f"task_{args.track_task_id}"
                process_transcription_results(
                    tingwu_service=tingwu_service,
                    task_id=args.track_task_id,
                    output_dir=args.output_dir,
                    filename_prefix=filename_prefix,
                    formats=formats
                )
            else:
                print(f"任务未完成，当前状态: {task_status}")
            
            return
        
        # 获取文件信息
        file_path, filename_prefix = get_file_info(args, config)
        if not file_path or not filename_prefix:
            print("无法获取文件信息，退出")
            sys.exit(1)
            
        # 提交转写任务
        task_id = submit_transcription_task(
            tingwu_service=tingwu_service,
            file_path=file_path,
            language_type=args.language_type
        )
        
        # 打印任务跟踪命令提示
        print("\n您可以随时使用以下命令查询此任务状态:")
        print(f"python {os.path.basename(__file__)} --track-task-id {task_id} --interval {args.interval}")
        
        # 跟踪并处理任务
        response = input("\n是否立即开始跟踪任务状态? [y/N]: ")
        if response.lower() == 'y':
            # 跟踪任务状态
            try:
                result = track_task_status(tingwu_service, task_id, args.interval)
                
                # 如果任务已完成，处理结果
                task_status = result.get("Data", {}).get("TaskStatus", "").upper()
                if task_status in ["COMPLETED", "FINISHED"]:
                    # 处理并保存结果
                    process_transcription_results(
                        tingwu_service=tingwu_service,
                        task_id=task_id,
                        output_dir=args.output_dir,
                        filename_prefix=filename_prefix,
                        formats=formats
                    )
                else:
                    print(f"任务未完成，当前状态: {task_status}")
            except Exception as e:
                print(f"跟踪任务状态时出错: {str(e)}")
                traceback.print_exc()
        else:
            print("\n您可以稍后使用上述命令查询任务状态和获取结果")
            
    except Exception as e:
        print(f"处理过程中出现错误: {str(e)}")
        traceback.print_exc()


if __name__ == "__main__":
    main() 