"""
parser.py - 카카오톡 대화 로그 파싱 모듈

이 모듈은 카카오톡에서 내보낸 텍스트 파일을 파싱하여
날짜별로 메시지를 그룹화하는 기능을 제공합니다.

지원하는 카카오톡 내보내기 형식:
- PC/Mac: --------------- 2024년 1월 24일 수요일 ---------------
- 모바일: 2024년 1월 24일 수요일
- 심플: 2024. 1. 24.
"""

from typing import List, Dict, Optional
import re
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ParseResult:
    """
    파싱 결과를 담는 데이터 클래스.
    
    Attributes:
        messages_by_date: 날짜별로 그룹화된 메시지 딕셔너리 {"YYYY-MM-DD": [메시지 목록]}
        total_dates: 파싱된 총 날짜 수
    """
    messages_by_date: Dict[str, List[str]]
    total_dates: int


class KakaoLogParser:
    """
    카카오톡 대화 로그 파서 클래스.
    
    다양한 카카오톡 내보내기 형식을 지원하며,
    날짜 헤더를 인식하여 메시지를 날짜별로 그룹화합니다.
    """
    
    # 날짜 헤더 패턴 목록 (대시 구분선이 있는 형식만 인식)
    # 대화 내용 안의 날짜 오인식 방지를 위해 대시로 시작하는 경우만 처리
    DATE_HEADER_PATTERNS = [
        # PC/Mac 형식: --------------- 2024년 1월 24일 수요일 ---------------
        re.compile(r'-{5,}\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일.*', re.IGNORECASE),
        # 심플 형식 (대시로 시작): ----- 2024. 1. 24. -----
        re.compile(r'-{5,}\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?\s*-*'),
    ]
    
    # 메시지 라인에 날짜가 포함된 형식 (PC 구버전 등)
    # 예: 2024. 1. 24. 오후 2:00, 닉네임 : 내용
    MSG_PATTERN_DATE_INCLUDED = re.compile(
        r'^(\d{4}[년.]\s*\d{1,2}[월.]\s*\d{1,2}[일.]).*?,\s*(.*?):(.*)$'
    )

    def parse(self, filepath: Path) -> ParseResult:
        """
        카카오톡 텍스트 파일을 파싱하여 날짜별 메시지를 추출합니다.
        
        Args:
            filepath: 파싱할 텍스트 파일 경로
            
        Returns:
            ParseResult: 파싱 결과 (날짜별 메시지 딕셔너리와 총 날짜 수)
        """
        try:
            text = filepath.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            text = filepath.read_text(encoding='cp949', errors='replace')
        lines = text.splitlines()
        
        messages_by_date = defaultdict(list)
        current_date = None  # 현재 처리 중인 날짜
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 1. 날짜 헤더인지 확인
            parsed_date = self._try_parse_date_header(line)
            if parsed_date:
                current_date = parsed_date
                continue
            
            # 2. 메시지 라인에 날짜가 포함되어 있는지 확인 (PC 구버전 형식)
            embedded_date = self._try_parse_embedded_date(line)
            if embedded_date:
                current_date = embedded_date
            
            # 3. 현재 날짜가 있으면 해당 날짜에 메시지 추가
            if current_date:
                messages_by_date[current_date].append(line)

        return ParseResult(
            messages_by_date=dict(messages_by_date),
            total_dates=len(messages_by_date)
        )

    def _try_parse_date_header(self, line: str) -> Optional[str]:
        """
        라인이 날짜 헤더인지 확인하고, 날짜를 추출합니다.
        
        Args:
            line: 확인할 텍스트 라인
            
        Returns:
            날짜 문자열 (YYYY-MM-DD) 또는 None
        """
        for pattern in self.DATE_HEADER_PATTERNS:
            match = pattern.search(line)
            if match:
                try:
                    y, m, d = match.groups()
                    # 날짜를 YYYY-MM-DD 형식으로 정규화
                    return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
                except (ValueError, IndexError):
                    pass
        return None

    def _try_parse_embedded_date(self, line: str) -> Optional[str]:
        """
        메시지 라인에 포함된 날짜를 추출합니다.
        
        일부 카카오톡 내보내기 형식에서는 각 메시지 라인에 날짜가 포함됩니다.
        예: "2024. 1. 24. 오후 2:00, 닉네임 : 내용"
        
        Args:
            line: 확인할 텍스트 라인
            
        Returns:
            날짜 문자열 (YYYY-MM-DD) 또는 None
        """
        match = self.MSG_PATTERN_DATE_INCLUDED.match(line)
        if match:
            try:
                # 날짜 부분 추출 후 정규화
                date_str = match.group(1).translate(str.maketrans({
                    "년": "-", "월": "-", "일": "", ".": "-", " ": ""
                }))
                parts = [p for p in date_str.split('-') if p]
                if len(parts) >= 3:
                    return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
            except (ValueError, IndexError):
                pass
        return None
