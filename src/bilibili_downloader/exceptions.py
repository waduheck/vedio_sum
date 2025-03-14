from typing import Optional


class BilibiliDownloaderError(Exception):
    """所有下载器相关异常的基类"""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """
        初始化异常
        
        Args:
            message: 错误消息
            original_error: 原始异常对象，可选
        """
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


class APIError(BilibiliDownloaderError):
    """API请求错误"""
    pass


class DownloadError(BilibiliDownloaderError):
    """视频下载错误"""
    pass


class OSSError(BilibiliDownloaderError):
    """OSS操作错误"""
    pass 