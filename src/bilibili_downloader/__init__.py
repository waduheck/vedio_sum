"""
B站视频下载和处理模块

这个模块提供了与B站视频下载、OSS上传和通义听悟API交互的功能
"""

__version__ = "0.1.0"

# 导出主要类和函数，方便用户导入
from .core.downloader import BiliVideoDownloader
from .core.models import VideoInfo
from .core.task_manager import TaskManager, VideoTask, TaskStatus
from .core.processor import VideoProcessor
from .services.oss_service import OSSService, OSSConfig
from .services.tingwu_service import TingwuService, TingwuConfig
from .services.display_service import StatusDisplayService
from .services.pipeline_service import PipelineService
from .exceptions import BilibiliDownloaderError, APIError, DownloadError, OSSError
from .config import load_config
