# 🤖 CLAUDE.md - AI 에이전트 프로젝트 컨텍스트

> Claude Opus 4.5가 프로젝트를 이해하고 작업을 계속할 수 있도록 작성된 컨텍스트 파일입니다.
> **새 대화 시작 시 `@CLAUDE.md`를 참조하세요.**

---

## 📋 프로젝트 개요

| 항목 | 값 |
|------|-----|
| **프로젝트명** | KakaoTalk Chat Summary |
| **목적** | 카카오톡 대화를 LLM으로 요약하고 관리하는 데스크톱 앱 |
| **언어** | Python 3.11+ |
| **GUI** | PySide6 (Qt for Python) |
| **DB** | SQLite + SQLAlchemy ORM |
| **버전** | v2.2.0 |
| **최종 업데이트** | 2026-02-01 |

---

## 🏗️ 프로젝트 구조

```
kakao-chat-summary/
├── src/
│   ├── app.py                 # 앱 진입점 (QApplication)
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py     # 메인 GUI (2600+ lines)
│   │   └── styles.py          # 카카오톡 스타일 테마
│   ├── db/
│   │   ├── __init__.py        # get_db() export
│   │   ├── database.py        # Database 클래스
│   │   └── models.py          # SQLAlchemy 모델 5개
│   ├── file_storage.py        # FileStorage 클래스
│   ├── full_config.py         # Config 클래스 (LLM 설정)
│   ├── parser.py              # KakaoLogParser 클래스
│   ├── llm_client.py          # LLMClient 클래스
│   ├── chat_processor.py      # ChatProcessor 클래스
│   ├── url_extractor.py       # URL 추출 함수들
│   ├── import_to_db.py        # DB import 유틸
│   └── scheduler/
│       ├── __init__.py
│       └── tasks.py           # 스케줄러 태스크 (미구현)
│   └── manual/                # CLI 스크립트 (레거시)
│       ├── README.md
│       ├── full_date_summary.py
│       ├── full_yesterday_summary.py
│       ├── full_2days_summary.py
│       ├── full_today_summary.py
│       ├── simple_date_summary.py
│       ├── simple_yesterday_summary.py
│       ├── simple_2days_summary.py
│       └── simple_today_summary.py
├── data/
│   ├── db/                    # SQLite 데이터베이스
│   │   └── chat_history.db
│   ├── original/              # 원본 대화 (일별)
│   │   └── <채팅방>/
│   │       └── <채팅방>_YYYYMMDD_full.md
│   ├── summary/               # LLM 요약 (일별)
│   │   └── <채팅방>/
│   │       └── <채팅방>_YYYYMMDD_summary.md
│   └── url/                   # URL 목록 (채팅방별 3개 파일)
│       └── <채팅방>/
│           ├── <채팅방>_urls_recent.md
│           ├── <채팅방>_urls_weekly.md
│           └── <채팅방>_urls_all.md
├── upload/                    # 파일 업로드 기본 디렉터리
├── logs/                      # 로그 (summarizer_YYYYMMDD.log)
├── docs/                      # 문서 (01-prd ~ 06-tasks)
├── .env.local                 # API 키 (gitignore)
├── env.local.example          # API 키 예제
├── requirements.txt
├── .gitignore
├── README.md
└── CLAUDE.md                  # 이 파일
```

---

## 🗃️ 데이터베이스 스키마 (5개 테이블)

### ChatRoom
```python
class ChatRoom(Base):
    __tablename__ = 'chat_rooms'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    file_path = Column(String(512))
    participant_count = Column(Integer, default=0)
    last_sync_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    # Relationships: messages, summaries, sync_logs, urls
```

### Message
```python
class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('chat_rooms.id'))
    sender = Column(String(255), nullable=False)
    content = Column(Text)
    message_date = Column(Date, nullable=False)
    message_time = Column(Time)
    raw_line = Column(Text)
    created_at = Column(DateTime)
    # UniqueConstraint: (room_id, sender, message_date, message_time, content)
```

### Summary
```python
class Summary(Base):
    __tablename__ = 'summaries'
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('chat_rooms.id'))
    summary_date = Column(Date, nullable=False)
    summary_type = Column(String(50))  # 'daily', '2days', 'weekly'
    content = Column(Text)
    llm_provider = Column(String(100))
    token_count = Column(Integer)
    created_at = Column(DateTime)
```

### SyncLog
```python
class SyncLog(Base):
    __tablename__ = 'sync_logs'
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('chat_rooms.id'))
    status = Column(String(50))  # 'success', 'failed', 'partial'
    message_count = Column(Integer)
    new_message_count = Column(Integer)
    error_message = Column(Text)
    synced_at = Column(DateTime)
```

### URL
```python
class URL(Base):
    __tablename__ = 'urls'
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('chat_rooms.id'))
    url = Column(Text, nullable=False)
    descriptions = Column(Text)  # " / " 구분자
    source_date = Column(Date)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    # UniqueConstraint: (room_id, url)
```

---

## 🖥️ GUI 구조 (main_window.py)

### 메인 윈도우 레이아웃
```
┌─────────────────────────────────────────────────────────┐
│ 메뉴바                                                   │
│ ├─ 파일: 채팅방 추가, 종료                               │
│ ├─ 도구: 지금 동기화, LLM 요약 생성, DB 복구, 설정       │
│ └─ 도움말: 정보                                          │
├──────────────┬──────────────────────────────────────────┤
│              │  QTabWidget (3개 탭)                      │
│  채팅방 목록  │  ├─ 📊 대시보드                           │
│  (QListWidget)│  ├─ 📅 날짜별 요약                       │
│              │  └─ 🔗 URL 정보                           │
│              │                                          │
│ [➕ 채팅방]   │                                          │
│ [📤 업로드]  │                                          │
├──────────────┴──────────────────────────────────────────┤
│ 상태바: [아이콘] 메시지                        (HH:MM:SS) │
└─────────────────────────────────────────────────────────┘
```

### 다이얼로그 클래스 (6개)
| 클래스 | 역할 |
|--------|------|
| `CreateRoomDialog` | 채팅방 생성 |
| `UploadFileDialog` | 파일 업로드 (기본 디렉터리: upload/) |
| `SummaryOptionsDialog` | LLM 요약 옵션 선택 |
| `SummaryProgressDialog` | 요약 진행률 표시 (취소 가능) |
| `SettingsDialog` | 설정 |
| (QMessageBox) | 각종 알림 |

### Worker 스레드 (4개)
| 클래스 | 역할 |
|--------|------|
| `FileUploadWorker` | 파일 업로드 및 파싱 |
| `SyncWorker` | 백그라운드 동기화 |
| `SummaryGeneratorWorker` | LLM 요약 생성 |
| `RecoveryWorker` | 파일에서 DB 복구 |

### 상태바 아이콘
| 아이콘 | 의미 |
|--------|------|
| ✅ | 성공/준비 완료 |
| ⏳ | 작업 진행 중 |
| ❌ | 실패 |
| ⚠️ | 경고 |
| ℹ️ | 정보 |

---

## 🔑 핵심 기능

### 1. 채팅방 관리
- 채팅방 생성/삭제
- 채팅방 목록 (메시지 개수 내림차순 정렬)
- 파일 업로드 (기본 디렉터리: `upload/`)

### 2. LLM 요약 생성
- **지원 LLM**: Z.AI GLM, OpenAI GPT-4o-mini, MiniMax, Perplexity
- **요약 옵션**: 전체 날짜, 요약 안된 날짜만, 대기 중인 날짜만
- **응답 검증**: finish_reason, 최소 길이, 필수 섹션, 잘림 패턴
- **진행 상황**: 실시간 진행률, 취소 가능

### 3. 대시보드 탭
- 채팅방 통계 (메시지 수, 참여자 수, 요약 수)
- 최근 요약 목록

### 4. 날짜별 요약 탭
- 달력 위젯으로 날짜 선택 (QCalendarWidget)
- 요약 마크다운 렌더링

### 5. URL 정보 탭
- **3개 섹션**: 최근 3일 (50개 제한), 최근 1주 (무제한), 전체 (무제한)
- **URL 정규화**: 특수문자, fragment, trailing slash 제거
- **중복 제거**: `deduplicate_urls()` 함수
- **동기화/복구 버튼**: DB ↔ 파일

### 6. 파일 기반 저장
- `data/original/`: 원본 대화 (일별 MD)
- `data/summary/`: LLM 요약 (일별 MD)
- `data/url/`: URL 목록 (채팅방별 3개 파일)

### 7. DB 복구
- `data/original/` + `data/summary/` → DB 재구축

---

## 📁 주요 모듈 상세

### src/db/database.py - Database 클래스
```python
# 채팅방
create_room(name) -> ChatRoom
get_all_rooms() -> List[ChatRoom]  # 메시지 수 내림차순
get_room_by_id(room_id) -> ChatRoom
delete_room(room_id) -> bool

# 메시지
add_messages(room_id, messages) -> int  # 배치, 중복 체크
get_messages_by_date(room_id, date) -> List[Message]
get_message_count_by_date(room_id, date) -> int
get_available_dates(room_id) -> List[str]

# 요약
add_summary(room_id, date, content, llm_provider) -> Summary
get_summary_by_date(room_id, date) -> Summary
get_summarized_dates(room_id) -> List[str]
delete_summary(room_id, date) -> bool

# URL
add_urls_batch(room_id, urls_dict) -> int
get_urls_by_room(room_id) -> List[URL]
clear_urls_by_room(room_id) -> int
```

### src/file_storage.py - FileStorage 클래스
```python
# 디렉터리
base_dir = Path("data")
original_dir = base_dir / "original"
summary_dir = base_dir / "summary"
url_dir = base_dir / "url"

# 원본 대화
save_daily_original(room_name, date_str, messages) -> Path
load_daily_original(room_name, date_str) -> List[str]
get_available_dates(room_name) -> List[str]

# 요약
save_daily_summary(room_name, date_str, content, llm) -> Path
load_daily_summary(room_name, date_str) -> str
get_summarized_dates(room_name) -> List[str]
invalidate_summary_if_updated(room_name, date, old_count, new_count)

# URL (3개 파일)
save_url_lists(room_name, urls_recent, urls_weekly, urls_all)
load_url_list(room_name, list_type) -> Dict[str, List[str]]
```

### src/url_extractor.py - URL 추출 함수
```python
extract_urls_from_text(text, section_only=False) -> Dict[str, List[str]]
extract_url_with_description(line) -> Tuple[str, str]
normalize_url(url) -> str  # 특수문자, fragment, trailing slash 제거
deduplicate_urls(urls_dict) -> Dict[str, List[str]]
save_urls_to_file(urls_dict, filepath) -> bool
```

### src/llm_client.py - LLMClient 클래스
```python
__init__(provider='glm')
summarize(text) -> Dict  # {"success": bool, "content": str, "error": str}
_validate_response(content) -> bool  # 응답 완결성 검증
```

### src/full_config.py - Config 클래스
```python
# LLM 제공자
LLM_PROVIDERS = {
    "glm": {..., env_key="ZAI_API_KEY"},
    "chatgpt": {..., env_key="OPENAI_API_KEY"},
    "minimax": {..., env_key="MINIMAX_API_KEY"},
    "perplexity": {..., env_key="PERPLEXITY_API_KEY"}
}

get_api_key(provider) -> str
set_api_key(api_key, provider)
```

---

## 🔧 환경 설정

### .env.local 형식
```bash
ZAI_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
MINIMAX_API_KEY=your_key_here
PERPLEXITY_API_KEY=your_key_here
```

---

## 🚀 실행 방법

```bash
# 가상환경 활성화
.venv\Scripts\activate  # Windows

# 앱 실행
python src/app.py
```

---

## ⚠️ 주의사항

1. **API 키**: `.env.local`은 절대 커밋하지 않음
2. **데이터**: `data/` 폴더는 `.gitignore`에 포함
3. **한글 인코딩**: 파일 읽기/쓰기 시 `encoding='utf-8'` 필수
4. **Qt 스레드**: UI 업데이트는 메인 스레드에서만 (Signal/Slot)
5. **PowerShell**: `&&` 대신 명령어 분리 실행

---

## 🔮 향후 개선 사항 (Pending)

1. [ ] APScheduler로 주기적 동기화 구현
2. [ ] 새 메시지 개수 표시
3. [ ] 설정 다이얼로그에서 API 키 입력
4. [ ] 요약 품질 평가 기능
5. [ ] 테스트 코드 작성 (pytest)

---

## 📚 관련 문서

| 파일 | 내용 |
|------|------|
| `docs/01-prd.md` | 제품 요구사항 |
| `docs/02-trd.md` | 기술 요구사항 |
| `docs/03-user-flow.md` | 사용자 흐름 |
| `docs/04-data-design.md` | 데이터 설계 |
| `docs/05-coding-convention.md` | 코딩 컨벤션 |
| `docs/06-tasks.md` | 작업 목록 & 버전 히스토리 |

---

*마지막 업데이트: 2026-02-01 | 버전: v2.2.0*
