# 05. Coding Convention

## 1. 일반 규칙

### 1.1 언어 및 인코딩
- Python 3.10+
- 파일 인코딩: UTF-8
- 줄 끝: LF (Unix 스타일)

### 1.2 포맷팅
- 들여쓰기: 4 스페이스
- 최대 줄 길이: 100자
- 빈 줄: 함수/클래스 사이에 2줄, 메서드 사이에 1줄

---

## 2. 네이밍 컨벤션

| 대상 | 스타일 | 예시 |
|------|--------|------|
| 모듈 | snake_case | `full_date_summary.py` |
| 클래스 | PascalCase | `ChatProcessor` |
| 함수/메서드 | snake_case | `process_summary()` |
| 변수 | snake_case | `messages_by_date` |
| 상수 | UPPER_SNAKE_CASE | `DEFAULT_TIMEOUT` |
| Private | underscore prefix | `_parse_response()` |

---

## 3. 타입 힌트

모든 함수와 메서드에 타입 힌트를 사용합니다.

```python
# Good
def summarize(self, text: str) -> Dict[str, Any]:
    ...

def parse(self, filepath: Path) -> ParseResult:
    ...

# Bad
def summarize(self, text):
    ...
```

---

## 4. 주석 및 문서화

### 4.1 모듈 Docstring
모든 모듈 파일 상단에 모듈 설명을 포함합니다.

```python
"""
full_config.py - 애플리케이션 설정 관리 모듈

이 모듈은 프로젝트 전역에서 사용되는 설정값들을 중앙에서 관리합니다.
- API 키, URL, 모델명 등의 외부 서비스 설정
- 디렉터리 경로 설정
- 로깅 설정
"""
```

### 4.2 클래스/함수 Docstring
```python
def process_summary(self, text: str) -> str:
    """
    대화 텍스트를 요약합니다.
    
    Args:
        text: 요약할 카카오톡 대화 텍스트
        
    Returns:
        Markdown 형식으로 포맷팅된 요약 결과 문자열.
        실패 시 '[ERROR]'로 시작하는 에러 메시지 반환.
    """
```

### 4.3 인라인 주석
복잡한 로직에 한글로 설명을 추가합니다.

```python
# 날짜를 YYYY-MM-DD 형식으로 정규화
return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
```

---

## 5. Import 순서

1. 표준 라이브러리
2. 서드파티 라이브러리
3. 로컬 모듈

```python
# 표준 라이브러리
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 서드파티
import requests

# 로컬 모듈
from full_config import config
from parser import KakaoLogParser
```

---

## 6. 에러 처리

### 6.1 예외 처리 패턴
```python
try:
    response = requests.post(url, json=payload, timeout=timeout)
    if response.status_code != 200:
        return {"success": False, "error": f"API Error {response.status_code}"}
    return self._parse_response(response.json())
except requests.exceptions.Timeout:
    self.logger.error("Request timed out.")
    return {"success": False, "error": "Request timed out."}
except Exception as e:
    self.logger.exception("Unexpected error occurred.")
    return {"success": False, "error": str(e)}
```

### 6.2 로깅
```python
# INFO: 정상 흐름
self.logger.info(f"Processing {target_date} ({msg_count} messages)...")

# WARNING: 주의 필요
self.logger.warning("No parsed messages found.")

# ERROR: 오류 발생
self.logger.error(f"File not found: {filepath}")

# EXCEPTION: 예외 발생 (스택 트레이스 포함)
self.logger.exception("API call failed.")
```

---

## 7. 파일 구조

```python
"""
module.py - 모듈 설명
"""

# Imports (순서 준수)
from typing import ...
import ...

from full_config import config

# 상수
CONSTANT_VALUE = ...

# 클래스
class MyClass:
    """클래스 설명"""
    
    def __init__(self):
        ...
    
    def public_method(self):
        ...
    
    def _private_method(self):
        ...

# 모듈 레벨 함수
def helper_function():
    ...

# 메인 진입점
def main():
    ...

if __name__ == "__main__":
    main()
```

---

## 8. 의존성 관리

### requirements.txt
```
# Core - 실제 사용되는 라이브러리만 포함
requests>=2.31.0

# Development - 개발 도구
pytest>=7.4.0
ruff>=0.1.0
mypy>=1.5.0
```
