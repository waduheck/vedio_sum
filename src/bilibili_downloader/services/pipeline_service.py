#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
流水线服务类，负责处理视频处理任务的并发执行
"""
import os
import time
import threading
import queue
import argparse
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, List, Callable, Tuple, TYPE_CHECKING

# 使用TYPE_CHECKING来避免循环导入
if TYPE_CHECKING:
    from ..core.processor import VideoProcessor

from ..core.task_manager import TaskManager, VideoTask, TaskStatus


class PipelineService:
    """流水线服务，负责并发执行视频处理任务"""
    
    def __init__(
        self,
        task_manager: TaskManager,
        video_processor: "VideoProcessor",
        max_workers: int = 1,
        use_pipeline: bool = True
    ):
        """
        初始化流水线服务
        
        Args:
            task_manager: 任务管理器
            video_processor: 视频处理器
            max_workers: 最大并发工作线程数
            use_pipeline: 是否使用流水线模式（同时下载上传和监控）
        """
        self.task_manager = task_manager
        self.video_processor = video_processor
        self.max_workers = max(1, max_workers)
        self.use_pipeline = use_pipeline
    
    def process_upload_task(self, task: VideoTask, args: argparse.Namespace) -> bool:
        """
        处理上传任务
        
        Args:
            task: 视频任务
            args: 命令行参数
        
        Returns:
            bool: 处理成功返回True，否则返回False
        """
        try:
            success = self.video_processor.prepare_and_upload_video(task, args)
            
            if success:
                # 如果上传成功，将任务添加到处理队列
                self.task_manager.processing_queue.put(task)
            
            return success
        except Exception as e:
            error_msg = str(e)
            print(f"[{task.bvid}] 上传处理异常: {error_msg}")
            task.update_status(TaskStatus.FAILED, error_msg)
            return False
    
    def process_monitor_task(self, task: VideoTask, args: argparse.Namespace) -> bool:
        """
        处理监控任务
        
        Args:
            task: 视频任务
            args: 命令行参数
        
        Returns:
            bool: 处理成功返回True，否则返回False
        """
        try:
            return self.video_processor.monitor_task_progress(task, args)
        except Exception as e:
            error_msg = str(e)
            print(f"[{task.bvid}] 监控处理异常: {error_msg}")
            task.update_status(TaskStatus.FAILED, error_msg)
            return False
    
    def run(self, args: argparse.Namespace) -> bool:
        """
        运行流水线处理
        
        Args:
            args: 命令行参数
        
        Returns:
            bool: 处理成功返回True，否则返回False
        """
        try:
            print(f"使用 {self.max_workers} 个并发上传线程")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as upload_executor:
                if self.use_pipeline:
                    # 流水线模式：同时启动上传和监控线程
                    self._run_pipeline(args, upload_executor)
                else:
                    # 非流水线模式：先完成所有上传，再进行监控
                    self._run_sequential(args, upload_executor)
            
            return True
            
        except KeyboardInterrupt:
            print("\n用户中断批处理")
            self.task_manager.stop()
            return False
    
    def _run_pipeline(self, args: argparse.Namespace, upload_executor: ThreadPoolExecutor) -> None:
        """
        运行流水线模式
        
        Args:
            args: 命令行参数
            upload_executor: 上传任务的线程池
        """
        # 监控线程函数
        def monitor_worker():
            """监控工作线程"""
            with ThreadPoolExecutor(max_workers=self.max_workers) as monitor_executor:
                monitor_futures = set()
                
                while not self.task_manager.stop_event.is_set():
                    # 从处理队列获取任务
                    try:
                        while not self.task_manager.processing_queue.empty():
                            task = self.task_manager.processing_queue.get_nowait()
                            # 提交监控任务
                            future = monitor_executor.submit(self.process_monitor_task, task, args)
                            monitor_futures.add(future)
                            self.task_manager.processing_queue.task_done()
                    except queue.Empty:
                        pass
                    
                    # 清理已完成的future
                    done_futures = {f for f in monitor_futures if f.done()}
                    monitor_futures -= done_futures
                    
                    # 检查是否所有任务都已完成
                    if self.task_manager.is_all_done() and len(monitor_futures) == 0:
                        break
                    
                    # 等待一段时间再检查
                    time.sleep(1)
        
        # 启动监控线程
        monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
        monitor_thread.start()
        
        # 提交所有上传任务
        upload_futures = []
        for task in self.task_manager.tasks:
            future = upload_executor.submit(self.process_upload_task, task, args)
            upload_futures.append(future)
        
        # 等待所有上传任务完成
        for future in upload_futures:
            future.result()
        
        # 等待处理队列清空
        self.task_manager.processing_queue.join()
        
        # 等待监控线程完成
        monitor_thread.join()
    
    def _run_sequential(self, args: argparse.Namespace, upload_executor: ThreadPoolExecutor) -> None:
        """
        运行顺序模式
        
        Args:
            args: 命令行参数
            upload_executor: 上传任务的线程池
        """
        # 提交所有上传任务
        upload_futures = []
        for task in self.task_manager.tasks:
            future = upload_executor.submit(self.process_upload_task, task, args)
            upload_futures.append(future)
        
        # 等待所有上传任务完成
        for future in upload_futures:
            future.result()
        
        # 所有上传完成后，开始监控处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as monitor_executor:
            # 提交所有监控任务
            monitor_futures = []
            for task in self.task_manager.tasks:
                if task.status == TaskStatus.PROCESSING:
                    future = monitor_executor.submit(self.process_monitor_task, task, args)
                    monitor_futures.append(future)
            
            # 等待所有监控任务完成
            for future in monitor_futures:
                future.result() 