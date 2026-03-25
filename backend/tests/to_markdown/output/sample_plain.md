MarkItDown 是微软开源的 Python 工具，支持将 15+ 种常见文档 / 媒体 / 网页格式 解析并转为 Markdown，核心覆盖办公文档、多媒体、网页、结构化数据、电子书、压缩包等。
一、办公文档（核心支持）
PDF（.pdf）：提取文本、表格、结构；支持扫描件 OCR（需 Azure Document Intelligence 等插件）
Word（.docx）：完整保留标题、列表、表格、样式层级
PowerPoint（.pptx）：按幻灯片提取标题、正文、图片描述
Excel（.xlsx/.xls）：表格转 Markdown 表格，保留行列结构
Outlook 邮件（.msg）：需安装 [outlook] 依赖
二、多媒体内容
图片（JPG/PNG/GIF 等）：提取 EXIF 元数据；支持 OCR 文字识别
音频（MP3/WAV 等）：提取元数据；语音转文字（需 [audio-transcription]）
YouTube 视频：自动提取字幕并转为文本
三、网页与结构化数据
HTML：网页内容清理与结构化转换
CSV/JSON/XML：结构化数据转 Markdown 格式
ZIP 压缩包：递归遍历并转换内部所有支持的文件
