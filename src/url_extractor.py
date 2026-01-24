"""
url_extractor.py - URL 추출 모듈

이 모듈은 요약된 Markdown 텍스트에서 URL을 추출하는 기능을 제공합니다.

주요 기능:
- "### 🔗 링크/URL" 섹션에서 URL 추출
- URL과 함께 설명 텍스트 추출
- 중복 URL 제거 (설명은 병합)
- 결과를 별도 텍스트 파일로 저장

사용법:
    python url_extractor.py <file_or_directory>
    python url_extractor.py  # data 디렉터리 기본 스캔
"""

import re
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# URL 추출을 위한 정규표현식 패턴
# http:// 또는 https://로 시작하는 URL을 매칭
# 공백, 괄호, 한글 등에서 URL 종료
URL_PATTERN = re.compile(
    r'(https?://[^\s<>"\')\]가-힣]+)',
    re.IGNORECASE
)


def extract_url_with_description(line: str) -> Tuple[str, str]:
    """
    한 줄의 텍스트에서 URL과 설명을 추출합니다.
    
    입력 예시:
    - "[닉네임] https://example.com (설명)"
    - "https://example.com - 유용한 도구"
    
    Args:
        line: 처리할 텍스트 라인
        
    Returns:
        (URL, 설명) 튜플. URL이 없으면 ("", "") 반환
    """
    # [닉네임] 이나 [시간] 같은 메타데이터 제거
    line_without_sender = re.sub(r'\[.*?\]', '', line).strip()
    
    # 리스트 마커 "- " 제거
    if line_without_sender.startswith('- '):
        line_without_sender = line_without_sender[2:].strip()
    
    # URL 검색
    url_match = URL_PATTERN.search(line_without_sender)
    if not url_match:
        return "", ""
    
    url = url_match.group(1)
    
    # URL 끝에 붙은 구두점 제거 (정규표현식이 과도하게 매칭하는 경우)
    while url and url[-1] in '.,;:!?)]\'"':
        url = url[:-1]
    
    # URL 이후 텍스트에서 설명 추출
    after_url = line_without_sender[url_match.end():].strip()
    
    # 괄호 안의 내용을 설명으로 사용 (예: https://... (설명))
    paren_match = re.search(r'\((.+)\)', after_url)
    if paren_match:
        description = paren_match.group(1).strip()
    else:
        # 괄호가 없으면 URL 앞뒤 텍스트를 설명으로 사용
        before_url = line_without_sender[:url_match.start()].strip()
        description = (before_url + " " + after_url).strip()
        
        # 콜론으로 시작하면 제거
        if description.startswith(':'):
            description = description[1:].strip()
        
        # 빈 괄호 제거
        description = re.sub(r'\(\s*\)', '', description).strip()
    
    return url, description


def extract_urls_from_text(text: str) -> Dict[str, List[str]]:
    """
    텍스트의 "링크/URL" 섹션에서 URL과 설명을 추출합니다.
    
    "### 🔗 링크/URL" 또는 유사한 헤더로 시작하는 섹션을 찾고,
    해당 섹션 내의 모든 URL을 추출합니다.
    
    Args:
        text: 분석할 전체 텍스트 (Markdown 형식)
        
    Returns:
        {URL: [설명 목록]} 딕셔너리
        같은 URL이 여러 번 등장하면 설명들이 리스트에 추가됨
    """
    url_descriptions = defaultdict(list)
    in_url_section = False  # 현재 URL 섹션 내부인지 여부
    
    for line in text.split('\n'):
        line = line.strip()
        
        # URL 섹션 시작 감지 (다양한 헤더 형식 지원)
        if '### 링크' in line or '### URL' in line or '2. 공유된 중요 링크' in line:
            in_url_section = True
            continue
        
        # 다른 섹션 시작 감지 (URL 섹션 종료)
        # "###", "##", "3." 등으로 시작하는 새로운 헤더
        if in_url_section and (line.startswith('### ') or line.startswith('## ') or (line[:2].isdigit() and line[2] == '.')):
             # 리스트 아이템("-")이 아닌 경우에만 섹션 종료로 판단
             if not line.startswith('-'): 
                 if line and not line.startswith('http'):
                     in_url_section = False
                     continue
        
        # URL 섹션 내에서 URL 추출
        if in_url_section:
            url, description = extract_url_with_description(line)
            if url:
                # 중복 설명 방지: 같은 설명은 추가하지 않음
                if description and description not in url_descriptions[url]:
                    url_descriptions[url].append(description)
                elif not description and url not in url_descriptions:
                    # 설명 없는 URL도 등록 (빈 리스트)
                    if not url_descriptions[url]:
                        url_descriptions[url] = []
    
    return dict(url_descriptions)


def save_urls_to_file(url_dict: Dict[str, List[str]], output_path: str, chatroom_name: str = "Unknown") -> None:
    """
    추출된 URL 목록을 파일로 저장합니다.
    
    Args:
        url_dict: {URL: [설명 목록]} 딕셔너리
        output_path: 출력 파일 경로
        chatroom_name: 채팅방 이름 (헤더에 표시)
    """
    # URL을 알파벳순으로 정렬
    sorted_urls = sorted(url_dict.items(), key=lambda x: x[0].lower())
    
    with open(output_path, "w", encoding="utf-8") as f:
        # 헤더 정보 작성
        f.write(f"🔗 [{chatroom_name}] URL 목록\n")
        f.write(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"총 {len(url_dict)}개 URL\n")
        f.write("=" * 60 + "\n\n")
        
        # URL과 설명 출력
        for url, descriptions in sorted_urls:
            if descriptions:
                # 여러 설명이 있으면 " / "로 연결
                merged_desc = " / ".join(descriptions)
                f.write(f"{url} ({merged_desc})\n")
            else:
                f.write(f"{url}\n")


def main():
    """
    독립 실행 시 메인 함수.
    
    명령줄 인자로 파일 또는 디렉터리 경로를 받아 처리합니다.
    인자가 없으면 기본 data 디렉터리를 스캔합니다.
    """
    import sys
    
    # 명령줄 인자 확인
    if len(sys.argv) < 2:
        # 기본 경로: src의 상위 디렉터리 -> data
        base_dir = Path(__file__).resolve().parent.parent
        data_dir = base_dir / 'data'
        print("Usage: python url_extractor.py <file_or_directory>")
        target_path = data_dir
    else:
        target_path = Path(sys.argv[1]).expanduser()
    
    # 경로 존재 확인
    if not target_path.exists():
        print(f"❌ Path not found: {target_path}")
        sys.exit(1)
        
    # 처리 대상 파일 목록 구성
    targets = []
    if target_path.is_file():
        targets.append(target_path)
    else:
        # 디렉터리인 경우: *_summary.md 파일 검색
        targets = list(target_path.glob("*_summary.md"))
        
    if not targets:
        print("❌ No matching files (*_summary.md) found.")
        return
        
    print(f"🔍 Found {len(targets)} files.\n")
    
    # 각 파일 처리
    for file_path in targets:
        print(f"Processing: {file_path.name}")
        try:
            text = file_path.read_text(encoding='utf-8')
            url_dict = extract_urls_from_text(text)
            
            if url_dict:
                # 출력 파일명 생성: *_summary.md -> *_url.txt
                output_filename = file_path.stem.replace("_summary", "") + "_url.txt"
                if output_filename == file_path.name: 
                     output_filename = file_path.stem + "_url.txt"
                
                output_path = file_path.parent / output_filename
                save_urls_to_file(url_dict, str(output_path), file_path.stem)
                print(f"  ✅ Saved: {output_filename}")
            else:
                print("  ℹ️  No URLs found.")
        except Exception as e:
            print(f"  ❌ Error: {e}")


if __name__ == "__main__":
    main()
