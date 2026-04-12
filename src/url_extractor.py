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


def normalize_url(url: str) -> str:
    """
    URL 정규화: 중복 방지를 위한 표준화.
    
    - 끝에 붙은 특수문자 제거
    - trailing slash 제거 (루트 경로 제외)
    - fragment(#) 제거
    - 쿼리 파라미터 정렬 (선택)
    """
    if not url:
        return url
    
    # 공백 제거
    url = url.strip()
    
    # 끝에 붙은 특수문자 제거 (백틱, 따옴표, 괄호 등)
    while url and url[-1] in '`\'\"~*_.,;:!?)]}>|\\':
        url = url[:-1]
    
    # 앞에 붙은 특수문자 제거
    while url and url[0] in '`\'\"~*_.,;:!?([{<|\\':
        url = url[1:]
    
    # fragment 제거
    if '#' in url:
        url = url.split('#')[0]
    
    # trailing slash 제거 (단, 루트 경로는 유지)
    if url.endswith('/'):
        parts = url.split('://')
        if len(parts) == 2:
            path_part = parts[1]
            if path_part.count('/') > 1:
                url = url.rstrip('/')
    
    return url


def deduplicate_urls(urls: dict) -> dict:
    """
    URL 중복 제거 및 정렬.
    
    Args:
        urls: {url: [descriptions]} 딕셔너리
        
    Returns:
        정규화 및 중복 제거된 {url: [descriptions]} 딕셔너리
    """
    normalized = {}
    
    for url, descriptions in urls.items():
        # URL 정규화
        norm_url = normalize_url(url)
        if not norm_url or len(norm_url) < 10:  # 너무 짧은 URL 제외
            continue
            
        if norm_url not in normalized:
            normalized[norm_url] = []
        
        # 설명 병합 (중복 제거)
        for desc in descriptions:
            if desc and desc not in normalized[norm_url]:
                normalized[norm_url].append(desc)
    
    return normalized


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
    
    # URL 끝에 붙은 구두점/특수문자 제거 (정규표현식이 과도하게 매칭하는 경우)
    while url and url[-1] in '.,;:!?)]\'"`~*_':
        url = url[:-1]
    
    # URL 정규화: trailing slash 제거, 소문자 도메인
    url = normalize_url(url)
    
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


def extract_urls_from_text(text: str, section_only: bool = False) -> Dict[str, List[str]]:
    """
    텍스트에서 URL과 설명을 추출합니다.

    새 포맷(멀티라인)과 기존 포맷(한 줄) 모두 지원:

    새 포맷:
        - https://example.com
          제목 (@공유자)
          **내용** — 설명
          **시사점** — 설명
          **활용** — 설명

    기존 포맷:
        - [닉네임] 설명: https://example.com

    Args:
        text: 분석할 전체 텍스트 (Markdown 형식)
        section_only: True면 "링크/URL" 섹션에서만 추출, False면 전체 텍스트에서 추출

    Returns:
        {URL: [설명 목록]} 딕셔너리
        같은 URL이 여러 번 등장하면 설명들이 리스트에 추가됨
    """
    url_descriptions = defaultdict(list)
    in_url_section = not section_only
    current_url = None  # 멀티라인 파싱용

    for line in text.split('\n'):
        stripped = line.strip()

        if section_only:
            if '### 링크' in stripped or '### URL' in stripped or '2. 공유된 중요 링크' in stripped or '🔗' in stripped:
                in_url_section = True
                continue
            if in_url_section and (stripped.startswith('### ') or stripped.startswith('## ') or (len(stripped) > 2 and stripped[:2].isdigit() and stripped[2] == '.')):
                if not stripped.startswith('-') and not stripped.startswith('http'):
                    in_url_section = False
                    current_url = None
                    continue

        if not in_url_section:
            continue

        # URL이 있는 줄 감지
        url, description = extract_url_with_description(stripped)
        if url:
            current_url = url
            if description and description not in url_descriptions[url]:
                url_descriptions[url].append(description)
            elif url not in url_descriptions:
                url_descriptions[url] = []
            continue

        # URL이 없는 줄 — 현재 URL의 후속 설명줄 (멀티라인 포맷)
        if current_url and stripped:
            # 새 리스트 항목(- )이면 URL이 아닌 일반 항목 → 무시하고 current_url 리셋
            if stripped.startswith('- '):
                current_url = None
                continue
            # **내용**, **시사점**, **활용** 또는 제목줄
            desc_line = stripped
            # 마크다운 bold 제거: **내용** — xxx → 내용 — xxx
            desc_line = re.sub(r'\*\*(.+?)\*\*', r'\1', desc_line)
            if desc_line and desc_line not in url_descriptions[current_url]:
                url_descriptions[current_url].append(desc_line)
        elif not stripped:
            # 빈 줄이면 현재 URL 블록 종료
            current_url = None

    return dict(url_descriptions)


def extract_urls_from_html(html_text: str) -> Dict[str, List[str]]:
    """
    상세 분석 HTML에서 URL과 설명을 추출합니다 (v2.9.0).

    상세 분석 HTML의 구조:
    - <div class="url-card"> 블록 내 <a href="..."> 태그에서 URL 추출
    - <h3> 태그에서 제목 추출
    - <li> 태그에서 내용/시사점/활용 추출
    - 토픽 근거의 <a href="...">🔗</a> 태그에서도 URL 추출

    Args:
        html_text: 상세 분석 HTML 텍스트

    Returns:
        {URL: [설명 목록]} 딕셔너리
    """
    url_descriptions: Dict[str, List[str]] = defaultdict(list)

    # 1) url-card 블록에서 URL + 설명 추출
    card_pattern = re.compile(
        r'<div\s+class="url-card">(.*?)</div>',
        re.DOTALL
    )
    for card_match in card_pattern.finditer(html_text):
        card_html = card_match.group(1)

        # URL 추출 (첫 번째 <a href="...">)
        href_match = re.search(r'<a\s+href="(https?://[^"]+)"', card_html)
        if not href_match:
            continue
        url = normalize_url(href_match.group(1))
        if not url or len(url) < 10:
            continue

        # 제목 추출 (<h3>...</h3>)
        h3_match = re.search(r'<h3>(.*?)</h3>', card_html, re.DOTALL)
        if h3_match:
            title = re.sub(r'<[^>]+>', '', h3_match.group(1)).strip()
            if title and title not in url_descriptions[url]:
                url_descriptions[url].append(title)

        # 내용/시사점/활용 추출 (<li>...</li>)
        for li_match in re.finditer(r'<li>(.*?)</li>', card_html, re.DOTALL):
            li_text = re.sub(r'<[^>]+>', '', li_match.group(1)).strip()
            if li_text and li_text not in url_descriptions[url]:
                url_descriptions[url].append(li_text)

    # 2) 토픽 근거의 인라인 URL 추출 (<a href="...">🔗</a>)
    inline_pattern = re.compile(r'<a\s+href="(https?://[^"]+)"[^>]*>🔗</a>')
    for inline_match in inline_pattern.finditer(html_text):
        url = normalize_url(inline_match.group(1))
        if url and len(url) >= 10 and url not in url_descriptions:
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
