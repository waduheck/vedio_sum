#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
阿里云OSS服务封装
"""
from typing import Optional
import os
import oss2
from oss2.credentials import EnvironmentVariableCredentialsProvider
from oss2.auth import ProviderAuthV4
from pydantic import BaseModel
from ..exceptions import OSSError

class OSSConfig(BaseModel):
    """OSS配置模型"""
    access_key_id: str
    access_key_secret: str
    endpoint: str
    bucket_name: str
    region: str = ""  # 新增region参数，用于v4签名

class OSSService:
    """阿里云OSS服务封装"""
    
    def __init__(self, config: OSSConfig):
        """
        初始化OSS服务
        
        Args:
            config: OSS配置对象
        """
        self.config = config
        self._init_bucket()

    def _init_bucket(self) -> None:
        """初始化OSS Bucket连接"""
        # 检查是否使用v4签名
        if self.config.region:
            try:
                # 使用v4签名
                auth = ProviderAuthV4(EnvironmentVariableCredentialsProvider())
                self.bucket = oss2.Bucket(
                    auth,
                    f"https://{self.config.endpoint}",
                    self.config.bucket_name,
                    region=self.config.region
                )
            except (ImportError, AttributeError):
                # 如果v4签名不可用，回退到v2签名
                print("警告: v4签名不可用，使用v2签名")
                self._init_bucket_v2()
        else:
            # 使用v2签名
            self._init_bucket_v2()

    def _init_bucket_v2(self) -> None:
        """使用v2签名初始化OSS Bucket连接"""
        auth = oss2.Auth(
            self.config.access_key_id,
            self.config.access_key_secret
        )
        self.bucket = oss2.Bucket(
            auth,
            f"https://{self.config.endpoint}",
            self.config.bucket_name
        )

    def upload_file(
        self,
        local_path: str,
        object_name: Optional[str] = None,
        expire_seconds: int = 3600
    ) -> str:
        """
        上传文件到OSS并生成临时URL
        
        Args:
            local_path: 本地文件路径
            object_name: OSS对象名称，可选
            expire_seconds: URL有效期（秒）
            
        Returns:
            str: 临时访问URL
            
        Raises:
            OSSError: OSS操作失败时抛出
        """
        if not os.path.exists(local_path):
            raise OSSError(f"文件不存在: {local_path}")
            
        if not object_name:
            object_name = os.path.basename(local_path)
            
        try:
            # 上传文件
            self.bucket.put_object_from_file(object_name, local_path)
            
            # 生成临时URL
            url = self.bucket.sign_url('GET', object_name, expire_seconds, slash_safe=True)
            return url
        except oss2.exceptions.OssError as e:
            raise OSSError(f"OSS操作失败: {str(e)}", original_error=e)
        except Exception as e:
            raise OSSError(f"未知错误: {str(e)}", original_error=e)

    def get_file_url(
        self,
        object_name: str,
        expire_seconds: int = 3600
    ) -> str:
        """
        获取OSS文件的临时访问URL
        
        Args:
            object_name: OSS对象名称
            expire_seconds: URL有效期（秒）
            
        Returns:
            str: 临时访问URL
            
        Raises:
            OSSError: OSS操作失败时抛出
        """
        try:
            # 检查文件是否存在
            if not self.bucket.object_exists(object_name):
                raise OSSError(f"文件不存在: {object_name}")
            
            # 生成临时URL
            url = self.bucket.sign_url('GET', object_name, expire_seconds, slash_safe=True)
            return url
        except oss2.exceptions.OssError as e:
            raise OSSError(f"获取URL失败: {str(e)}", original_error=e)
        except Exception as e:
            raise OSSError(f"未知错误: {str(e)}", original_error=e)
            
    def delete_object(self, object_name: str) -> None:
        """
        删除OSS对象
        
        Args:
            object_name: OSS对象名称
            
        Raises:
            OSSError: OSS操作失败时抛出
        """
        try:
            self.bucket.delete_object(object_name)
        except oss2.exceptions.OssError as e:
            raise OSSError(f"删除对象失败: {str(e)}", original_error=e) 