#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
显示服务类，负责显示处理任务的状态和进度
"""
import os
import time
import threading
from typing import Dict, Any, Optional

from ..core.task_manager import TaskManager, TaskStatus


class StatusDisplayService:
    """状态显示服务，负责实时显示任务状态"""
    
    def __init__(
        self, 
        task_manager: TaskManager,
        refresh_interval: float = 2.0,
        no_status_display: bool = False
    ):
        """
        初始化状态显示服务
        
        Args:
            task_manager: 任务管理器
            refresh_interval: 刷新间隔（秒）
            no_status_display: 是否禁用状态显示
        """
        self.task_manager = task_manager
        self.refresh_interval = refresh_interval
        self.no_status_display = no_status_display
        self.display_thread = None
        self.stop_event = task_manager.stop_event
    
    def start(self) -> None:
        """
        启动状态显示线程
        """
        if self.no_status_display:
            return
            
        self.display_thread = threading.Thread(target=self._display_status_thread, daemon=True)
        self.display_thread.start()
    
    def _display_status_thread(self) -> None:
        """状态显示线程的主函数"""
        while not self.stop_event.is_set():
            # 清空屏幕
            os.system('cls' if os.name == 'nt' else 'clear')
            
            # 获取任务计数
            counts = self.task_manager.get_task_counts()
            total_videos = counts['total']
            
            # 显示总体进度
            print(f"\n总进度: {counts['completed']+counts['failed']}/{total_videos} ({(counts['completed']+counts['failed'])/total_videos:.1%})")
            print(f"待处理: {counts['pending']} | 下载中: {counts['downloading']} | 上传中: {counts['uploading']} | "
                  f"处理中: {counts['processing']} | 完成: {counts['completed']} | 失败: {counts['failed']}")
            
            # 显示各任务状态
            for task in sorted(self.task_manager.tasks, key=lambda t: t.index):
                print(task.get_progress_str())
            
            # 等待一段时间再刷新
            time.sleep(self.refresh_interval)
    
    def stop(self) -> None:
        """
        停止状态显示
        """
        if self.display_thread and self.display_thread.is_alive():
            self.display_thread.join(timeout=2)
    
    def print_summary(self, output_dir: str, script_name: str) -> None:
        """
        打印处理完成的摘要信息
        
        Args:
            output_dir: 输出目录
            script_name: 脚本名称，用于生成重试命令
        """
        # 获取完成情况摘要
        summary = self.task_manager.get_completion_summary()
        
        # 打印总结
        print("\n批处理完成!")
        print(f"总计: {summary['total']} 个视频")
        print(f"成功: {summary['completed']} 个")
        print(f"失败: {summary['failed']} 个")
        
        # 如果有失败的任务，显示详情
        if summary['failed'] > 0:
            failed_bvids = summary['failed_bvids']
            print("失败的BV号:")
            for bvid in failed_bvids:
                print(f"  - {bvid}")
            
            # 创建失败BV号列表文件，方便重试
            if failed_bvids:
                self._save_failed_bvids(output_dir, script_name, failed_bvids)
    
    def _save_failed_bvids(self, output_dir: str, script_name: str, failed_bvids: list) -> None:
        """
        保存失败的BV号到文件
        
        Args:
            output_dir: 输出目录
            script_name: 脚本名称
            failed_bvids: 失败的BV号列表
        """
        failed_file = os.path.join(output_dir, "failed_bvids.txt")
        with open(failed_file, 'w', encoding='utf-8') as f:
            for bvid in failed_bvids:
                f.write(f"{bvid}\n")
        print(f"失败的BV号列表已保存到: {failed_file}")
        print(f"可以使用以下命令重试失败的视频:")
        print(f"python {script_name} --bvid-file {failed_file}") 