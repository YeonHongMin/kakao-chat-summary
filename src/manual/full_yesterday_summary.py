"""
full_yesterday_summary.py - 전체 기간 대화 요약 모듈

파일 내에 존재하는 모든 날짜의 대화를 날짜별로 구분하여 요약을 생성합니다.
(기존 어제 날짜 요약 기능에서 전체 기간 요약으로 확장됨)

사용법:
    python full_yesterday_summary.py <filepath>              # 단일 파일
    python full_yesterday_summary.py <directory>             # 디렉터리 일괄
    python full_yesterday_summary.py --llm chatgpt <file>    # LLM 지정
    python full_yesterday_summary.py                         # 대화형 모드
"""

import sys
import io
from pathlib import Path

# 상위 디렉터리 모듈 import를 위한 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# Windows 콘솔 인코딩 문제 해결 (cp949 -> utf-8)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

from full_config import config, LLM_PROVIDERS
from parser import KakaoLogParser
from chat_processor import ChatProcessor
from url_extractor import extract_urls_from_text, save_urls_to_file

logger = config.logger


class FullLogSummarizer:
    """파일 내 모든 날짜의 대화를 요약하는 클래스."""
    
    def __init__(self, filepath: Path, provider: Optional[str] = None):
        self.filepath = filepath
        self.parser = KakaoLogParser()
        self.processor = ChatProcessor(provider)
        # 출력 파일명 변경: _full_yesterday.md -> _full_summary.md (전체 요약 의미)
        self.output_file = filepath.parent / f"{filepath.stem}_full_summary.md"

    def run(self) -> bool:
        """전체 날짜 요약 처리를 실행."""
        if not self.filepath.exists():
            logger.error(f"File not found: {self.filepath}")
            return False

        print(f"📄 파일: {self.filepath.name}")

        logger.info(f"Parsing file: {self.filepath.name}...")
        parse_result = self.parser.parse(self.filepath)
        
        # 날짜 필터링: 어제와 오늘만
        today_date = datetime.now().strftime("%Y-%m-%d")
        yesterday_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        all_dates = sorted(parse_result.messages_by_date.keys())
        target_dates = [d for d in all_dates if d >= yesterday_date]  # 어제 이후의 날짜만 (어제, 오늘)
        
        print(f"   📅 전체 날짜: {len(all_dates)}일")
        print(f"   🎯 대상 날짜 (어제~오늘): {len(target_dates)}일 ({', '.join(target_dates)})")
        
        if not target_dates:
            print(f"   ⚠️  어제와 오늘 날짜의 대화가 없습니다.")
            return False
            
        summary_results: List[Tuple[str, int, str]] = [] # (date, msg_count, summary)
        
        for date in target_dates:
            messages = parse_result.messages_by_date[date]
            msg_count = len(messages)
            
            print(f"   ▶ {date} ({msg_count}개 메시지) 요약 중...")
            
            chat_content = "\n".join(messages)
            summary_result = self.processor.process_summary(chat_content)
            
            if "[ERROR]" in summary_result:
                logger.error(f"{date} 요약 실패: {summary_result}")
                print(f"     ❌ 실패 (로그 참조)")
                # 실패해도 계속 진행할지 여부: 여기서는 실패 메시지를 포함하여 진행
                summary_results.append((date, msg_count, f"❌ 요약 실패: {summary_result}"))
            else:
                summary_results.append((date, msg_count, summary_result))
        
        self._save_all_summaries(summary_results)
        
        print(f"   ✅ 완료: {self.output_file.name}")
        return True

    def _save_all_summaries(self, results: List[Tuple[str, int, str]]):
        """모든 날짜의 요약 결과를 파일 하나에 저장."""
        total_msgs = sum(r[1] for r in results)
        dates = [r[0] for r in results]
        date_range = f"{dates[0]} ~ {dates[-1]}" if len(dates) > 1 else dates[0]

        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write(f"# 📚 카카오톡 대화 통합 요약\n")
            f.write(f"- **원본 파일**: {self.filepath.name}\n")
            f.write(f"- **대화 기간**: {date_range}\n")
            f.write(f"- **총 메시지 수**: {total_msgs}개\n")
            f.write(f"- **LLM**: {config.get_provider_info().name}\n")
            f.write(f"- **생성 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("---\n")
            
            for date, count, summary in results:
                f.write(f"\n## 📅 {date} ({count}개 메시지)\n\n")
                clean_summary = self._strip_headers(summary)
                f.write(clean_summary)
                f.write("\n\n---\n")
            
            f.write("_Generated by AI Assistant_\n")

    def _strip_headers(self, text: str) -> str:
        # 기존 요약 텍스트에서 불필요한 상단 헤더(# 제목 등)와 하단 서명을 제거하여 깔끔하게 합침
        lines = text.split('\n')
        start_idx = 0
        end_idx = len(lines)
        
        # 실제 내용이 시작되는 지점 찾기 (### 등으로 시작하는 소제목)
        for i, line in enumerate(lines):
            if line.strip().startswith("###"):
                start_idx = i
                break
        
        # 하단 서명 제거
        for i in range(len(lines)-1, -1, -1):
            if "_Generated by" in lines[i]:
                end_idx = i
                break
                
        # 만약 ###를 못찾았으면 전체 반환 (단, 제목인 #은 제외하도록 노력)
        if start_idx == 0:
            for i, line in enumerate(lines):
                if line.strip().startswith("# "):
                    continue # 메인 제목 건너뛰기
                if line.strip().startswith("- **"):
                    continue # 메타 데이터 건너뛰기
                if line.strip() == "---":
                    start_idx = i + 1
                    # --- 다음 줄부터 내용일 확률 높음
                if i > 10: break # 너무 많이 건너뛰지 않음
        
        return "\n".join(lines[start_idx:end_idx]).strip() if start_idx < end_idx else text


class BatchProcessor:
    """디렉터리 내 모든 파일 일괄 처리 (전체 기간)."""
    
    def __init__(self, directory: Path, provider: Optional[str] = None):
        self.directory = directory
        self.provider = provider

    def get_target_files(self) -> List[Path]:
        all_txt_files = list(self.directory.glob("*.txt"))
        
        target_files = [
            f for f in all_txt_files
            if "_summary" not in f.name 
            and "_url" not in f.name
            and "_summaries" not in f.name
        ]
        
        return sorted(target_files)

    def run(self):
        if not self.directory.exists() or not self.directory.is_dir():
            print(f"❌ 유효하지 않은 디렉터리: {self.directory}")
            return

        target_files = self.get_target_files()
        
        if not target_files:
            print(f"❌ 처리할 파일이 없습니다.")
            return

        print("="*60)
        print("📅 전체 기간 대화 일괄 요약")
        print("="*60)
        print(f"📂 디렉터리: {self.directory}")
        print(f"🤖 LLM: {config.get_provider_info().name}")
        print(f"📄 파일 수: {len(target_files)}개")
        print("="*60 + "\n")

        results = []
        
        for filepath in target_files:
            summarizer = FullLogSummarizer(filepath, self.provider)
            success = summarizer.run()
            results.append((filepath.name, success))
            print()

        self._print_results(results)

    def _print_results(self, results: List[tuple]):
        print("="*60)
        print("📋 처리 결과")
        print("="*60)
        
        success_count = sum(1 for _, success in results if success)
        skip_count = len(results) - success_count
        
        for filename, success in results:
            status = "✅ 성공" if success else "⏭️  스킵"
            print(f"  {status}: {filename}")
        
        print("-"*60)
        print(f"총 {len(results)}개 | ✅ 성공: {success_count} | ⏭️  스킵: {skip_count}")


def prompt_api_key():
    """API 키가 설정되지 않은 경우 대화형으로 입력 요청."""
    if config.get_api_key():
        return

    provider_info = config.get_provider_info()
    print("\n" + "="*50)
    print(f"🔑 API 인증 설정 ({provider_info.name})")
    print("="*50)
    print(f"환경 변수 {provider_info.env_key}가 설정되지 않았습니다.")
    
    while True:
        try:
            input_key = input(f"👉 {provider_info.name} API Key: ").strip()
            if input_key:
                config.set_api_key(input_key)
                print("✅ API Key가 설정되었습니다.\n")
                break
            else:
                print("⚠️  API Key는 비어있을 수 없습니다.")
        except KeyboardInterrupt:
            print("\n❌ 프로그램을 종료합니다.")
            sys.exit(0)


def select_llm_provider() -> str:
    """LLM 제공자 선택 프롬프트."""
    print("\n🤖 LLM 제공자 선택:")
    providers = list(LLM_PROVIDERS.keys())
    for i, key in enumerate(providers, 1):
        info = LLM_PROVIDERS[key]
        print(f"  {i}. {info.name} ({key})")
    
    while True:
        choice = input(f"\n선택 (1-{len(providers)}, 기본=1): ").strip()
        if not choice:
            return providers[0]
        if choice.isdigit() and 1 <= int(choice) <= len(providers):
            return providers[int(choice) - 1]
        print("⚠️ 올바른 번호를 선택하세요.")


def parse_args():
    """명령줄 인자 파싱."""
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
    """메인 진입점 함수."""
    target, provider = parse_args()
    
    # LLM 제공자 설정
    if provider:
        if provider not in LLM_PROVIDERS:
            print(f"❌ 알 수 없는 LLM: {provider}")
            print(f"   사용 가능: {', '.join(LLM_PROVIDERS.keys())}")
            sys.exit(1)
        config.set_provider(provider)
    
    print("="*50)
    print(f"📅 전체 기간 대화 요약기 (모든 날짜)")
    print("="*50)
    
    # 명령줄 인자 없으면 대화형 모드
    if not target:
        print("Usage:")
        print("  python full_yesterday_summary.py <file>")
        print("  python full_yesterday_summary.py <directory>")
        print("  python full_yesterday_summary.py --llm chatgpt <file>\n")
        
        # LLM 선택
        selected_provider = select_llm_provider()
        config.set_provider(selected_provider)
        
        # 파일/디렉터리 선택
        data_dir = config.data_dir
        if data_dir.exists():
            files = list(data_dir.glob("*.txt"))
            txt_files = [f for f in files if "_summary" not in f.name and "_url" not in f.name]
            
            if txt_files:
                print("\nAvailable files:")
                for i, f in enumerate(txt_files, 1):
                    print(f"  {i}. {f.name}")
                print(f"  A. 전체 디렉터리 처리")
                
                choice = input("\nSelect (number/A/Enter to exit): ").strip()
                
                if choice.upper() == 'A':
                    prompt_api_key()
                    processor = BatchProcessor(data_dir, selected_provider)
                    processor.run()
                    sys.exit(0)
                elif choice.isdigit() and 1 <= int(choice) <= len(txt_files):
                    target_file = txt_files[int(choice)-1]
                    prompt_api_key()
                    summarizer = FullLogSummarizer(target_file, selected_provider)
                    summarizer.run()
                    sys.exit(0)
        sys.exit(1)

    # 명령줄 인자로 경로가 주어진 경우
    target_path = Path(target).resolve()
    prompt_api_key()
    
    if target_path.is_dir():
        processor = BatchProcessor(target_path, provider)
        processor.run()
    else:
        summarizer = FullLogSummarizer(target_path, provider)
        summarizer.run()


if __name__ == "__main__":
    main()
