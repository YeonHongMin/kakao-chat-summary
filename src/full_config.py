"""
config.py - 애플리케이션 설정 관리 모듈

이 모듈은 프로젝트 전역에서 사용되는 설정값들을 중앙에서 관리합니다.
- 다중 LLM API 설정 (GLM, ChatGPT, MiniMax, Perplexity)
- 디렉터리 경로 설정
- 로깅 설정
- LLM 프롬프트 템플릿
"""

from typing import Dict, Optional
from dataclasses import dataclass
import os
import logging
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
BASE_DIR = CURRENT_DIR.parent

# .env.local 파일 로드 (프로젝트 루트에서)
try:
    from dotenv import load_dotenv

    env_local = BASE_DIR / '.env.local'
    env_file = BASE_DIR / '.env'
    # 우선순위: .env.local > .env
    if env_local.exists():
        load_dotenv(env_local, override=True)
    elif env_file.exists():
        load_dotenv(env_file, override=True)
except ImportError:
    pass  # python-dotenv가 설치되지 않은 경우 환경변수만 사용


@dataclass
class LLMProvider:
    """LLM 제공자 설정 정보"""
    name: str
    api_url: str
    model: str
    env_key: str
    max_tokens: int = 16000
    reasoning_effort: str = ""  # "high", "medium", "low", "none", "" (미지정)
    max_input_chars: int = 0    # 0 = 무제한. 컨텍스트 윈도우가 작은 모델에 설정


# 지원하는 LLM 제공자 목록
LLM_PROVIDERS: Dict[str, LLMProvider] = {
    "glm": LLMProvider(
        name="Z.AI GLM",
        api_url="https://api.z.ai/api/coding/paas/v4/chat/completions",
        model="glm-4.5",
        env_key="ZAI_API_KEY",
        max_tokens=int(os.getenv("ZAI_MAX_TOKENS", "8192")),
        max_input_chars=int(os.getenv("ZAI_MAX_INPUT_CHARS", "1500000"))  # 약 1.5MB 문자수(대략 1M 토큰) 제한
    ),
    "chatgpt": LLMProvider(
        name="OpenAI ChatGPT",
        api_url="https://api.openai.com/v1/chat/completions",
        model="gpt-4o-mini",
        env_key="OPENAI_API_KEY"
    ),
    "minimax": LLMProvider(
        name="MiniMax Coding Plan",
        api_url="https://api.minimax.io/v1/chat/completions",
        model="MiniMax-M2.7",
        env_key="MINIMAX_API_KEY"
    ),
    "perplexity": LLMProvider(
        name="Perplexity",
        api_url="https://api.perplexity.ai/chat/completions",
        model="sonar",
        env_key="PERPLEXITY_API_KEY"
    ),
    "grok": LLMProvider(
        name="xAI Grok",
        api_url="https://api.x.ai/v1/chat/completions",
        model="grok-4-1-fast-non-reasoning",
        env_key="XAI_API_KEY"
    ),
    "qwen-or": LLMProvider(
        name="OpenRouter",
        api_url="https://openrouter.ai/api/v1/chat/completions",
        model=os.getenv("OPENROUTER_MODEL", "x-ai/grok-4.1-fast"),
        env_key="OPENROUTER_API_KEY",
        max_tokens=int(os.getenv("OPENROUTER_MAX_TOKENS", "30000")),
        max_input_chars=int(os.getenv("OPENROUTER_MAX_INPUT_CHARS", "0")),  # 0 = 무제한 (grok-4.1-fast: 2M context)
    ),
    "qwen-kilo": LLMProvider(
        name="Kilo",
        api_url="https://api.kilo.ai/api/gateway/chat/completions",
        model=os.getenv("KILO_MODEL", "x-ai/grok-4.1-fast"),
        env_key="KILO_API_KEY",
        max_tokens=int(os.getenv("KILO_MAX_TOKENS", "30000")),
        max_input_chars=int(os.getenv("KILO_MAX_INPUT_CHARS", "0")),  # 0 = 무제한 (grok-4.1-fast: 2M context)
    ),
    "ollama": LLMProvider(
        name="Local LLM",
        api_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/") + "/v1/chat/completions",
        model=os.getenv("OLLAMA_MODEL", "qwen35-35b-maxctx"),
        env_key="",
        max_tokens=int(os.getenv("OLLAMA_MAX_TOKENS", "16000")),
        max_input_chars=int(os.getenv("OLLAMA_MAX_INPUT_CHARS", "0")),
        reasoning_effort=os.getenv("OLLAMA_REASONING_EFFORT", "none")
    ),
}


class Config:
    """애플리케이션 설정을 관리하는 싱글톤 클래스."""

    DEFAULT_TIMEOUT = 600
    DEFAULT_PROVIDER = "glm"

    def __init__(self):
        self.current_provider: str = os.getenv("LLM_PROVIDER", self.DEFAULT_PROVIDER)
        self.api_timeout: int = int(os.getenv("API_TIMEOUT", self.DEFAULT_TIMEOUT))
        self.base_dir: Path = CURRENT_DIR.parent
        self.data_dir: Path = self.base_dir / 'data'
        self._api_keys: Dict[str, Optional[str]] = {}
        self._setup_logging()

    def set_provider(self, provider: str) -> None:
        if provider not in LLM_PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(LLM_PROVIDERS.keys())}")
        self.current_provider = provider

    def get_provider_info(self) -> LLMProvider:
        return LLM_PROVIDERS[self.current_provider]

    @staticmethod
    def _is_placeholder(key: Optional[str]) -> bool:
        """API 키가 placeholder인지 확인"""
        if not key:
            return True
        stripped = key.strip()
        if not stripped:
            return True
        lower = stripped.lower()
        return 'your_' in lower and '_here' in lower

    def get_api_key(self, provider: Optional[str] = None) -> Optional[str]:
        provider = provider or self.current_provider
        provider_info = LLM_PROVIDERS[provider]
        if not provider_info.env_key:
            return "no-key-needed"
        if provider in self._api_keys and self._api_keys[provider]:
            key = self._api_keys[provider]
            return None if self._is_placeholder(key) else key
        key = os.getenv(provider_info.env_key)
        return None if self._is_placeholder(key) else key

    def set_api_key(self, api_key: str, provider: Optional[str] = None) -> None:
        provider = provider or self.current_provider
        self._api_keys[provider] = api_key.strip()

    @property
    def zai_api_key(self) -> Optional[str]:
        return self.get_api_key()

    def _setup_logging(self) -> None:
        # logs 디렉터리 생성
        self.logs_dir = self.base_dir / 'logs'
        self.logs_dir.mkdir(exist_ok=True)
        
        # 로그 파일 경로 (날짜별)
        from datetime import datetime
        log_filename = f"summarizer_{datetime.now().strftime('%Y%m%d')}.log"
        log_path = self.logs_dir / log_filename
        
        # 파일 핸들러 (상세 로그 - DEBUG 이상)
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))

        # INFO 전용 파일 핸들러 (요약 진행/속도 확인용)
        info_log_filename = f"info_{datetime.now().strftime('%Y%m%d')}.log"
        info_log_path = self.logs_dir / info_log_filename
        info_handler = logging.FileHandler(info_log_path, encoding='utf-8')
        info_handler.setLevel(logging.INFO)
        info_handler.addFilter(lambda record: record.levelno == logging.INFO)
        info_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))

        # 콘솔 핸들러 (간단한 로그)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)  # 콘솔에는 경고 이상만
        console_handler.setFormatter(logging.Formatter('%(message)s'))

        # 로거 설정
        logger = logging.getLogger("KakaoSummarizer")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
        logger.addHandler(info_handler)
        logger.addHandler(console_handler)

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger("KakaoSummarizer")


config = Config()
