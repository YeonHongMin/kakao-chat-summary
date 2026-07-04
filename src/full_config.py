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
    max_input_chars: int = 0    # 0 = 무제한. 입력 문자 수 상한
    max_input_bytes: int = 0    # 0 = 무제한. 입력 UTF-8 바이트 상한 (max_input_chars보다 우선)


# 한글 대화 기준 토큰→문자 근사 (Z.AI 문서: 1 token ≈ 1.5 한글자)
_CHARS_PER_TOKEN = 1.5


def _input_chars_from_context(context_tokens: int, reserved_output_tokens: int) -> int:
    """컨텍스트 토큰에서 출력 예약분을 뺀 입력 문자 수 상한."""
    budget = max(context_tokens - reserved_output_tokens, 0)
    return int(budget * _CHARS_PER_TOKEN)


def _resolve_mimo_api_url() -> str:
    """MiMo API URL. tp-(Token Plan) / sk-(종량제) 엔드포인트가 다름.

    Token Plan 싱가포르 OpenAI 호환 Base:
      https://token-plan-sgp.xiaomimimo.com/v1
    → chat/completions: .../v1/chat/completions
    """
    explicit = os.getenv("MIMO_BASE_URL", "").strip()
    if explicit:
        base = explicit.rstrip("/")
    else:
        key = os.getenv("MIMO_API_KEY", "").strip()
        if key.startswith("tp-"):
            # Token Plan: pay-as-you-go URL과 혼용 불가 (401). 기본 싱가포르 클러스터
            base = "https://token-plan-sgp.xiaomimimo.com/v1"
        else:
            base = "https://api.xiaomimimo.com/v1"
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


_ZAI_MAX_TOKENS = int(os.getenv("ZAI_MAX_TOKENS", "32768"))
_OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "16384"))
_MINIMAX_MAX_TOKENS = int(os.getenv("MINIMAX_MAX_TOKENS", "32768"))
_PERPLEXITY_MAX_TOKENS = int(os.getenv("PERPLEXITY_MAX_TOKENS", "16000"))
_XAI_MAX_TOKENS = int(os.getenv("XAI_MAX_TOKENS", "16000"))
_OPENROUTER_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "30000"))
_KILO_MAX_TOKENS = int(os.getenv("KILO_MAX_TOKENS", "30000"))
_MIMO_MAX_TOKENS = int(os.getenv("MIMO_MAX_TOKENS", "32768"))


# 지원하는 LLM 제공자 목록
LLM_PROVIDERS: Dict[str, LLMProvider] = {
    "glm": LLMProvider(
        name="Z.AI GLM",
        api_url="https://api.z.ai/api/coding/paas/v4/chat/completions",
        model=os.getenv("ZAI_MODEL", "glm-5.2"),
        env_key="ZAI_API_KEY",
        max_tokens=_ZAI_MAX_TOKENS,
        # glm-5.2: 1M context, 최대 출력 128K tokens (docs.z.ai/guides/llm/glm-5.2)
        max_input_chars=int(os.getenv(
            "ZAI_MAX_INPUT_CHARS",
            str(_input_chars_from_context(1_000_000, _ZAI_MAX_TOKENS)),
        )),
    ),
    "chatgpt": LLMProvider(
        name="OpenAI ChatGPT",
        api_url="https://api.openai.com/v1/chat/completions",
        model="gpt-4o-mini",
        env_key="OPENAI_API_KEY",
        max_tokens=_OPENAI_MAX_TOKENS,
        # 공식 컨텍스트 128K, 최대 출력 16K tokens (OpenAI)
        max_input_chars=int(os.getenv(
            "OPENAI_MAX_INPUT_CHARS",
            str(_input_chars_from_context(128_000, _OPENAI_MAX_TOKENS)),
        )),
    ),
    "minimax": LLMProvider(
        name="MiniMax Coding Plan",
        api_url="https://api.minimax.io/v1/chat/completions",
        model="MiniMax-M3",
        env_key="MINIMAX_API_KEY",
        max_tokens=_MINIMAX_MAX_TOKENS,
        # 공식 최대 1M tokens, 표준 요금 구간 512K (platform.minimax.io)
        max_input_chars=int(os.getenv(
            "MINIMAX_MAX_INPUT_CHARS",
            str(_input_chars_from_context(512_000, _MINIMAX_MAX_TOKENS)),
        )),
    ),
    "perplexity": LLMProvider(
        name="Perplexity",
        api_url="https://api.perplexity.ai/chat/completions",
        model="sonar",
        env_key="PERPLEXITY_API_KEY",
        max_tokens=_PERPLEXITY_MAX_TOKENS,
        # sonar 공식 컨텍스트 128K tokens (docs.perplexity.ai)
        max_input_chars=int(os.getenv(
            "PERPLEXITY_MAX_INPUT_CHARS",
            str(_input_chars_from_context(128_000, _PERPLEXITY_MAX_TOKENS)),
        )),
    ),
    "grok": LLMProvider(
        name="xAI Grok",
        api_url="https://api.x.ai/v1/chat/completions",
        model="grok-4-1-fast-non-reasoning",
        env_key="XAI_API_KEY",
        max_tokens=_XAI_MAX_TOKENS,
        # grok-4-1-fast-non-reasoning: 2M tokens (xAI/서드파티 스펙)
        max_input_chars=int(os.getenv("XAI_MAX_INPUT_CHARS", "0")),
    ),
    "qwen-or": LLMProvider(
        name="OpenRouter",
        api_url="https://openrouter.ai/api/v1/chat/completions",
        model=os.getenv("OPENROUTER_MODEL", "x-ai/grok-4.1-fast"),
        env_key="OPENROUTER_API_KEY",
        max_tokens=_OPENROUTER_MAX_TOKENS,
        max_input_chars=int(os.getenv("OPENROUTER_MAX_INPUT_CHARS", "0")),  # 0 = 무제한 (기본 모델 2M context)
    ),
    "qwen-kilo": LLMProvider(
        name="Kilo",
        api_url="https://api.kilo.ai/api/gateway/chat/completions",
        model=os.getenv("KILO_MODEL", "x-ai/grok-4.1-fast"),
        env_key="KILO_API_KEY",
        max_tokens=_KILO_MAX_TOKENS,
        max_input_chars=int(os.getenv("KILO_MAX_INPUT_CHARS", "0")),  # 0 = 무제한 (기본 모델 2M context)
    ),
    "mimo": LLMProvider(
        name="Xiaomi MiMo",
        api_url=_resolve_mimo_api_url(),
        model="mimo-v2.5-pro",
        env_key="MIMO_API_KEY",
        max_tokens=_MIMO_MAX_TOKENS,
        # mimo-v2.5-pro: 1M context, 최대 출력 128K tokens (platform.xiaomimimo.com)
        max_input_chars=int(os.getenv(
            "MIMO_MAX_INPUT_CHARS",
            str(_input_chars_from_context(1_000_000, _MIMO_MAX_TOKENS)),
        )),
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

    DEFAULT_TIMEOUT = 1200
    DEFAULT_PROVIDER = "minimax"

    def __init__(self):
        # LLM_PROVIDER가 파일에만 있고 값이 비어 있으면 getenv가 ""를 주어
        # 기본값 대신 빈 문자열이 되고, UI 콤보가 첫 항목(glm)으로 떨어지는 문제 방지
        _raw = os.getenv("LLM_PROVIDER")
        if _raw is None:
            self.current_provider = self.DEFAULT_PROVIDER
        else:
            cand = str(_raw).strip()
            self.current_provider = (
                cand if cand in LLM_PROVIDERS else self.DEFAULT_PROVIDER
            )
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

    def _write_env_var(self, env_key: str, value: str) -> None:
        """`.env.local`에 KEY=value 한 줄을 갱신하거나 추가합니다."""
        env_file = self.base_dir / '.env.local'
        lines: list[str] = []
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

        prefix = f"{env_key}="
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(prefix):
                lines[i] = f"{prefix}{value}\n"
                updated = True
                break

        if not updated:
            if lines and not lines[-1].endswith('\n'):
                lines.append('\n')
            lines.append(f"{prefix}{value}\n")

        with open(env_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        os.environ[env_key] = value

    def save_provider_to_env(self, provider: str) -> None:
        """선택한 LLM 제공자를 메모리와 `.env.local`에 저장합니다."""
        self.set_provider(provider)
        self._write_env_var("LLM_PROVIDER", provider)

    def save_api_key_to_env(self, api_key: str, provider: Optional[str] = None) -> None:
        """API 키를 메모리와 `.env.local`에 저장합니다. 빈 값이면 기존 파일 값을 유지합니다."""
        provider = provider or self.current_provider
        provider_info = LLM_PROVIDERS[provider]
        if not provider_info.env_key:
            return

        stripped = api_key.strip()
        if not stripped:
            return

        self.set_api_key(stripped, provider)
        self._write_env_var(provider_info.env_key, stripped)

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
