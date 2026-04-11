"""
配置管理模块

从 .env 文件和环境变量加载项目配置，使用 Pydantic 进行校验。
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 加载 .env 文件
load_dotenv(PROJECT_ROOT / ".env")

# 支持的 LLM 提供商列表
LLM_PROVIDERS = ("claude", "openai", "qwen", "deepseek", "ollama")


class BilibiliConfig(BaseModel):
    """B站相关配置"""
    sessdata: str = Field(default="", description="B站 SESSDATA Cookie")
    bili_jct: str = Field(default="", description="B站 bili_jct Cookie")
    buvid3: str = Field(default="", description="B站 buvid3 Cookie")


class AnthropicConfig(BaseModel):
    """Claude API 配置"""
    api_key: str = Field(default="", description="Anthropic API Key")
    model: str = Field(default="claude-sonnet-4-20250514", description="使用的模型名称")


class OpenAIConfig(BaseModel):
    """OpenAI API 配置"""
    api_key: str = Field(default="", description="OpenAI API Key")
    base_url: str = Field(default="https://api.openai.com/v1", description="API Base URL")
    model: str = Field(default="gpt-4o", description="使用的模型名称")


class QwenConfig(BaseModel):
    """通义千问 Qwen API 配置（阿里云 DashScope，OpenAI 兼容接口）"""
    api_key: str = Field(default="", description="DashScope API Key")
    base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="DashScope OpenAI 兼容接口地址",
    )
    model: str = Field(default="qwen3-235b-a22b", description="Qwen 模型名称")


class DeepSeekConfig(BaseModel):
    """DeepSeek API 配置（OpenAI 兼容接口）"""
    api_key: str = Field(default="", description="DeepSeek API Key")
    base_url: str = Field(
        default="https://api.deepseek.com",
        description="DeepSeek API 地址",
    )
    model: str = Field(default="deepseek-reasoner", description="DeepSeek 模型名称")


class OllamaConfig(BaseModel):
    """Ollama 本地模型配置"""
    base_url: str = Field(default="http://localhost:11434/v1", description="Ollama API 地址")
    model: str = Field(default="qwen2.5:3b", description="本地模型名称")


class FunASRConfig(BaseModel):
    """FunASR 语音识别配置"""
    model: str = Field(default="paraformer-zh", description="ASR模型名称")
    vad_model: str = Field(default="fsmn-vad", description="VAD模型名称")
    punc_model: str = Field(default="ct-punc", description="标点恢复模型名称")


class AppConfig(BaseModel):
    """应用全局配置"""
    up_uid: int = Field(default=0, description="UP主UID")
    llm_provider: str = Field(default="claude", description="LLM提供商")
    data_dir: Path = Field(default=PROJECT_ROOT / "data", description="数据存储目录")
    output_dir: Path = Field(default=PROJECT_ROOT / "output", description="输出目录")
    bilibili: BilibiliConfig = Field(default_factory=BilibiliConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    qwen: QwenConfig = Field(default_factory=QwenConfig)
    deepseek: DeepSeekConfig = Field(default_factory=DeepSeekConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    funasr: FunASRConfig = Field(default_factory=FunASRConfig)

    @property
    def model_cache_dir(self) -> Path:
        """FunASR/ModelScope 模型缓存目录"""
        return self.data_dir / ".cache" / "modelscope"

    @property
    def audio_dir(self) -> Path:
        """音频文件目录"""
        return self.data_dir / "audio"

    @property
    def transcripts_dir(self) -> Path:
        """转写结果目录"""
        return self.data_dir / "transcripts"

    @property
    def cleaned_dir(self) -> Path:
        """清洗结果目录"""
        return self.data_dir / "cleaned"

    @property
    def knowledge_dir(self) -> Path:
        """知识模型目录"""
        return self.data_dir / "knowledge"

    def ensure_dirs(self):
        """确保所有数据目录存在"""
        for d in [self.audio_dir, self.transcripts_dir, self.cleaned_dir,
                  self.knowledge_dir, self.output_dir, self.model_cache_dir]:
            d.mkdir(parents=True, exist_ok=True)


def load_config() -> AppConfig:
    """从环境变量加载配置"""
    config = AppConfig(
        up_uid=int(os.getenv("UP_UID", "0")),
        llm_provider=os.getenv("LLM_PROVIDER", "claude"),
        data_dir=Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data"))),
        output_dir=Path(os.getenv("OUTPUT_DIR", str(PROJECT_ROOT / "output"))),
        bilibili=BilibiliConfig(
            sessdata=os.getenv("BILIBILI_SESSDATA", ""),
            bili_jct=os.getenv("BILIBILI_BILI_JCT", ""),
            buvid3=os.getenv("BILIBILI_BUVID3", ""),
        ),
        anthropic=AnthropicConfig(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        ),
        openai=OpenAIConfig(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        ),
        qwen=QwenConfig(
            api_key=os.getenv("QWEN_API_KEY", ""),
            base_url=os.getenv("QWEN_BASE_URL",
                               "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            model=os.getenv("QWEN_MODEL", "qwen3-235b-a22b"),
        ),
        deepseek=DeepSeekConfig(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner"),
        ),
        ollama=OllamaConfig(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        ),
        funasr=FunASRConfig(
            model=os.getenv("FUNASR_MODEL", "paraformer-zh"),
            vad_model=os.getenv("FUNASR_VAD_MODEL", "fsmn-vad"),
            punc_model=os.getenv("FUNASR_PUNC_MODEL", "ct-punc"),
        ),
    )
    config.ensure_dirs()
    return config
