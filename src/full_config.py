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


# 지원하는 LLM 제공자 목록
LLM_PROVIDERS: Dict[str, LLMProvider] = {
    "glm": LLMProvider(
        name="Z.AI GLM",
        api_url="https://api.z.ai/api/coding/paas/v4/chat/completions",
        model="glm-4.7",
        env_key="ZAI_API_KEY"
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
        model="MiniMax-M2.1",
        env_key="MINIMAX_API_KEY"
    ),
    "perplexity": LLMProvider(
        name="Perplexity",
        api_url="https://api.perplexity.ai/chat/completions",
        model="sonar",
        env_key="PERPLEXITY_API_KEY"
    ),
}


class Config:
    """애플리케이션 설정을 관리하는 싱글톤 클래스."""
    
    DEFAULT_TIMEOUT = 600
    DEFAULT_PROVIDER = "glm"

    PROMPT_TEMPLATE = """다음은 카카오톡 오픈채팅방의 대화 내용입니다.
이 대화방은 정보 공유와 토론을 목적으로 합니다.
대화에 등장한 모든 질문, 토픽, 팁, 링크를 빠짐없이 포함하여 다음 섹션으로 체계적으로 정리해주세요.
내용을 생략하거나 축약하지 말고, 각 섹션에 해당하는 내용을 모두 기록해주세요.

⚠️ 중복 방지 규칙 (빠짐없이 기록하되, 같은 내용을 여러 섹션에 반복하지 않기):
1. 하나의 내용은 가장 적합한 섹션 하나에만 기록할 것
2. Q&A에 포함된 내용은 토픽에서 반복하지 않을 것
3. 꿀팁에 포함된 도구/링크는 링크 섹션에서 URL만 나열할 것
4. 판단이 어려우면 Q&A보다 토픽을, 토픽보다 꿀팁을 우선할 것

### 🌟 3줄 요약
전체 대화의 핵심 흐름과 분위기를 3문장으로 요약

### ❓ Q&A (명시적 질문-답변만)
- 누군가 물음표(?)로 직접 질문한 내용과 그에 대한 답변만 기록
- 같은 주제의 질문이 여러 번이면 대표 질문 1개로 통합
- 답변자가 여러 명이면 핵심 답변 위주로 정리
- 답변이 없는 질문은 "A. (미해결)" 로 표시
- Q. [질문 내용]
  A. [답변/해결책] (답변자 닉네임)

### 💬 주요 토픽 & 논의 (Q&A 제외한 논의만)
- Q&A에 이미 포함된 내용은 제외
- 질문이 아닌 논의, 의견 교환, 정보 공유만 기록
- [주제]: 논의된 내용, 주요 의견, 결론

### 💡 꿀팁 및 도구 추천 (구체적 실용 정보만)
- 구체적 도구명, 명령어, 설정값, 단축키가 포함된 실용 정보만 기록
- 일반적인 의견이나 추상적 조언은 토픽 섹션에 배치
- 추천받은 라이브러리, 유용한 단축키, 명령어, 팁 등

### 🔗 링크/URL
- [발언자] 공유된 중요 링크 설명: https://...
(이 섹션 헤더는 정확히 '### 링크/URL'로 작성하고, 각 링크는 '- '로 알기 쉽게 나열해주세요. URL 추출 스크립트가 인식해야 합니다.)

### 📅 일정 및 공지
일정, 모임, 주요 공지사항 (해당 없으면 "없음"으로 표시)

---
{text}
---

요약:"""

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
        
        # 파일 핸들러 (상세 로그)
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
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
        logger.addHandler(console_handler)

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger("KakaoSummarizer")


config = Config()
