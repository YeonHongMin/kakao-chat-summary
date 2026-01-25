"""
simple_today_summary.py - 오늘 날짜 대화 간결 요약 모듈

음슴체/단답형으로 짧고 간결한 요약을 생성합니다.
full_today_summary.py의 간소화 버전입니다.

사용법:
    python simple_today_summary.py <filepath>              # 단일 파일
    python simple_today_summary.py <directory>             # 디렉터리 일괄
    python simple_today_summary.py --llm chatgpt <file>    # LLM 지정
    python simple_today_summary.py                         # 대화형 모드
"""

import sys
import io
import os
import logging
import requests

# Windows 콘솔 인코딩 문제 해결 (cp949 -> utf-8)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass


# ============================================================
# 설정 (full_config.py에서 필요한 부분만 내장)
# ============================================================

CURRENT_DIR = Path(__file__).resolve().parent


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


# ============================================================
# 음슴체/단답형 프롬프트 템플릿
# ============================================================

SIMPLE_PROMPT_TEMPLATE = """카카오톡 오픈채팅 대화. 음슴체로 짧게 정리.

### 🌟 한줄요약
핵심 한 문장

### ❓ Q&A
- Q. 질문
  A. 답변 (답변자)

### 💬 주요 토픽
- 주제: 핵심만

### 💡 꿀팁
- 도구, 팁, 단축키

### 🔗 링크
- [닉네임] 설명: URL

### 📢 공지
- 일정, 공지

---
{text}
---

요약:"""


class SimpleConfig:
    """간단한 설정 관리 클래스"""
    
    DEFAULT_TIMEOUT = 180
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

    def get_api_key(self, provider: Optional[str] = None) -> Optional[str]:
        provider = provider or self.current_provider
        provider_info = LLM_PROVIDERS[provider]
        if provider in self._api_keys and self._api_keys[provider]:
            return self._api_keys[provider]
        return os.getenv(provider_info.env_key)

    def set_api_key(self, api_key: str, provider: Optional[str] = None) -> None:
        provider = provider or self.current_provider
        self._api_keys[provider] = api_key.strip()

    def _setup_logging(self) -> None:
        self.logs_dir = self.base_dir / 'logs'
        self.logs_dir.mkdir(exist_ok=True)
        
        log_filename = f"simple_summarizer_{datetime.now().strftime('%Y%m%d')}.log"
        log_path = self.logs_dir / log_filename
        
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(logging.Formatter('%(message)s'))
        
        logger = logging.getLogger("SimpleSummarizer")
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger("SimpleSummarizer")


config = SimpleConfig()
logger = config.logger


# ============================================================
# 파서 (parser.py에서 필요한 부분만 내장)
# ============================================================

@dataclass
class ParseResult:
    """파싱 결과"""
    messages_by_date: Dict[str, List[str]]
    total_messages: int


class SimpleParser:
    """간단한 카카오톡 로그 파서"""
    
    # 카카오톡 날짜 구분선 패턴 (대시로 시작하는 경우만)
    # 예: --------------- 2026년 1월 24일 금요일 ---------------
    DATE_PATTERN = r'-{5,}\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일'
    
    def parse(self, filepath: Path) -> ParseResult:
        import re
        
        messages_by_date: Dict[str, List[str]] = {}
        current_date = None
        total_messages = 0
        
        try:
            content = filepath.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = filepath.read_text(encoding='cp949')
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # 날짜 구분선 검사 (대시로 시작하는 경우만)
            match = re.search(self.DATE_PATTERN, line)
            if match:
                year, month, day = match.groups()
                current_date = f"{year}-{int(month):02d}-{int(day):02d}"
                if current_date not in messages_by_date:
                    messages_by_date[current_date] = []
            elif current_date and self._is_message_line(line):
                messages_by_date[current_date].append(line)
                total_messages += 1
        
        return ParseResult(messages_by_date, total_messages)
    
    def _is_message_line(self, line: str) -> bool:
        import re
        # [닉네임] [시간] 메시지 패턴
        return bool(re.match(r'\[.+?\]\s*\[.+?\]', line))


# ============================================================
# LLM 클라이언트
# ============================================================

class SimpleLLMClient:
    """간단한 LLM API 클라이언트"""
    
    def __init__(self):
        self.provider = config.get_provider_info()
        self.api_key = config.get_api_key()
    
    def summarize(self, text: str) -> str:
        if not self.api_key:
            return "[ERROR] API key not set"
        
        prompt = SIMPLE_PROMPT_TEMPLATE.format(text=text)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.provider.model,
            "messages": [
                {"role": "system", "content": "채팅 요약 전문가. 음슴체로 짧고 핵심만."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        try:
            response = requests.post(
                self.provider.api_url,
                headers=headers,
                json=payload,
                timeout=config.api_timeout
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return self._strip_think_tags(content)
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return f"[ERROR] API 요청 실패: {e}"
        except (KeyError, IndexError) as e:
            logger.error(f"Response parsing failed: {e}")
            return f"[ERROR] 응답 파싱 실패: {e}"

    def _strip_think_tags(self, text: str) -> str:
        """LLM 응답에서 <think>...</think> 태그 제거"""
        import re
        # <think>...</think> 블록 전체 제거
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        return cleaned.strip()


# ============================================================
# URL 추출
# ============================================================

def extract_urls(text: str) -> List[str]:
    """텍스트에서 URL 추출"""
    import re
    url_pattern = r'https?://[^\s\)\]\>\"\']+' 
    urls = re.findall(url_pattern, text)
    return list(set(urls))


# ============================================================
# 메인 요약 클래스
# ============================================================

def get_today_date() -> str:
    """오늘 날짜를 YYYY-MM-DD 형식으로 반환"""
    today = datetime.now()
    return today.strftime("%Y-%m-%d")


class SimpleTodaySummarizer:
    """오늘 날짜 대화 간결 요약 클래스"""
    
    def __init__(self, filepath: Path, provider: Optional[str] = None):
        self.filepath = filepath
        self.parser = SimpleParser()
        self.llm = SimpleLLMClient()
        self.today = get_today_date()
        self.output_file = filepath.parent / f"{filepath.stem}_simple_today_summary.md"

    def run(self) -> bool:
        """오늘 날짜 요약 처리 실행"""
        if not self.filepath.exists():
            logger.error(f"File not found: {self.filepath}")
            return False

        print(f"📄 {self.filepath.name}")

        parse_result = self.parser.parse(self.filepath)
        
        if not parse_result.messages_by_date:
            print(f"   ⚠️  파싱된 메시지 없음")
            return False

        if self.today not in parse_result.messages_by_date:
            print(f"   ℹ️  오늘({self.today}) 대화 없음")
            return False

        messages = parse_result.messages_by_date[self.today]
        msg_count = len(messages)
        
        print(f"   ▶ {self.today} ({msg_count}개) 요약 중...")
        
        chat_content = "\n".join(messages)
        summary = self.llm.summarize(chat_content)
        
        if "[ERROR]" in summary:
            logger.error(f"{self.today} 요약 실패: {summary}")
            print(f"   ❌ 실패 (로그 참조)")
            return False
        
        self._save(msg_count, summary)
        
        print(f"   ✅ 완료: {self.output_file.name}")
        return True

    def _save(self, msg_count: int, summary: str):
        """결과 저장"""
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write(f"# {self.today} 간결 요약\n")
            f.write(f"- 파일: {self.filepath.name}\n")
            f.write(f"- 메시지: {msg_count}개\n")
            f.write(f"- LLM: {config.get_provider_info().name}\n")
            f.write(f"- 생성: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write("---\n\n")
            f.write(summary.strip())
            f.write("\n")




class SimpleBatchProcessor:
    """디렉터리 일괄 처리"""
    
    def __init__(self, directory: Path, provider: Optional[str] = None):
        self.directory = directory
        self.provider = provider
        self.today = get_today_date()

    def get_target_files(self) -> List[Path]:
        all_txt = list(self.directory.glob("*.txt"))
        return sorted([
            f for f in all_txt
            if "_summary" not in f.name 
            and "_url" not in f.name
            and "_summaries" not in f.name
        ])

    def run(self):
        if not self.directory.exists() or not self.directory.is_dir():
            print(f"❌ 디렉터리 오류: {self.directory}")
            return

        files = self.get_target_files()
        
        if not files:
            print(f"❌ 파일 없음")
            return

        print("=" * 50)
        print(f"📅 {self.today} 간결 요약")
        print("=" * 50)
        print(f"📂 {self.directory}")
        print(f"🤖 {config.get_provider_info().name}")
        print(f"📄 {len(files)}개 파일")
        print("=" * 50 + "\n")

        results = []
        for f in files:
            summarizer = SimpleTodaySummarizer(f, self.provider)
            success = summarizer.run()
            results.append((f.name, success))
            print()

        # 결과 출력
        print("=" * 50)
        success_count = sum(1 for _, s in results if s)
        print(f"✅ {success_count}/{len(results)} 완료")


# ============================================================
# CLI
# ============================================================

def prompt_api_key():
    """API 키 입력 프롬프트"""
    if config.get_api_key():
        return

    provider = config.get_provider_info()
    print(f"\n🔑 {provider.name} API Key 필요")
    
    while True:
        try:
            key = input(f"👉 API Key: ").strip()
            if key:
                config.set_api_key(key)
                print("✅ 설정 완료\n")
                break
            print("⚠️ 빈 값 불가")
        except KeyboardInterrupt:
            print("\n❌ 종료")
            sys.exit(0)


def select_llm() -> str:
    """LLM 선택"""
    print("\n🤖 LLM 선택:")
    providers = list(LLM_PROVIDERS.keys())
    for i, key in enumerate(providers, 1):
        print(f"  {i}. {LLM_PROVIDERS[key].name}")
    
    while True:
        choice = input(f"선택 (1-{len(providers)}, 기본=1): ").strip()
        if not choice:
            return providers[0]
        if choice.isdigit() and 1 <= int(choice) <= len(providers):
            return providers[int(choice) - 1]
        print("⚠️ 잘못된 입력")


def parse_args():
    """명령줄 인자 파싱"""
    args = sys.argv[1:]
    provider = None
    target = None
    
    i = 0
    while i < len(args):
        if args[i] == "--llm" and i + 1 < len(args):
            provider = args[i + 1]
            i += 2
        else:
            target = args[i]
            i += 1
    
    return target, provider


def main():
    """메인 함수"""
    today = get_today_date()
    target, provider = parse_args()
    
    if provider:
        if provider not in LLM_PROVIDERS:
            print(f"❌ 알 수 없는 LLM: {provider}")
            print(f"   가능: {', '.join(LLM_PROVIDERS.keys())}")
            sys.exit(1)
        config.set_provider(provider)
    
    print("=" * 50)
    print(f"📅 {today} 간결 요약기 (음슴체)")
    print("=" * 50)
    
    if not target:
        print("Usage: python simple_today_summary.py <file|dir>")
        print("       python simple_today_summary.py --llm chatgpt <file>\n")
        
        selected = select_llm()
        config.set_provider(selected)
        
        data_dir = config.data_dir
        if data_dir.exists():
            files = [f for f in data_dir.glob("*.txt") 
                     if "_summary" not in f.name and "_url" not in f.name]
            
            if files:
                print("\n파일 선택:")
                for i, f in enumerate(files, 1):
                    print(f"  {i}. {f.name}")
                print(f"  A. 전체 처리")
                
                choice = input("\n선택: ").strip()
                
                if choice.upper() == 'A':
                    prompt_api_key()
                    SimpleBatchProcessor(data_dir, selected).run()
                    sys.exit(0)
                elif choice.isdigit() and 1 <= int(choice) <= len(files):
                    prompt_api_key()
                    SimpleTodaySummarizer(files[int(choice)-1], selected).run()
                    sys.exit(0)
        sys.exit(1)

    target_path = Path(target).resolve()
    prompt_api_key()
    
    if target_path.is_dir():
        SimpleBatchProcessor(target_path, provider).run()
    else:
        SimpleTodaySummarizer(target_path, provider).run()


if __name__ == "__main__":
    main()
