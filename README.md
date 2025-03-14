# 哔哩哔哩视频下载器

这是一个用于下载B站视频并上传到阿里云OSS存储的工具。

## 功能特点

- 从B站下载指定BV号的视频
- 可选择不同的视频质量
- 上传视频到阿里云OSS存储
- 生成视频的临时访问链接
- 使用通义听悟API进行视频内容转写和摘要生成
- 支持多种转写格式：纯文本、段落分组、SRT和VTT字幕
- 模块化设计，支持代码复用

## 安装

```bash
# 克隆仓库
git clone <仓库URL>
cd vedio_summ

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

## 使用方法

### 配置

1. 在 `config/config.yaml` 中设置阿里云OSS配置，或使用环境变量
2. 对于B站登录状态，可以通过以下方式提供Cookie以下载高清视频：
   - 在配置文件中设置: `bilibili.cookie: 你的Cookie值`
   - 使用环境变量: `export BILIBILI_COOKIE=你的Cookie值`
   - 在命令行指定: `--cookie "你的Cookie值"`
3. 通义听悟API配置：
   - 在配置文件中设置: `tingwu.app_key: 你的AppKey`
   - 使用环境变量设置访问密钥: `TINGWU_ACCESS_KEY_ID` 和 `TINGWU_ACCESS_KEY_SECRET`

配置文件示例：
```yaml
oss:
  access_key_id: ${OSS_ACCESS_KEY_ID}
  access_key_secret: ${OSS_ACCESS_KEY_SECRET}
  endpoint: oss-cn-beijing.aliyuncs.com
  bucket_name: auto-scrip
  region: cn-beijing  # OSS区域，用于v4签名

bilibili:
  default_quality: 80
  chunk_size: 1048576  # 1MB
  cookie: ${BILIBILI_COOKIE}  # 可以使用环境变量或直接填写完整的Cookie

tingwu:
  app_key: YOUR_TINGWU_APP_KEY  # 通义听悟项目AppKey
  access_key_id: ${TINGWU_ACCESS_KEY_ID}  # 通义听悟访问密钥
  access_key_secret: ${TINGWU_ACCESS_KEY_SECRET}  # 通义听悟访问密钥Secret
  region_id: cn-beijing  # 服务区域
```

### 示例

```python
from src.bilibili_downloader.core import BiliVideoDownloader
from src.bilibili_downloader.services import OSSService, OSSConfig

# 初始化下载器
downloader = BiliVideoDownloader(cookie="your_cookie")

# 获取视频信息
video_info = downloader.get_video_info("BV1G4AHe1E1P")
print(f"视频标题: {video_info.title}")

# 设置OSS配置
oss_config = OSSConfig(
    access_key_id="YOUR_ACCESS_KEY_ID",
    access_key_secret="YOUR_ACCESS_KEY_SECRET", 
    endpoint="oss-cn-beijing.aliyuncs.com",
    bucket_name="your-bucket-name"
)

# 初始化OSS服务
oss_service = OSSService(oss_config)

# 下载并上传视频
# ...
```

## 使用示例

### 下载B站视频并上传到OSS

```bash
python examples/download_video.py BV1G4AHe1E1P
```

### 从OSS获取文件URL

```bash
# 获取OSS对象的临时访问URL
python examples/get_oss_url.py videos/example.mp4

# 指定URL有效期（秒）
python examples/get_oss_url.py videos/example.mp4 --expire 7200
```

### 使用OSS对象名将视频提交给通义听悟API进行处理

```bash
# 直接处理OSS上的文件
python examples/oss_to_tingwu.py --oss-bucket your-bucket --oss-key videos/example.mp4

# 处理本地文件
python examples/oss_to_tingwu.py --local-file path/to/video.mp4

# 跟踪已有任务
python examples/oss_to_tingwu.py --track-task-id your-task-id --interval 5

# 指定输出格式
python examples/oss_to_tingwu.py --local-file video.mp4 --format srt
```

#### 支持的输出格式

- `json`: 原始转写JSON结果
- `txt`: 提取的纯文本，移除时间戳和标签
- `paragraph`: 按段落和说话人分组的文本
- `srt`: SRT字幕格式，适用于大多数视频播放器
- `vtt`: WebVTT字幕格式，适用于网页播放器
- `all`: 生成所有格式（默认）

### 一键下载视频并生成摘要

```bash
python examples/video_summary.py BV1G4AHe1E1P
```

## 开发

### 项目结构

```
vedio_summ/
├── config/             # 配置文件
├── src/                # 源代码
│   └── bilibili_downloader/
│       ├── core.py     # 下载核心功能
│       ├── services.py # OSS服务
│       ├── tingwu.py   # 通义听悟服务
│       └── exceptions.py # 异常定义
├── examples/           # 示例脚本
├── tests/              # 测试代码
└── requirements.txt    # 依赖管理
```

### 运行测试

```bash
pytest tests/
``` 

## 功能说明

### 转写格式支持

- **纯文本提取**: 从转写结果中提取纯文本内容，去除时间戳、说话人标签等
- **段落格式化**: 按段落和说话人分组，保持原始文本结构
- **SRT字幕**: 生成包含时间戳和说话人信息的SRT格式字幕文件
- **VTT字幕**: 生成WebVTT格式字幕文件，适用于HTML5视频

### OSS集成

- 支持OSS V2和V4签名，自动根据配置选择适当的签名方式
- 提供临时访问URL生成功能
- 支持文件上传和管理

### 通义听悟API集成

- 支持视频语音转写
- 支持摘要生成
- 提供任务状态跟踪
- 支持多种结果格式处理 