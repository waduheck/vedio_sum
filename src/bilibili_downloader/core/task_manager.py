#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
任务管理相关类，负责管理视频处理任务的状态和生命周期
"""
import time
import threading
import queue
from typing import Dict, Any, Optional, List, Set, Tuple


class TaskStatus:
    """任务状态枚举"""
    PENDING = "待处理"
    DOWNLOADING = "下载中"
    UPLOADING = "上传中"
    PROCESSING = "处理中"
    COMPLETED = "已完成"
    FAILED = "失败"


class VideoTask:
    """视频处理任务"""
    def __init__(self, bvid: str, index: int, total: int):
        """
        初始化视频处理任务
        
        Args:
            bvid: 视频BV号
            index: 任务索引
            total: 总任务数
        """
        self.bvid = bvid
        self.index = index
        self.total = total
        self.status = TaskStatus.PENDING
        self.task_id = None
        self.video_info = None
        self.local_path = None
        self.oss_url = None
        self.error = None
        self.start_time = time.time()
        self.processing_start_time = None
        self.end_time = None
        self.lock = threading.Lock()
        
    def update_status(self, status: str, error: Optional[str] = None) -> None:
        """
        更新任务状态
        
        Args:
            status: 新状态
            error: 错误信息（如果有）
        """
        with self.lock:
            self.status = status
            if error:
                self.error = error
            
            if status == TaskStatus.PROCESSING and not self.processing_start_time:
                self.processing_start_time = time.time()
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                self.end_time = time.time()
    
    def get_progress_str(self) -> str:
        """
        获取进度字符串
        
        Returns:
            str: 进度字符串
        """
        elapsed = int(time.time() - self.start_time)
        progress = f"[{self.index}/{self.total}] BV: {self.bvid} | 状态: {self.status}"
        
        if self.status == TaskStatus.PROCESSING and self.processing_start_time:
            processing_elapsed = int(time.time() - self.processing_start_time)
            progress += f" | 处理时间: {processing_elapsed}秒"
        elif self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            total_elapsed = int(self.end_time - self.start_time)
            progress += f" | 总耗时: {total_elapsed}秒"
            
            if self.error:
                progress += f" | 错误: {self.error}"
        else:
            progress += f" | 耗时: {elapsed}秒"
            
        return progress


class TaskManager:
    """任务管理器，负责管理所有视频处理任务"""
    
    def __init__(self, bvids: List[str]):
        """
        初始化任务管理器
        
        Args:
            bvids: 要处理的视频BV号列表
        """
        self.bvids = bvids
        self.total_videos = len(bvids)
        self.tasks = []
        self.task_queue = queue.Queue()
        self.processing_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        # 初始化任务
        for index, bvid in enumerate(bvids, 1):
            task = VideoTask(bvid, index, self.total_videos)
            self.tasks.append(task)
            self.task_queue.put(task)
    
    def get_task_by_bvid(self, bvid: str) -> Optional[VideoTask]:
        """
        根据BV号获取任务
        
        Args:
            bvid: 视频BV号
            
        Returns:
            Optional[VideoTask]: 找到的任务，如果没有找到则返回None
        """
        for task in self.tasks:
            if task.bvid == bvid:
                return task
        return None
    
    def get_task_counts(self) -> Dict[str, int]:
        """
        获取各状态的任务数量
        
        Returns:
            Dict[str, int]: 状态到任务数量的映射
        """
        return {
            'pending': sum(1 for t in self.tasks if t.status == TaskStatus.PENDING),
            'downloading': sum(1 for t in self.tasks if t.status == TaskStatus.DOWNLOADING),
            'uploading': sum(1 for t in self.tasks if t.status == TaskStatus.UPLOADING),
            'processing': sum(1 for t in self.tasks if t.status == TaskStatus.PROCESSING),
            'completed': sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED),
            'failed': sum(1 for t in self.tasks if t.status == TaskStatus.FAILED),
            'total': self.total_videos
        }
    
    def get_failed_bvids(self) -> List[str]:
        """
        获取处理失败的BV号列表
        
        Returns:
            List[str]: 失败的BV号列表
        """
        return [t.bvid for t in self.tasks if t.status == TaskStatus.FAILED]
    
    def is_all_done(self) -> bool:
        """
        检查是否所有任务都已完成（成功或失败）
        
        Returns:
            bool: 如果所有任务都已完成，返回True
        """
        return all(t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED] for t in self.tasks)
    
    def get_completion_summary(self) -> Dict[str, Any]:
        """
        获取完成情况摘要
        
        Returns:
            Dict[str, Any]: 包含完成情况的字典
        """
        counts = self.get_task_counts()
        failed_bvids = self.get_failed_bvids()
        
        return {
            'total': self.total_videos,
            'completed': counts['completed'],
            'failed': counts['failed'],
            'failed_bvids': failed_bvids
        }
    
    def stop(self) -> None:
        """停止所有任务处理"""
        self.stop_event.set() 