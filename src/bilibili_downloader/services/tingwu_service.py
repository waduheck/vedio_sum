#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
通义听悟API调用模块
"""
from typing import Dict, Any, Optional, List, Union
import os
import time
import json
import datetime
import requests
import traceback
from pydantic import BaseModel, Field
from ..exceptions import APIError
import re

# 阿里云SDK导入
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from aliyunsdkcore.auth.credentials import AccessKeyCredential
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException

# 全局设置阿里云SDK超时（如果SDK支持这种方式）
# 这些设置可能不适用于所有版本的SDK，如果仍然出错，可以尝试其他方法
try:
    import aliyunsdkcore.vendored.requests as requests
    # 尝试设置全局超时
    requests.adapters.DEFAULT_RETRIES = 3
    # 设置连接和读取超时（秒）
    requests.adapters.DEFAULT_TIMEOUT = (10, 30)
except (ImportError, AttributeError):
    print("警告: 无法设置阿里云SDK全局超时参数")


class TingwuConfig(BaseModel):
    """通义听悟配置模型"""
    app_key: str = Field(..., description="通义听悟项目的AppKey")
    access_key_id: str = Field(..., description="阿里云访问密钥ID")
    access_key_secret: str = Field(..., description="阿里云访问密钥Secret")
    region_id: str = Field("cn-beijing", description="服务区域ID，默认为cn-beijing")


class TingwuService:
    """通义听悟服务封装"""
    
    def __init__(self, config: TingwuConfig):
        """
        初始化通义听悟服务
        
        Args:
            config: 通义听悟配置对象
        """
        self.config = config
        self.domain = "tingwu.cn-beijing.aliyuncs.com"
        self.version = "2023-09-30"
        self.protocol_type = "https"
        
        # 显式打印凭证信息以便调试（不包含敏感信息）
        print(f"初始化通义听悟服务: 区域={config.region_id}, AppKey={config.app_key}, AccessKeyID长度={len(config.access_key_id) if config.access_key_id else 0}")
        
        # 超时设置（秒）
        self.connect_timeout = 10
        self.read_timeout = 30
        
        # 初始化阿里云客户端
        # 直接使用配置中的访问凭证，不再依赖环境变量
        credentials = AccessKeyCredential(
            config.access_key_id, 
            config.access_key_secret
        )
        
        # 创建客户端
        # 注意：不同版本的SDK设置超时的方式可能不同
        # 这里尝试一个标准的初始化方式，超时在具体请求时处理
        self.client = AcsClient(
            region_id=config.region_id, 
            credential=credentials
        )

    def _create_common_request(self, method: str, uri: str) -> CommonRequest:
        """
        创建通用请求对象
        
        Args:
            method: 请求方法
            uri: 请求URI
            
        Returns:
            CommonRequest: 请求对象
        """
        request = CommonRequest()
        request.set_accept_format('json')
        request.set_domain(self.domain)
        request.set_version(self.version)
        request.set_protocol_type(self.protocol_type)
        request.set_method(method)
        request.set_uri_pattern(uri)
        
        # 设置通用请求头
        request.add_header('Content-Type', 'application/json')
        request.add_header('Date', datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT'))
        request.add_header('Host', self.domain)
        request.add_header('X-TingWu-AppKey', self.config.app_key)
        
        # 注意: CommonRequest不支持直接设置超时
        # 超时控制应该在AcsClient初始化时设置
        
        return request

    def create_task(
        self, 
        file_url: str, 
        source_language: str = "auto",
        enable_summary: bool = True, 
        enable_timestamp: bool = True,
        enable_diarization: bool = False,
        speaker_count: int = 2,
        enable_translation: bool = False,
        target_languages: Optional[List[str]] = None,
        enable_auto_chapters: bool = False,
        enable_meeting_assistance: bool = False,
        enable_ppt_extraction: bool = False,
        enable_text_polish: bool = False
    ) -> str:
        """
        创建视频转写任务
        
        Args:
            file_url: 视频文件URL
            source_language: 源语言，默认auto自动检测
            enable_summary: 是否启用摘要生成
            enable_timestamp: 是否启用时间戳
            enable_diarization: 是否启用角色分离
            speaker_count: 说话人数量
            enable_translation: 是否启用翻译
            target_languages: 目标语言列表
            enable_auto_chapters: 是否启用章节速览
            enable_meeting_assistance: 是否启用智能纪要
            enable_ppt_extraction: 是否启用PPT提取
            enable_text_polish: 是否启用口语书面化
            
        Returns:
            str: 任务ID
            
        Raises:
            APIError: API请求失败时抛出
        """
        # 构建请求体
        body = {}
        body['AppKey'] = self.config.app_key
        
        # 设置任务名称和时间戳，便于后续查询
        task_key = f"task_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 基本请求参数
        input_params = {}
        input_params['SourceLanguage'] = source_language
        input_params['TaskKey'] = task_key
        input_params['FileUrl'] = file_url
        body['Input'] = input_params
        
        # AI参数
        parameters = {}
        
        # 摘要相关
        if enable_summary:
            parameters['SummarizationEnabled'] = True
            summarization = {"Types": ["Paragraph"]}
            parameters['Summarization'] = summarization
        
        # 语音识别相关参数
        transcription = {}
        
        # 是否使用时间戳
        if enable_timestamp:
            transcription['TimestampEnabled'] = True
        
        # 角色分离设置
        if enable_diarization:
            transcription['DiarizationEnabled'] = True
            diarization = {"SpeakerCount": speaker_count}
            transcription['Diarization'] = diarization
        
        # 如果有任何转写参数，添加到parameters
        if transcription:
            parameters['Transcription'] = transcription
        
        # 翻译相关
        if enable_translation and target_languages:
            parameters['TranslationEnabled'] = True
            translation = {"TargetLanguages": target_languages}
            parameters['Translation'] = translation
        
        # 章节速览
        if enable_auto_chapters:
            parameters['AutoChaptersEnabled'] = True
        
        # 智能纪要
        if enable_meeting_assistance:
            parameters['MeetingAssistanceEnabled'] = True
            meeting_assistance = {"Types": ["Actions", "KeyInformation"]}
            parameters['MeetingAssistance'] = meeting_assistance
        
        # PPT提取
        if enable_ppt_extraction:
            parameters['PptExtractionEnabled'] = True
        
        # 口语书面化
        if enable_text_polish:
            parameters['TextPolishEnabled'] = True
        
        body['Parameters'] = parameters
        
        print(f"创建通义听悟任务: TaskKey={task_key}, FileUrl={file_url[:50]}...")
        print(f"启用功能: 摘要={enable_summary}, 时间戳={enable_timestamp}, 角色分离={enable_diarization}")
        
        # 使用ROA风格请求
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                request = self._create_common_request("PUT", "/openapi/tingwu/v2/tasks")
                request.add_query_param('type', 'offline')
                request.add_header('X-TingWu-AppKey', self.config.app_key)
                request.set_content(json.dumps(body).encode('utf-8'))
                
                # 发送请求
                # 阿里云SDK不同版本的do_action_with_exception可能不支持超时参数
                # 如果有超时错误，可以考虑通过系统环境变量等方式控制
                response = self.client.do_action_with_exception(request)
                response_dict = json.loads(response.decode('utf-8'))
                
                # 输出完整响应用于调试
                response_str = json.dumps(response_dict)
                print(f"API响应: {response_str}")
                
                # 检查响应是否成功
                if response_dict.get("Code") != "0" or "success" not in response_dict.get("Message", "").lower():
                    error_msg = response_str
                    print(f"创建任务失败，响应: {error_msg}")
                    raise APIError(f"创建任务失败: {error_msg}")
                
                # 从响应中获取任务ID
                if "Data" in response_dict and "TaskId" in response_dict["Data"]:
                    task_id = response_dict["Data"]["TaskId"]
                    task_status = response_dict["Data"].get("TaskStatus", "UNKNOWN")
                    
                    # 任务状态为ONGOING表示任务成功创建并开始处理
                    if task_status.upper() == "ONGOING":
                        print(f"任务创建成功: TaskId={task_id}, 初始状态={task_status}")
                        return task_id
                    else:
                        print(f"任务创建成功但状态异常: TaskId={task_id}, 状态={task_status}")
                        return task_id
                else:
                    error_msg = f"响应中未找到任务ID: {response_str}"
                    print(error_msg)
                    raise APIError(error_msg)
                
            except (ClientException, ServerException) as e:
                retry_count += 1
                error_msg = str(e)
                
                # 特殊处理连接错误
                if 'SDK.HttpError' in error_msg and 'Connection aborted' in error_msg:
                    print(f"HTTP连接中断，这是一个网络问题 (尝试 {retry_count}/{max_retries})")
                    if retry_count < max_retries:
                        # 指数退避
                        backoff_time = 2 ** (retry_count - 1)
                        print(f"等待 {backoff_time} 秒后重试...")
                        time.sleep(backoff_time)
                        continue
                
                print(f"请求失败: {error_msg}")
                raise APIError(f"请求失败: {error_msg}") from e
            
            except json.JSONDecodeError as e:
                retry_count += 1
                print(f"JSON解析错误 (尝试 {retry_count}/{max_retries}): {str(e)}")
                
                if retry_count < max_retries:
                    time.sleep(2 ** (retry_count - 1))
                    continue
                
                raise APIError(f"响应解析失败: {str(e)}") from e
                
            except Exception as e:
                print(f"未知错误: {str(e)}")
                raise APIError(f"未知错误: {str(e)}") from e

    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 任务结果（完整API响应）
            
        Raises:
            APIError: API请求失败时抛出
        """
        print(f"获取任务结果: TaskId={task_id}")
        
        # 创建请求
        request = self._create_common_request("GET", f"/openapi/tingwu/v2/tasks/{task_id}")
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 发送请求
                # 阿里云SDK不同版本的AcsClient可能不支持在do_action_with_exception中设置超时
                # 如果出现超时相关错误，可能需要使用其他方式设置或通过环境变量控制
                response = self.client.do_action_with_exception(request)
                response_dict = json.loads(response.decode('utf-8'))
                
                # 打印响应头部信息以便调试
                print(f"响应包含字段: {list(response_dict.keys())}")
                
                # 检查是否成功返回任务状态
                if 'Data' in response_dict and 'TaskStatus' in response_dict['Data']:
                    print(f"任务状态: {response_dict['Data']['TaskStatus']}")
                    
                    # 如果任务已完成，打印更多信息
                    if response_dict['Data']['TaskStatus'].upper() == 'FINISHED':
                        if 'Results' in response_dict['Data']:
                            result_types = [r.get('Type', 'Unknown') for r in response_dict['Data'].get('Results', [])]
                            print(f"结果类型: {result_types}")
                
                # 返回完整任务数据
                return response_dict
                
            except (ClientException, ServerException) as e:
                error_msg = str(e)
                retry_count += 1
                
                if 'SDK.HttpError' in error_msg and 'Connection aborted' in error_msg:
                    print(f"HTTP连接中断，这是一个网络问题 (尝试 {retry_count}/{max_retries})")
                    if retry_count < max_retries:
                        # 指数退避
                        backoff_time = 2 ** (retry_count - 1)
                        print(f"等待 {backoff_time} 秒后重试...")
                        time.sleep(backoff_time)
                        continue
                
                print(f"获取任务结果失败: {error_msg}")
                raise APIError(f"请求失败: {error_msg}") from e
                
            except json.JSONDecodeError as e:
                retry_count += 1
                print(f"JSON解析错误 (尝试 {retry_count}/{max_retries}): {str(e)}")
                
                if retry_count < max_retries:
                    time.sleep(2 ** (retry_count - 1))
                    continue
                
                raise APIError(f"响应解析失败: {str(e)}") from e
                
            except Exception as e:
                error_msg = str(e)
                print(f"获取任务结果时发生未知错误: {error_msg}")
                raise APIError(f"未知错误: {error_msg}") from e

    def wait_for_result(self, task_id: str, timeout: int = 10800, interval: int = 60) -> Dict[str, Any]:
        """
        等待并获取任务结果
        
        Args:
            task_id: 任务ID
            timeout: 超时时间（秒），默认3小时
            interval: 轮询间隔（秒），默认60秒
            
        Returns:
            Dict[str, Any]: 任务结果
            
        Raises:
            APIError: API请求失败时抛出
            TimeoutError: 超时时抛出
        """
        start_time = time.time()
        while True:
            # 获取任务结果
            response_dict = self.get_task_result(task_id)
            
            # 检查响应格式
            if response_dict.get("Code") != "0" or "success" not in response_dict.get("Message", "").lower():
                error_msg = json.dumps(response_dict)
                print(f"获取任务结果失败: {error_msg}")
                raise APIError(f"API错误: {error_msg}")
            
            # 从响应中提取任务数据
            result = response_dict.get("Data", {})
            
            # 获取任务状态
            status = result.get('TaskStatus', '')
            
            # 打印任务状态以便调试
            print(f"当前任务状态: {status}")
            
            # 根据任务状态处理
            # 通义听悟API可能返回COMPLETED或FINISHED作为成功状态
            if status.upper() in ["COMPLETED", "FINISHED"]:
                print(f"任务处理完成，已用时: {int(time.time() - start_time)}秒")
                return result
            elif status.upper() == "FAILED":
                error_msg = result.get('ErrorMessage', '未知错误')
                print(f"任务失败详情: {error_msg}")
                raise APIError(f"任务处理失败: {error_msg}")
            elif time.time() - start_time > timeout:
                raise TimeoutError(f"任务处理超时，已等待{timeout}秒")
            
            # 输出当前状态并等待
            elapsed_time = int(time.time() - start_time)
            print(f"任务处理中... 状态: {status}，已等待: {elapsed_time}秒")
            time.sleep(interval)
    
    def get_summary(self, result: Dict[str, Any]) -> str:
        """
        从任务结果中提取摘要
        
        Args:
            result: 任务结果，可以是完整API响应或Data部分
            
        Returns:
            str: 摘要文本
        """
        try:
            # 如果输入是完整的API响应，提取Data部分
            if isinstance(result, dict) and 'Data' in result and 'Code' in result:
                result = result.get('Data', {})
                
            # 确保任务已完成
            status = result.get('TaskStatus', '').upper()
            if status not in ['FINISHED', 'COMPLETED']:
                return f"任务尚未完成，当前状态: {status}，无法获取摘要"
            
            # 打印结果结构以便调试
            print(f"结果结构包含以下字段: {list(result.keys())}")
            
            # 检查结果中是否包含指向摘要的URL
            if 'Result' in result and 'Summarization' in result['Result']:
                summarization_url = result['Result']['Summarization']
                print(f"找到摘要URL: {summarization_url}")
                
                try:
                    # 下载摘要内容
                    print("正在下载摘要内容...")
                    response = requests.get(summarization_url, timeout=30)
                    response.raise_for_status()
                    
                    # 解析JSON响应
                    summary_data = response.json()
                    print(f"摘要数据结构: {list(summary_data.keys()) if isinstance(summary_data, dict) else 'not a dict'}")
                    
                    # 尝试从不同的可能结构中提取摘要文本
                    if isinstance(summary_data, dict):
                        # 尝试从Type为Paragraph的项目中提取
                        if 'Data' in summary_data:
                            for item in summary_data['Data']:
                                if item.get('Type') == 'Paragraph':
                                    return item.get('Text', '')
                        
                        # 尝试直接获取Text字段
                        if 'Text' in summary_data:
                            return summary_data['Text']
                        
                        # 尝试从Content字段获取
                        if 'Content' in summary_data:
                            return summary_data['Content']
                    
                    # 如果无法解析，返回原始内容的字符串表示
                    return json.dumps(summary_data, ensure_ascii=False, indent=2)
                    
                except Exception as e:
                    print(f"下载或解析摘要内容失败: {str(e)}")
                    return f"下载摘要失败: {str(e)}"
            
            # 从新API结构中提取摘要
            if 'Results' in result and result['Results']:
                print(f"发现 {len(result['Results'])} 个结果项")
                
                for result_item in result['Results']:
                    result_type = result_item.get('Type', 'Unknown')
                    print(f"处理结果类型: {result_type}")
                    
                    if result_type == 'Summarization':
                        data_items = result_item.get('Data', [])
                        print(f"发现 {len(data_items)} 个摘要数据项")
                        
                        for summary_item in data_items:
                            item_type = summary_item.get('Type', 'Unknown')
                            print(f"摘要类型: {item_type}")
                            
                            if item_type == 'Paragraph':
                                summary_text = summary_item.get('Text', '')
                                if summary_text:
                                    print(f"找到段落摘要，长度: {len(summary_text)}")
                                    return summary_text
            
            # 尝试旧的结构
            if 'Summary' in result:
                summary_text = result['Summary']
                print(f"从旧API格式中找到摘要，长度: {len(summary_text)}")
                return summary_text
                
            print("未能在任何已知结构中找到摘要")
            return "未找到摘要信息"
        except Exception as e:
            print(f"提取摘要时发生错误: {str(e)}")
            return f"提取摘要失败: {str(e)}"
    
    def get_transcript(self, result: Dict[str, Any]) -> str:
        """
        从任务结果中提取完整转写文本
        
        Args:
            result: 任务结果，可以是完整API响应或Data部分
            
        Returns:
            str: 完整转写文本
        """
        try:
            # 如果输入是完整的API响应，提取Data部分
            if isinstance(result, dict) and 'Data' in result and 'Code' in result:
                result = result.get('Data', {})
                
            # 确保任务已完成
            status = result.get('TaskStatus', '').upper()
            if status not in ['FINISHED', 'COMPLETED']:
                return f"任务尚未完成，当前状态: {status}，无法获取转写文本"
            
            # 打印结果结构以便调试
            print(f"结果结构包含以下字段: {list(result.keys())}")
            
            # 检查结果中是否包含指向转写文本的URL
            if 'Result' in result and 'Transcription' in result['Result']:
                transcription_url = result['Result']['Transcription']
                print(f"找到转写URL: {transcription_url}")
                
                try:
                    # 下载转写内容
                    print("正在下载转写内容...")
                    response = requests.get(transcription_url, timeout=30)
                    response.raise_for_status()
                    
                    # 解析JSON响应
                    transcript_data = response.json()
                    print(f"转写数据结构: {list(transcript_data.keys()) if isinstance(transcript_data, dict) else 'not a dict'}")
                    
                    # 尝试从不同的可能结构中提取转写文本
                    full_transcript = ""
                    
                    if isinstance(transcript_data, dict):
                        # 尝试从Data数组中提取
                        if 'Data' in transcript_data:
                            for item in transcript_data['Data']:
                                if 'Text' in item:
                                    full_transcript += item['Text'] + "\n"
                        
                        # 尝试直接获取Text字段
                        elif 'Text' in transcript_data:
                            full_transcript = transcript_data['Text']
                        
                        # 尝试从Content字段获取
                        elif 'Content' in transcript_data:
                            full_transcript = transcript_data['Content']
                        
                        # 尝试从SentenceArray数组提取
                        elif 'SentenceArray' in transcript_data:
                            for sentence in transcript_data['SentenceArray']:
                                if 'Text' in sentence:
                                    full_transcript += sentence['Text'] + "\n"
                    
                    if full_transcript:
                        return full_transcript
                    
                    # 如果无法解析，返回原始内容的字符串表示
                    return json.dumps(transcript_data, ensure_ascii=False, indent=2)
                    
                except Exception as e:
                    print(f"下载或解析转写内容失败: {str(e)}")
                    return f"下载转写失败: {str(e)}"
            
            # 从新API结构中提取转写文本
            if 'Results' in result and result['Results']:
                print(f"发现 {len(result['Results'])} 个结果项")
                
                for result_item in result['Results']:
                    result_type = result_item.get('Type', 'Unknown')
                    print(f"处理结果类型: {result_type}")
                    
                    if result_type == 'Transcription':
                        data_items = result_item.get('Data', [])
                        print(f"发现 {len(data_items)} 个转写段落")
                        
                        if data_items:
                            transcript = ""
                            for segment in data_items:
                                if 'Text' in segment:
                                    transcript += segment['Text'] + "\n"
                            
                            if transcript:
                                print(f"构建了转写文本，长度: {len(transcript)}")
                                return transcript
            
            # 尝试旧的结构
            if 'Transcript' in result:
                transcript = result['Transcript']
                print(f"从旧API格式中找到转写文本，长度: {len(transcript)}")
                return transcript
                
            print("未能在任何已知结构中找到转写文本")
            return "未找到转写文本"
        except Exception as e:
            print(f"提取转写文本时发生错误: {str(e)}")
            return f"提取转写文本失败: {str(e)}"


    def extract_text_by_paragraph_id(self, data: Union[Dict[str, Any], str]) -> str:
        """
        从转写结果中按ParagraphId提取并合并文本
        
        Args:
            data: 转写结果数据，可以是字典或JSON字符串
            
        Returns:
            str: 合并后的文本，按段落分隔
        """
        # 如果是字符串，尝试解析为JSON
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return data
        
        # 如果不是字典类型，无法处理
        if not isinstance(data, dict):
            return str(data)
        
        # 提取Transcription字段
        transcription = data.get("Transcription", {})
        if not transcription:
            # 尝试从Data字段提取
            transcription = data.get("Data", {}).get("Transcription", {})
            if not transcription:
                return str(data)
        
        # 提取段落数组
        paragraphs = transcription.get("Paragraphs", [])
        if not paragraphs:
            return str(data)
        
        # 按段落ID组织文本
        paragraph_texts = {}
        
        for paragraph in paragraphs:
            paragraph_id = paragraph.get("ParagraphId", "unknown")
            speaker_id = paragraph.get("SpeakerId", "unknown")
            words = paragraph.get("Words", [])
            
            # 提取并合并该段落中所有单词的文本
            texts = [word.get("Text", "") for word in words]
            paragraph_text = "".join(texts)
            
            # 存储该段落的文本
            paragraph_texts[paragraph_id] = {
                "SpeakerId": speaker_id,
                "Text": paragraph_text
            }
        
        # 按段落ID排序并格式化输出
        result_lines = []
        for p_id, p_data in sorted(paragraph_texts.items()):
            speaker = p_data["SpeakerId"]
            text = p_data["Text"]
            result_lines.append(f"[段落ID: {p_id}, 说话人: {speaker}]\n{text}\n")
        
        return "\n".join(result_lines)

    def submit_task(self, file_url: str, language_type: str = "auto") -> str:
        """
        提交文件进行转写任务
        
        Args:
            file_url: 文件URL
            language_type: 语言类型，默认为自动检测
            
        Returns:
            str: 任务ID
        """
        return self.create_task(
            file_url=file_url,
            source_language=language_type,
            enable_summary=True,
            enable_timestamp=True,
            enable_diarization=True,
            speaker_count=2
        )
        
    def process_results(
        self, 
        task_id: str, 
        output_dir: str, 
        filename_prefix: str, 
        formats: List[str] = ["json", "txt", "paragraph", "srt", "vtt"]
    ) -> Dict[str, str]:
        """
        处理任务结果，生成不同格式的输出文件
        
        Args:
            task_id: 任务ID
            output_dir: 输出目录
            filename_prefix: 文件名前缀（通常是原始文件名，不含扩展名）
            formats: 要生成的格式列表，默认为所有格式
            
        Returns:
            Dict[str, str]: 格式名称到文件路径的映射
            
        Raises:
            APIError: API请求失败时抛出
        """
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 存储输出文件路径
        output_files = {}
        
        try:
            # 获取原始结果和转写文本
            result = self.get_task_result(task_id)
            transcript_json = result.get("Data", {})
            transcript = self.get_transcript(result)
            summary = self.get_summary(result)
            
            # 保存JSON格式（原始数据）
            if "json" in formats:
                json_file = os.path.join(output_dir, f"{filename_prefix}_转写.json")
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(transcript_json, f, ensure_ascii=False, indent=2)
                print(f"原始转写数据已保存到: {json_file}")
                output_files["json"] = json_file
            
            if "transcription" in formats:
                transcription_file = os.path.join(output_dir, f"{filename_prefix}_转写.txt")
                with open(transcription_file, "w", encoding="utf-8") as f:
                    f.write(transcript)
                print(f"转写文本已保存到: {transcription_file}")
                output_files["transcription"] = transcription_file

            if "paragraph" in formats:
                paragraph_file = os.path.join(output_dir, f"{filename_prefix}_段落.txt")
                with open(paragraph_file, "w", encoding="utf-8") as f:
                    f.write(self.extract_text_by_paragraph_id(transcript))
                print(f"段落格式转写已保存到: {paragraph_file}")
                output_files["paragraph"] = paragraph_file

            # 保存摘要
            if summary:
                summary_file = os.path.join(output_dir, f"{filename_prefix}_摘要.txt")
                with open(summary_file, "w", encoding="utf-8") as f:
                    f.write(summary)
                print(f"摘要已保存到: {summary_file}")
                output_files["summary"] = summary_file
            
            # 打印所有保存的文件
            if output_files:
                print("\n所有输出文件:")
                for file_type, file_path in output_files.items():
                    print(f"- {file_type}: {file_path}")
            else:
                print("警告: 未保存任何输出文件")
            
            return output_files
            
        except Exception as e:
            print(f"获取或保存结果时出错: {str(e)}")
            traceback.print_exc()
            raise APIError(f"处理结果失败: {str(e)}") from e 