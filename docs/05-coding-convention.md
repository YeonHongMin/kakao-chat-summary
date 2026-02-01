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
| 모듈 | snake_case | `file_storage.py` |
| 클래스 | PascalCase | `MainWindow`, `FileUploadWorker` |
| 함수/메서드 | snake_case | `process_summary()` |
| 변수 | snake_case | `messages_by_date` |
| 상수 | UPPER_SNAKE_CASE | `DEFAULT_TIMEOUT` |
| Private | underscore prefix | `_parse_response()` |
| Qt 슬롯 | underscore prefix | `_on_button_clicked()` |

---

## 3. 타입 힌트

모든 함수와 메서드에 타입 힌트를 사용합니다.

```python
# Good
def summarize(self, text: str) -> Dict[str, Any]:
    ...

def parse(self, filepath: Path) -> ParseResult:
    ...

def _on_room_selected(self, room_id: int, file_path: str) -> None:
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
file_storage.py - 파일 기반 데이터 저장 모듈

이 모듈은 채팅 데이터와 요약을 Markdown 파일로 저장/로드합니다.
- original/: 날짜별 원본 대화
- summary/: 날짜별 LLM 요약
"""
```

### 4.2 클래스/함수 Docstring
```python
def save_daily_original(self, room_name: str, date_str: str, messages: List[str]) -> bool:
    """
    날짜별 원본 대화를 Markdown 파일로 저장합니다.
    
    기존 파일이 있으면 메시지를 병합합니다.
    
    Args:
        room_name: 채팅방 이름
        date_str: 날짜 문자열 (YYYY-MM-DD)
        messages: 메시지 목록
        
    Returns:
        저장 성공 여부
    """
```

### 4.3 인라인 주석
복잡한 로직에 한글로 설명을 추가합니다.

```python
# 날짜를 YYYY-MM-DD 형식으로 정규화
return f"{y}-{m.zfill(2)}-{d.zfill(2)}"

# WAL 모드 활성화 (동시 접근 성능 향상)
connection.execute("PRAGMA journal_mode=WAL")
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
from PySide6.QtWidgets import QMainWindow, QPushButton
from PySide6.QtCore import Qt, Signal, Slot
from sqlalchemy import create_engine

# 로컬 모듈
from full_config import config
from parser import KakaoLogParser
from db import get_db, ChatRoom, Message
```

---

## 6. PySide6/Qt 규칙

### 6.1 시그널/슬롯 연결
```python
# 시그널-슬롯 연결은 명시적으로
self.button.clicked.connect(self._on_button_clicked)

# 슬롯 메서드는 @Slot 데코레이터 사용
@Slot()
def _on_button_clicked(self):
    ...

@Slot(int, str)
def _on_progress_update(self, progress: int, message: str):
    ...
```

### 6.2 Worker 스레드 패턴
```python
class MyWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(bool, str)
    
    def run(self):
        try:
            for i in range(100):
                self.progress.emit(i, f"처리 중... {i}%")
            self.finished.emit(True, "완료")
        except Exception as e:
            self.finished.emit(False, str(e))
```

---

## 7. 에러 처리

### 7.1 예외 처리 패턴
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

### 7.2 로깅
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

## 8. 파일 구조

```python
"""
module.py - 모듈 설명
"""

# Imports (순서 준수)
from typing import ...
import ...

from PySide6.QtWidgets import ...
from PySide6.QtCore import ...

from full_config import config
from db import get_db

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

## 9. 의존성 관리

### requirements.txt
```
# Core - HTTP 통신
requests>=2.31.0

# Environment
python-dotenv>=1.0.0

# UI - Qt for Python
PySide6>=6.6.0

# Database - ORM
SQLAlchemy>=2.0.0

# Scheduler (미래용)
APScheduler>=3.10.0

# Development - 테스트
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0
```

---

## 10. Git 컨벤션

### 10.1 커밋 메시지
```
<type>: <subject>

<body (optional)>
```

**Type**:
- `feat`: 새 기능
- `fix`: 버그 수정
- `docs`: 문서 수정
- `style`: 포맷팅
- `refactor`: 리팩터링
- `test`: 테스트
- `chore`: 기타

### 10.2 .gitignore 규칙
```gitignore
# Data - 구조만 유지, 내용 제외
data/*
!data/.gitkeep
!data/original/
!data/summary/
data/original/*
data/summary/*
!data/original/.gitkeep
!data/summary/.gitkeep

# Environment
.env
.env.local
!env.local.example
```
