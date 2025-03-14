#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
视频处理器类，负责处理视频的下载、上传和处理逻辑
"""
import os
import time
import argparse
import traceback
from typing import Dict, Any, Optional, List, Tuple, Set, Union, TYPE_CHECKING, Callable

# 使用TYPE_CHECKING避免循环导入
if TYPE_CHECKING:
    from ..services import OSSService
    from ..services.tingwu_service import TingwuService

from .task_manager import VideoTask, TaskStatus
from . import BiliVideoDownloader


class VideoProcessor:
    """视频处理器，负责处理视频的下载、上传和结果处理"""
    
    def __init__(
        self,
        oss_service: "OSSService",
        tingwu_service: "TingwuService",
        cookie: str,
        chunk_size: int = 1024*1024
    ):
        """
        初始化视频处理器
        
        Args:
            oss_service: OSS服务对象
            tingwu_service: 通义听悟服务对象
            cookie: B站Cookie
            chunk_size: 下载块大小，默认1MB
        """
        self.oss_service = oss_service
        self.tingwu_service = tingwu_service
        self.cookie = cookie
        self.chunk_size = chunk_size
    
    def _handle_exception(self, task: VideoTask, msg_prefix: str, error: Exception) -> bool:
        """
        统一处理异常
        
        Args:
            task: 视频任务对象
            msg_prefix: 错误信息前缀
            error: 异常对象
            
        Returns:
            bool: 始终返回False表示处理失败
        """
        error_msg = str(error)
        print(f"[{task.bvid}] {msg_prefix}: {error_msg}")
        traceback.print_exc()
        task.update_status(TaskStatus.FAILED, error_msg)
        return False

    def _wrap_exception_handler(self, task: VideoTask, fn: Callable, msg_prefix: str, *args, **kwargs) -> bool:
        """
        异常处理包装器
        
        Args:
            task: 视频任务对象
            fn: 要包装的函数
            msg_prefix: 错误信息前缀
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            bool: 处理结果，成功为True，失败为False
        """
        try:
            return fn(*args, **kwargs)
        except KeyboardInterrupt:
            raise  # 重新抛出键盘中断
        except Exception as e:
            return self._handle_exception(task, msg_prefix, e)
    
    def prepare_and_upload_video(self, task: VideoTask, args: argparse.Namespace) -> bool:
        """
        准备并上传视频到听悟服务
        
        Args:
            task: 视频任务对象
            args: 命令行参数
            
        Returns:
            bool: 处理成功返回True，否则返回False
        """
        bvid = task.bvid
        try:
            print(f"\n{'='*20} 开始处理视频: {bvid} {'='*20}")
            
            # 1. 下载B站视频
            task.update_status(TaskStatus.DOWNLOADING)
            print(f"[{bvid}] 开始下载B站视频")
            
            # 初始化下载器
            downloader = BiliVideoDownloader(cookie=self.cookie)
            
            # 获取视频信息
            print(f"[{bvid}] 获取视频信息...")
            video_info = downloader.get_video_info(bvid)
            task.video_info = video_info
            print(f"[{bvid}] 视频标题: {video_info.title}")
            
            # 获取下载地址
            cid = video_info.cid
            print(f"[{bvid}] 获取下载地址, 质量: {args.quality}")
            url = downloader.get_download_url(bvid, cid, args.quality)
            
            # 下载视频
            output_path = args.output.format(bvid=bvid)
            print(f"[{bvid}] 开始下载到: {output_path}")
            local_path = downloader.download_video(url, output_path, self.chunk_size)
            task.local_path = local_path
            
            # 2. 上传文件到OSS
            task.update_status(TaskStatus.UPLOADING)
            print(f"[{bvid}] 开始上传文件到OSS: {local_path}")
            object_name = f"videos/{bvid}_{os.path.basename(local_path)}"
            oss_url = self.oss_service.upload_file(local_path, object_name, expire_seconds=10800)  # 3小时有效期
            task.oss_url = oss_url
            print(f"[{bvid}] 上传成功，临时URL有效期3小时")
            
            # 清理本地文件（如果不需要保留）
            if not args.keep:
                os.remove(local_path)
                print(f"[{bvid}] 已删除本地文件: {local_path}")
            
            # 3. 提交通义听悟任务
            print(f"[{bvid}] 提交文件到通义听悟进行处理...")
            task_id = self.tingwu_service.create_task(
                file_url=oss_url,
                source_language=args.language_type,
                enable_summary=True,
                enable_timestamp=True,
                enable_diarization=args.enable_diarization,
                speaker_count=args.speaker_count,
                enable_translation=False,
                enable_auto_chapters=args.enable_chapters,
                enable_meeting_assistance=args.enable_meeting,
                enable_ppt_extraction=args.enable_ppt,
                enable_text_polish=args.enable_polish
            )
            task.task_id = task_id
            print(f"[{bvid}] 提交成功，任务ID: {task_id}")
            
            # 更新状态为处理中
            task.update_status(TaskStatus.PROCESSING)
            return True
                
        except Exception as e:
            return self._handle_exception(task, "准备和上传失败", e)

    def monitor_task_progress(self, task: VideoTask, args: argparse.Namespace) -> bool:
        """
        监控任务进度并处理结果
        
        Args:
            task: 视频任务对象
            args: 命令行参数
            
        Returns:
            bool: 处理成功返回True，否则返回False
        """
        bvid = task.bvid
        task_id = task.task_id
        
        if not task_id:
            error_msg = "任务ID为空，无法监控进度"
            print(f"[{bvid}] {error_msg}")
            task.update_status(TaskStatus.FAILED, error_msg)
            return False
        
        try:
            # 4. 跟踪任务状态
            print(f"[{bvid}] 开始跟踪任务状态: {task_id}")
            
            # 使用wait_for_result方法等待结果
            start_time = time.time()
            result = self.tingwu_service.wait_for_result(
                task_id=task_id,
                timeout=10800,  # 3小时超时
                interval=args.interval
            )
            elapsed_time = int(time.time() - start_time)
            print(f"[{bvid}] 任务处理完成! 总耗时: {elapsed_time}秒")
            
            # 5. 处理结果
            self._process_results(task, args, task_id)
            
            print(f"[{bvid}] 处理完成")
            task.update_status(TaskStatus.COMPLETED)
            return True
            
        except KeyboardInterrupt:
            print(f"\n[{bvid}] 用户中断跟踪")
            print(f"[{bvid}] 您可以稍后使用以下命令查询此任务状态:")
            print(f"python {os.path.basename(__file__)} --track-task-id {task_id}")
            task.update_status(TaskStatus.FAILED, "用户中断")
            raise  # 重新抛出中断异常，让主程序处理
            
        except Exception as e:
            return self._handle_exception(task, "监控进度失败", e)
    
    def _process_results(self, task: VideoTask, args: argparse.Namespace, task_id: str) -> None:
        """
        处理任务结果
        
        Args:
            task: 视频任务对象
            args: 命令行参数
            task_id: 任务ID
        """
        bvid = task.bvid
        print(f"[{bvid}] 处理结果...")
        filename_prefix = f"{bvid}_{task.video_info.title if task.video_info else bvid}"
        # 替换文件名中的非法字符
        filename_prefix = "".join(c for c in filename_prefix if c.isalnum() or c in "._- ")
        
        # 确保输出目录存在
        output_dir = os.path.join(args.output_dir, bvid)
        os.makedirs(output_dir, exist_ok=True)
        
        # 处理结果
        output_files = self.tingwu_service.process_results(
            task_id=task_id,
            output_dir=output_dir,
            filename_prefix=filename_prefix,
            formats=["json", "transcription", "paragraph"]
        )
        
        # 显示摘要内容
        summary_file = output_files.get("summary")
        if summary_file and os.path.exists(summary_file):
            print(f"[{bvid}] 摘要内容:")
            print("-" * 50)
            with open(summary_file, 'r', encoding='utf-8') as f:
                summary = f.read()
                print(summary)
            print("-" * 50)
        else:
            print(f"[{bvid}] 未找到摘要结果")
    
    def process_video(self, task: VideoTask, args: argparse.Namespace) -> bool:
        """
        处理单个视频，从下载到上传到获取摘要
        
        Args:
            task: 视频任务对象
            args: 命令行参数
            
        Returns:
            bool: 处理成功返回True，否则返回False
        """
        # 上传视频
        if not self.prepare_and_upload_video(task, args):
            return False
        
        # 监控进度
        return self.monitor_task_progress(task, args) 