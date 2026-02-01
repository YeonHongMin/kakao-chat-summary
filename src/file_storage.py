"""
file_storage.py - 일별 파일 저장 모듈

디렉토리 구조:
    data/
    ├── original/           # 원본 대화 (일별)
    │   └── <채팅방>/
    │       ├── <채팅방>_20260131_full.md
    │       └── <채팅방>_20260130_full.md
    ├── summary/            # LLM 요약 (일별)
    │   └── <채팅방>/
    │       ├── <채팅방>_20260131_summary.md
    │       └── <채팅방>_20260130_summary.md
    └── url/                # URL 목록
        └── <채팅방>/
            └── <채팅방>_urls.md
"""

import os
import re
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Optional, Set
from collections import defaultdict


class FileStorage:
    """일별 파일 저장 관리 클래스."""
    
    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            base_dir = Path(__file__).parent.parent / "data"
        
        self.base_dir = base_dir
        self.original_dir = base_dir / "original"
        self.summary_dir = base_dir / "summary"
        self.url_dir = base_dir / "url"
        
        # 디렉토리 생성
        self.original_dir.mkdir(parents=True, exist_ok=True)
        self.summary_dir.mkdir(parents=True, exist_ok=True)
        self.url_dir.mkdir(parents=True, exist_ok=True)
    
    # ==================== Original (원본 대화) ====================
    
    def save_daily_original(self, room_name: str, date_str: str, messages: List[str]) -> Path:
        """
        일별 원본 대화 저장 (중복 merge).
        
        Args:
            room_name: 채팅방 이름
            date_str: 날짜 (YYYY-MM-DD)
            messages: 메시지 목록
        
        Returns:
            저장된 파일 경로
        """
        # 디렉토리 생성
        room_dir = self.original_dir / self._sanitize_name(room_name)
        room_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일명: <채팅방>_yyyymmdd_full.md
        date_compact = date_str.replace("-", "")
        filename = f"{self._sanitize_name(room_name)}_{date_compact}_full.md"
        filepath = room_dir / filename
        
        # 기존 내용 로드 (있으면)
        existing_messages = self._load_existing_messages(filepath)
        
        # 중복 제거 및 merge
        merged_messages = self._merge_messages(existing_messages, messages)
        
        # 파일 저장
        content = self._format_original_content(room_name, date_str, merged_messages)
        filepath.write_text(content, encoding='utf-8')
        
        return filepath
    
    def save_all_daily_originals(self, room_name: str, messages_by_date: Dict[str, List[str]]) -> List[Path]:
        """모든 날짜의 원본 대화 저장."""
        saved_files = []
        
        for date_str in sorted(messages_by_date.keys()):
            messages = messages_by_date[date_str]
            filepath = self.save_daily_original(room_name, date_str, messages)
            saved_files.append(filepath)
        
        return saved_files
    
    def load_daily_original(self, room_name: str, date_str: str) -> List[str]:
        """일별 원본 대화 로드."""
        room_dir = self.original_dir / self._sanitize_name(room_name)
        date_compact = date_str.replace("-", "")
        filename = f"{self._sanitize_name(room_name)}_{date_compact}_full.md"
        filepath = room_dir / filename
        
        return self._load_existing_messages(filepath)
    
    def load_all_originals(self, room_name: str) -> Dict[str, List[str]]:
        """채팅방의 모든 원본 대화 로드."""
        room_dir = self.original_dir / self._sanitize_name(room_name)
        if not room_dir.exists():
            return {}
        
        messages_by_date = {}
        
        for filepath in room_dir.glob("*_full.md"):
            # 파일명에서 날짜 추출
            match = re.search(r'_(\d{8})_full\.md$', filepath.name)
            if match:
                date_compact = match.group(1)
                date_str = f"{date_compact[:4]}-{date_compact[4:6]}-{date_compact[6:8]}"
                messages = self._load_existing_messages(filepath)
                if messages:
                    messages_by_date[date_str] = messages
        
        return messages_by_date
    
    def get_available_dates(self, room_name: str) -> List[str]:
        """채팅방의 사용 가능한 날짜 목록."""
        room_dir = self.original_dir / self._sanitize_name(room_name)
        if not room_dir.exists():
            return []
        
        dates = []
        for filepath in room_dir.glob("*_full.md"):
            match = re.search(r'_(\d{8})_full\.md$', filepath.name)
            if match:
                date_compact = match.group(1)
                date_str = f"{date_compact[:4]}-{date_compact[4:6]}-{date_compact[6:8]}"
                dates.append(date_str)
        
        return sorted(dates)
    
    # ==================== Summary (LLM 요약) ====================
    
    def save_daily_summary(self, room_name: str, date_str: str, 
                           summary_content: str, llm_provider: str = "Unknown") -> Path:
        """
        일별 LLM 요약 저장.
        
        Args:
            room_name: 채팅방 이름
            date_str: 날짜 (YYYY-MM-DD)
            summary_content: 요약 내용
            llm_provider: LLM 제공자
        
        Returns:
            저장된 파일 경로
        """
        # 디렉토리 생성
        room_dir = self.summary_dir / self._sanitize_name(room_name)
        room_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일명: <채팅방>_yyyymmdd_summary.md
        date_compact = date_str.replace("-", "")
        filename = f"{self._sanitize_name(room_name)}_{date_compact}_summary.md"
        filepath = room_dir / filename
        
        # 파일 저장
        content = self._format_summary_content(room_name, date_str, summary_content, llm_provider)
        filepath.write_text(content, encoding='utf-8')
        
        return filepath
    
    def load_daily_summary(self, room_name: str, date_str: str) -> Optional[str]:
        """일별 요약 로드."""
        room_dir = self.summary_dir / self._sanitize_name(room_name)
        date_compact = date_str.replace("-", "")
        filename = f"{self._sanitize_name(room_name)}_{date_compact}_summary.md"
        filepath = room_dir / filename
        
        if filepath.exists():
            return filepath.read_text(encoding='utf-8')
        return None
    
    def has_summary(self, room_name: str, date_str: str) -> bool:
        """해당 날짜의 요약이 있는지 확인."""
        room_dir = self.summary_dir / self._sanitize_name(room_name)
        date_compact = date_str.replace("-", "")
        filename = f"{self._sanitize_name(room_name)}_{date_compact}_summary.md"
        filepath = room_dir / filename
        return filepath.exists()
    
    def delete_daily_summary(self, room_name: str, date_str: str) -> bool:
        """해당 날짜의 요약 삭제."""
        room_dir = self.summary_dir / self._sanitize_name(room_name)
        date_compact = date_str.replace("-", "")
        filename = f"{self._sanitize_name(room_name)}_{date_compact}_summary.md"
        filepath = room_dir / filename
        
        if filepath.exists():
            filepath.unlink()
            return True
        return False
    
    def get_original_message_count(self, room_name: str, date_str: str) -> int:
        """특정 날짜의 원본 메시지 수 반환."""
        messages = self.load_daily_original(room_name, date_str)
        return len(messages)
    
    def get_summarized_dates(self, room_name: str) -> List[str]:
        """요약된 날짜 목록."""
        room_dir = self.summary_dir / self._sanitize_name(room_name)
        if not room_dir.exists():
            return []
        
        dates = []
        for filepath in room_dir.glob("*_summary.md"):
            match = re.search(r'_(\d{8})_summary\.md$', filepath.name)
            if match:
                date_compact = match.group(1)
                date_str = f"{date_compact[:4]}-{date_compact[4:6]}-{date_compact[6:8]}"
                dates.append(date_str)
        
        return sorted(dates)
    
    # ==================== 채팅방 관리 ====================
    
    def get_all_rooms(self) -> List[str]:
        """모든 채팅방 목록 (original, summary, url 디렉터리 스캔)."""
        rooms = set()

        # original 디렉토리에서
        if self.original_dir.exists():
            for d in self.original_dir.iterdir():
                if d.is_dir():
                    rooms.add(d.name)

        # summary 디렉토리에서
        if self.summary_dir.exists():
            for d in self.summary_dir.iterdir():
                if d.is_dir():
                    rooms.add(d.name)

        # url 디렉토리에서
        if self.url_dir.exists():
            for d in self.url_dir.iterdir():
                if d.is_dir():
                    rooms.add(d.name)

        return sorted(rooms)
    
    def get_room_stats(self, room_name: str) -> Dict:
        """채팅방 통계."""
        safe_name = self._sanitize_name(room_name)
        original_dates = self.get_available_dates(room_name)
        summary_dates = self.get_summarized_dates(room_name)
        
        return {
            'room_name': room_name,
            'total_days': len(original_dates),
            'summarized_days': len(summary_dates),
            'unsummarized_days': len(set(original_dates) - set(summary_dates)),
            'date_range': (original_dates[0], original_dates[-1]) if original_dates else (None, None)
        }
    
    def get_dates_needing_summary(self, room_name: str) -> Dict[str, str]:
        """
        요약이 필요한 날짜 목록 반환.

        요약 파일이 없는 날짜만 "new"로 반환.
        메시지가 추가된 경우는 업로드 시 invalidate_summary_if_updated()에서
        요약 파일을 삭제하므로, 여기서는 존재 여부만 확인하면 됨.

        Returns:
            Dict[date_str, reason]: 날짜별 요약 필요 사유
            - "new": 새로운 날짜 (요약 없음)
        """
        result = {}
        original_dates = self.get_available_dates(room_name)
        summarized_dates = set(self.get_summarized_dates(room_name))

        for date_str in original_dates:
            if date_str not in summarized_dates:
                result[date_str] = "new"

        return result
    
    def invalidate_summary_if_updated(self, room_name: str, date_str: str, 
                                       old_count: int, new_count: int) -> bool:
        """
        원본 메시지가 업데이트되면 기존 요약 무효화.
        
        Returns:
            True if summary was invalidated
        """
        if new_count > old_count and self.has_summary(room_name, date_str):
            self.delete_daily_summary(room_name, date_str)
            return True
        return False
    
    def _get_original_path(self, room_name: str, date_str: str) -> Path:
        """원본 파일 경로 반환."""
        room_dir = self.original_dir / self._sanitize_name(room_name)
        date_compact = date_str.replace("-", "")
        filename = f"{self._sanitize_name(room_name)}_{date_compact}_full.md"
        return room_dir / filename
    
    def _get_summary_path(self, room_name: str, date_str: str) -> Path:
        """요약 파일 경로 반환."""
        room_dir = self.summary_dir / self._sanitize_name(room_name)
        date_compact = date_str.replace("-", "")
        filename = f"{self._sanitize_name(room_name)}_{date_compact}_summary.md"
        return room_dir / filename
    
    def create_room_directories(self, room_name: str) -> None:
        """채팅방 디렉토리 생성."""
        safe_name = self._sanitize_name(room_name)
        (self.original_dir / safe_name).mkdir(parents=True, exist_ok=True)
        (self.summary_dir / safe_name).mkdir(parents=True, exist_ok=True)
    
    # ==================== 내부 헬퍼 메서드 ====================
    
    def _sanitize_name(self, name: str) -> str:
        """파일/디렉토리 이름에 사용 가능하도록 정리."""
        # 특수문자 제거, 공백은 _로 대체
        sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
        sanitized = sanitized.replace(' ', '_')
        return sanitized.strip()
    
    def _load_existing_messages(self, filepath: Path) -> List[str]:
        """기존 파일에서 메시지 로드."""
        if not filepath.exists():
            return []
        
        content = filepath.read_text(encoding='utf-8')
        
        # 메타데이터 이후의 내용 추출
        lines = content.split('\n')
        start_idx = 0
        
        for i, line in enumerate(lines):
            if line.strip() == '---' and i > 0:
                start_idx = i + 1
                break
        
        # 푸터 제거
        messages = []
        for line in lines[start_idx:]:
            if line.strip().startswith('_Generated'):
                break
            if line.strip():
                messages.append(line)
        
        return messages
    
    def _merge_messages(self, existing: List[str], new: List[str]) -> List[str]:
        """기존 메시지와 새 메시지 merge (중복 제거)."""
        # 메시지를 해시로 관리하여 중복 제거
        seen = set()
        merged = []
        
        for msg in existing + new:
            msg_hash = hash(msg.strip())
            if msg_hash not in seen:
                seen.add(msg_hash)
                merged.append(msg)
        
        return merged
    
    def _format_original_content(self, room_name: str, date_str: str, 
                                  messages: List[str]) -> str:
        """원본 파일 포맷."""
        header = f"""# 📅 {room_name} - {date_str}
- **채팅방**: {room_name}
- **날짜**: {date_str}
- **메시지 수**: {len(messages)}개
- **저장 시각**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

"""
        content = "\n".join(messages)
        footer = "\n\n---\n_Generated by KakaoTalk Chat Summary_\n"
        
        return header + content + footer
    
    def _format_summary_content(self, room_name: str, date_str: str,
                                 summary: str, llm_provider: str) -> str:
        """요약 파일 포맷."""
        header = f"""# 📝 {room_name} 요약 - {date_str}
- **채팅방**: {room_name}
- **날짜**: {date_str}
- **LLM**: {llm_provider}
- **생성 시각**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

"""
        footer = "\n\n---\n_Generated by AI Assistant_\n"
        
        return header + summary + footer
    
    # ==================== URL 관리 ====================
    
    def _write_url_file(self, filepath: Path, room_name: str, urls: Dict[str, List[str]], 
                        title: str, period_info: str) -> None:
        """URL 파일 작성 헬퍼."""
        sorted_urls = sorted(urls.items(), key=lambda x: x[0].lower())
        
        content = f"""# {title}

- **채팅방**: {room_name}
- **기간**: {period_info}
- **URL 개수**: {len(urls)}개
- **최종 업데이트**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

"""
        for i, (url, descriptions) in enumerate(sorted_urls, 1):
            desc_text = " / ".join(descriptions) if descriptions else ""
            if desc_text:
                content += f"{i}. {url}\n   - 💬 {desc_text}\n"
            else:
                content += f"{i}. {url}\n"
        
        filepath.write_text(content, encoding='utf-8')
    
    def save_url_lists(self, room_name: str, 
                       urls_recent: Dict[str, List[str]],
                       urls_weekly: Dict[str, List[str]],
                       urls_all: Dict[str, List[str]]) -> Dict[str, Path]:
        """
        채팅방의 URL 목록을 3개 파일로 저장.
        
        Args:
            room_name: 채팅방 이름
            urls_recent: 최근 3일 URL {url: [descriptions]}
            urls_weekly: 최근 1주 URL {url: [descriptions]}
            urls_all: 전체 URL {url: [descriptions]}
        
        Returns:
            {'recent': Path, 'weekly': Path, 'all': Path}
        """
        room_dir = self.url_dir / self._sanitize_name(room_name)
        room_dir.mkdir(parents=True, exist_ok=True)
        
        sanitized = self._sanitize_name(room_name)
        
        # 3개 파일 저장
        paths = {}
        
        # 1. 최근 3일
        recent_path = room_dir / f"{sanitized}_urls_recent.md"
        self._write_url_file(recent_path, room_name, urls_recent, 
                             "🔥 최근 3일 URL", "최근 3일")
        paths['recent'] = recent_path
        
        # 2. 최근 1주
        weekly_path = room_dir / f"{sanitized}_urls_weekly.md"
        self._write_url_file(weekly_path, room_name, urls_weekly,
                             "📅 최근 1주 URL", "최근 7일")
        paths['weekly'] = weekly_path
        
        # 3. 전체
        all_path = room_dir / f"{sanitized}_urls_all.md"
        self._write_url_file(all_path, room_name, urls_all,
                             "📚 전체 URL", "전체 기간")
        paths['all'] = all_path
        
        return paths
    
    def load_url_list(self, room_name: str, list_type: str = "all") -> Dict[str, List[str]]:
        """
        채팅방의 URL 목록 로드.
        
        Args:
            room_name: 채팅방 이름
            list_type: 'recent', 'weekly', 'all' 중 하나
        
        Returns:
            {url: [descriptions]} 딕셔너리
        """
        room_dir = self.url_dir / self._sanitize_name(room_name)
        sanitized = self._sanitize_name(room_name)
        filepath = room_dir / f"{sanitized}_urls_{list_type}.md"
        
        if not filepath.exists():
            return {}
        
        urls = {}
        current_url = None
        
        for line in filepath.read_text(encoding='utf-8').split('\n'):
            line = line.strip()
            
            # URL 라인 (1. http... 또는 - http...)
            if '. http' in line or line.startswith('- http'):
                # 번호 제거
                if '. http' in line:
                    url_start = line.find('http')
                    current_url = line[url_start:].strip()
                else:
                    current_url = line[2:].strip()
                urls[current_url] = []
            # 설명 라인 (- 💬 ...)
            elif '💬' in line and current_url:
                desc_start = line.find('💬') + 2
                desc = line[desc_start:].strip()
                if desc:
                    for d in desc.split(' / '):
                        if d and d not in urls[current_url]:
                            urls[current_url].append(d)
        
        return urls
    
    def get_url_file_info(self, room_name: str) -> Optional[Dict]:
        """
        URL 파일 정보 반환.
        
        Returns:
            {'recent': info, 'weekly': info, 'all': info} 또는 None
        """
        room_dir = self.url_dir / self._sanitize_name(room_name)
        sanitized = self._sanitize_name(room_name)
        
        result = {}
        for list_type in ['recent', 'weekly', 'all']:
            filepath = room_dir / f"{sanitized}_urls_{list_type}.md"
            if filepath.exists():
                urls = self.load_url_list(room_name, list_type)
                stat = filepath.stat()
                result[list_type] = {
                    'path': filepath,
                    'modified': datetime.fromtimestamp(stat.st_mtime),
                    'count': len(urls)
                }
        
        return result if result else None


# 싱글톤 인스턴스
_storage_instance: Optional[FileStorage] = None


def get_storage() -> FileStorage:
    """FileStorage 싱글톤 인스턴스 반환."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = FileStorage()
    return _storage_instance
