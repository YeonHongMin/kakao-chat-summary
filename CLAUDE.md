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
| **버전** | v2.5.1 |
| **최종 업데이트** | 2026-02-10 |

---

## 🏗️ 프로젝트 구조

```
kakao-chat-summary/
├── src/
│   ├── app.py                 # 앱 진입점 (QApplication)
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py     # 메인 GUI (2900+ lines)
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
│       └── tasks.py           # SyncScheduler (프레임워크 구현, 메인 앱 미연동)
│   └── manual/                # CLI 스크립트 (수동 요약용, 레거시)
│       ├── README.md
│       ├── full_date_summary.py      # 상세 요약 - src/ 모듈 재사용
│       ├── full_yesterday_summary.py
│       ├── full_2days_summary.py
│       ├── full_today_summary.py
│       ├── simple_date_summary.py    # 간결 요약 (음슴체) - 자체 내장 구현
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
├── output/                    # CLI 스크립트 (src/manual/) 출력 디렉터리
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
│ ├─ 파일: 채팅방 추가, 채팅방 삭제, 종료                   │
│ ├─ 도구: 지금 동기화, LLM 요약 생성, DB 복구, 채팅방 복구, 설정 │
│ └─ 도움말: 정보                                          │
├──────────────┬──────────────────────────────────────────┤
│              │  QTabWidget (4개 탭)                      │
│  채팅방 목록  │  ├─ 📊 대시보드                           │
│  (QListWidget)│  ├─ 📅 날짜별 요약                       │
│              │  ├─ 🔗 URL 정보 (동기화/복구 버튼 포함)    │
│              │  └─ 🔧 기타 (통계 갱신 등)                │
│              │                                          │
│ [➕ 채팅방]   │                                          │
│ [📤 업로드]  │                                          │
├──────────────┴──────────────────────────────────────────┤
│ 상태바: [아이콘] 메시지  [🤖 요약 중 3/10 ▮▮▯ ❌] (HH:MM:SS) │
└─────────────────────────────────────────────────────────┘
```

### 다이얼로그 클래스 (6개)
| 클래스 | 역할 |
|--------|------|
| `CreateRoomDialog` | 채팅방 생성 |
| `UploadFileDialog` | 파일 업로드 (기본 디렉터리: upload/) |
| `SummaryOptionsDialog` | LLM 요약 옵션 선택 |
| `SummaryProgressDialog` | 요약 진행률 다이얼로그 (미사용, 보존) |
| `SettingsDialog` | 설정 |
| (QMessageBox) | 각종 알림 |

### 위젯 클래스
| 클래스 | 역할 |
|--------|------|
| `ChatRoomWidget` | 채팅방 목록 아이템 |
| `DashboardCard` | 대시보드 통계 카드 (`update_card()` 메서드) |
| `SummaryProgressWidget` | 상태바 내장 비모달 프로그레스 (아이콘+메시지+프로그레스바+취소) |

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
- 채팅방 생성 (Enter 키로 즉시 생성 가능)
- 채팅방 삭제 (파일 메뉴 → 현재 선택된 채팅방 삭제, 확인 다이얼로그)
- 채팅방 목록 (메시지 개수 내림차순 정렬)
- 파일 업로드 (기본 디렉터리: `upload/`)

### 2. LLM 요약 생성
- **지원 LLM**: Z.AI GLM, OpenAI GPT-4o-mini, MiniMax, Perplexity
- **요약 옵션**: 요약 필요한 날짜만 (기본), 오늘, 어제~오늘, 엇그제~오늘, 전체 일자 + 이미 요약된 날짜 건너뛰기 체크박스
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
- **동기화/복구 버튼**: 요약에서 URL 추출, 파일에서 DB 복구

### 6. 파일 기반 저장
- `data/original/`: 원본 대화 (일별 MD)
- `data/summary/`: LLM 요약 (일별 MD)
- `data/url/`: URL 목록 (채팅방별 3개 파일)

### 7. 기타 기능 탭
- **📊 통계 정보 갱신**: 대시보드 통계와 채팅방 목록을 최신 상태로 갱신
- (향후 기능 추가 영역)

### 8. 도구 메뉴 복구 기능
- **🗄️ DB 전체 복구**: `data/original/` + `data/summary/` + `data/url/` → DB 재구축 (파괴적)
- **💬 채팅방 복구**: 파일 디렉터리에 있지만 DB에 없는 채팅방만 추가 (비파괴적)

---

## 📁 주요 모듈 상세

### src/db/database.py - Database 클래스
```python
# 채팅방
create_room(name, file_path=None) -> ChatRoom
get_all_rooms() -> List[ChatRoom]  # 메시지 수 내림차순
get_room_by_id(room_id) -> Optional[ChatRoom]
get_room_by_name(name) -> Optional[ChatRoom]
get_room_stats(room_id) -> Dict[str, Any]
update_room_sync_time(room_id)
delete_room(room_id)

# 메시지
add_messages(room_id, messages, batch_size=500) -> int  # 배치, 중복 체크
get_messages_by_room(room_id, start_date=None, end_date=None) -> List[Message]
get_message_count_by_room(room_id) -> int
get_message_count_by_date(room_id, target_date) -> int
get_unique_senders(room_id) -> List[str]

# 요약
add_summary(room_id, summary_date, summary_type, content, llm_provider=None) -> Summary
get_summary_by_id(summary_id) -> Optional[Summary]
get_summaries_by_room(room_id, summary_type=None) -> List[Summary]
delete_summary(room_id, summary_date) -> bool

# 동기화 로그
add_sync_log(room_id, status, message_count, new_message_count, error_message) -> SyncLog
get_sync_logs_by_room(room_id, limit=10) -> List[SyncLog]

# URL
add_url(room_id, url, descriptions=None, source_date=None) -> URL
add_urls_batch(room_id, urls) -> int
get_urls_by_room(room_id) -> Dict[str, List[str]]
get_url_count_by_room(room_id) -> int
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
get_dates_needing_summary(room_name) -> Dict[str, str]  # 요약 파일 존재 여부만 확인
invalidate_summary_if_updated(room_name, date, old_count, new_count)  # 업로드 시 메시지 수 비교로 요약 삭제

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
_validate_response_content(content) -> Dict[str, Any]  # 응답 완결성 검증
_wait_for_rate_limit()  # ChatGPT Rate Limit 대기 (21초)
# timeout: (connect=60s, read=600s), 스트리밍 방식
# CHATGPT_RATE_LIMIT_DELAY = 21
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
# GUI 앱 실행 (가상환경 불필요)
python src/app.py

# CLI 스크립트 (수동 요약) - 결과는 output/ 디렉터리에 저장
python src/manual/full_date_summary.py <파일 또는 디렉터리> [--llm chatgpt]
python src/manual/simple_today_summary.py <파일> [--llm glm]
```

### CLI 스크립트 (src/manual/) 상세

**두 가지 유형**:

| 유형 | 스크립트 | 특징 |
|------|----------|------|
| **Full (상세)** | `full_*.py` | src/ 모듈 재사용 (`full_config`, `parser`, `chat_processor`, `url_extractor`) |
| **Simple (간결)** | `simple_*.py` | 자체 내장 구현 (`SimpleConfig`, `SimpleParser`, `SimpleLLMClient`), 음슴체 |

**날짜 범위별 스크립트**:
| 범위 | Full | Simple |
|------|------|--------|
| 오늘만 | `full_today_summary.py` | `simple_today_summary.py` |
| 어제~오늘 | `full_yesterday_summary.py` | `simple_yesterday_summary.py` |
| 엇그제~오늘 | `full_2days_summary.py` | `simple_2days_summary.py` |
| 전체 날짜 | `full_date_summary.py` | `simple_date_summary.py` |

**GUI와의 차이**:
- DB/FileStorage 사용하지 않음 (직접 파일 I/O)
- 출력: `output/` 디렉터리 (GUI는 `data/summary/`)
- Simple 스크립트 timeout: (60, 300)초 (GUI는 (60, 600)초)

---

## ⚠️ 주의사항

1. **API 키**: `.env.local`은 절대 커밋하지 않음
2. **데이터**: `data/` 폴더는 `.gitignore`에 포함
3. **한글 인코딩**: 파일 읽기/쓰기 시 `encoding='utf-8'` 필수
4. **Qt 스레드**: UI 업데이트는 메인 스레드에서만 (Signal/Slot)
5. **PowerShell**: `&&` 대신 명령어 분리 실행

---

## 🔮 향후 개선 사항 (Pending)

1. [ ] APScheduler 메인 앱 연동 (SyncScheduler 프레임워크는 구현 완료)
2. [ ] 새 메시지 개수 표시
3. [ ] 설정 다이얼로그에서 API 키 입력
4. [ ] 요약 품질 평가 기능
5. [ ] 테스트 코드 작성 (pytest)

---

## 🐛 트러블슈팅 히스토리

### v2.2.2 - 요약 파일 ↔ DB 동기화 버그 (2026-02-01)

**증상**: LLM 요약 생성 후 대시보드에 요약이 표시되지 않음

**원인 3가지**:
1. **SummaryGeneratorWorker가 파일에만 저장** (`main_window.py` ~826행)
   - `storage.save_daily_summary()`만 호출하고 `db.add_summary()`는 호출하지 않았음
   - 대시보드는 DB에서 요약 목록을 읽으므로 불일치 발생
2. **RecoveryWorker date 타입 버그** (`main_window.py` ~916행)
   - `db.add_summary()`에 `date_str` (문자열)을 전달 → `date` 객체 필요
3. **RecoveryWorker 요약 내용 500자 잘림** (`main_window.py` ~920행)
   - `summary_content[:500]`으로 잘라서 저장 → 전체 내용 손실

**수정**:
1. SummaryGeneratorWorker에서 파일 저장 직후 `db.delete_summary()` + `db.add_summary()` 호출 추가
2. RecoveryWorker에서 `datetime.strptime(date_str, '%Y-%m-%d').date()` 변환 적용
3. `summary_content[:500]` → `summary_content` 전체 저장으로 변경
4. `database.py`에 `delete_summary(room_id, summary_date)` 메서드 신규 추가

**설계 원칙**: 요약 필요 여부는 **파일 존재 여부**로 판단 (`get_dates_needing_summary`, `get_summarized_dates`).
DB에 데이터가 있어도 파일이 없으면 재수집 대상이며, DB 저장 시 기존 행을 삭제 후 추가하여 중복 방지.

### v2.2.3 - UI 개선 및 중복 헤더 제거 (2026-02-01)

**변경 1: 채팅방 삭제를 파일 메뉴로 이동**
- ChatRoomWidget의 ✕ 삭제 버튼 제거 (오클릭 위험, 버튼이 보이지 않는 문제)
- 파일 메뉴에 "채팅방 삭제..." 액션 추가
- 현재 선택된 채팅방(`self.current_room_id`)을 기준으로 삭제
- 채팅방 미선택 시 경고 메시지 표시

**변경 2: CreateRoomDialog Enter 키 수정**
- Enter 키가 취소(reject) 대신 만들기(accept) 동작하도록 수정
- `name_input.returnPressed` → `_on_create` 연결
- `create_btn.setDefault(True)` 설정
- 빈 이름 입력 시 가드 추가

**변경 3: 요약 헤더 중복 제거**
- `chat_processor._format_as_markdown()`의 "카카오톡 대화 요약 리포트" 헤더/푸터 제거
- `file_storage._format_summary_content()`의 헤더만 사용 (채팅방명, 날짜, LLM, 생성 시각 포함)

**변경 4: placeholder 개인정보 제거**
- CreateRoomDialog의 placeholder를 실제 고객명에서 일반 그룹명으로 변경

**변경 5: LLM read timeout 증가**
- `llm_client.py`의 read_timeout을 300초 → 600초로 증가

### v2.3.0 - 비모달 요약 프로그레스 & 대시보드 개선 (2026-02-01)

**변경 1: 모달 다이얼로그 → 상태바 프로그레스 위젯**
- `SummaryProgressDialog` (모달) 대신 `SummaryProgressWidget` (비모달) 사용
- 상태바에 `[채팅방명] LLM 요약 중...` + 프로그레스바 + 취소 버튼 표시
- 요약 중 메인 윈도우 자유롭게 조작 가능 (다른 채팅방 조회 등)

**변경 2: 중복 실행 방지 & 채팅방 전환 처리**
- `_summary_in_progress` 플래그로 중복 실행 차단
- `summary_source_room_id`로 요약 대상 채팅방 추적
- 완료 시: 같은 방이면 대시보드 갱신, 다른 방이면 상태바 알림만

**변경 3: closeEvent 추가**
- 요약 진행 중 앱 종료 시 확인 다이얼로그 → worker.cancel() + wait(5000)

**변경 4: 대시보드 카드 컴팩트화**
- `DashboardCard`에 `update_card(value, subtext)` 메서드 추가
- 아이콘+제목+값을 한 줄로 배치 (기존 3줄 → 1줄 + 서브텍스트)
- 폰트/패딩 축소로 카드 높이 절반 감소
- 서브텍스트에 실제 통계 표시: 대화 기간, 요약 진행률(N/M일, %)

**변경 5: DetachedInstanceError 수정**
- `database.py` sessionmaker에 `expire_on_commit=False` 추가
- 세션 종료 후 ORM 객체 속성 접근 시 에러 발생하던 버그 수정

### v2.3.1 - 기타 탭, 채팅방 복구, 도움말 정보 (2026-02-02)

**변경 1: 4번째 탭 "🔧 기타" 추가**
- 통계 정보 갱신 카드 (대시보드 + 채팅방 목록 새로고침)
- 향후 기능 추가 영역으로 활용

**변경 2: 도구 메뉴에 복구 기능 배치**
- DB 전체 복구 (`_on_recovery`): 파괴적 복구
- 채팅방 복구 (`_on_room_recovery`): 비파괴적, 파일 디렉터리 스캔 후 누락된 채팅방만 추가

**변경 3: URL 탭 동기화/복구 버튼 유지**
- URL 탭 헤더에 동기화/파일 복구 버튼 배치 (채팅방별 기능이므로 URL 탭에 유지)

**변경 4: `FileStorage.get_all_rooms()` url 디렉터리 포함**
- 기존: `data/original/` + `data/summary/`만 스캔
- 변경: `data/url/` 디렉터리도 포함하여 누락 방지

**변경 5: 도움말 정보 업데이트**
- 버전 2.3.1, 제작자: 민연홍, GitHub 링크 추가

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

### v2.4.0 - 데이터 안전성 및 견고성 강화 (2026-02-04)

**이슈 1: 채팅 데이터 로드 시 기존 데이터 삭제 (Data Loss)**
- **증상**: 채팅 파일 재업로드 시 기존 데이터가 사라지는 현상
- **원인**: `save_daily_original`에서 파싱 실패(0건) 또는 단순 병합 시 데이터 감소(파싱 포맷 차이 등)를 체크하지 않고 덮어씀
- **수정**:
  - `file_storage.py`: 기존 파일이 존재하는데 파싱 결과가 0건이면 원본 내용을 read_text로 복구
  - 병합 결과가 기존 데이터보다 적으면(`merged < existing`) 저장을 건너뛰는(Skip) 안전 장치 추가

**이슈 2: 요약 파일 대량 삭제 (Summary Invalidation)**
- **증상**: 업로드 시 모든 날짜의 요약 파일이 삭제됨
- **원인**: 메시지 데이터가 소량 변경(+1건)되거나 이전 불완전 데이터(134건)가 완전한 데이터(452건)로 바뀔 때 무조건 `New > Old` 조건으로 삭제(`unlink`)
- **수정**:
  - `file_storage.py`: `delete_daily_summary`를 `.bak` 파일로 리네임하는 백업 로직으로 변경 (영구 삭제 방지)

**이슈 3: DB 파일 손상 (Database Corruption) - 근본 원인 수정**
- **증상**: `sqlalchemy.exc.DatabaseError: database disk image is malformed` 발생 (LLM 요약 중 특히 빈번)
- **근본 원인**: **워커 스레드들이 싱글톤 `get_db()` 인스턴스를 공유**
  - `FileUploadWorker`, `SyncWorker`, `SummaryGeneratorWorker`가 모두 `__init__`에서 `self.db = get_db()`로 동일한 DB 인스턴스를 가져감
  - 워커 스레드가 DB 쓰기(`add_messages`, `add_summary`)를 하는 동안, 메인 UI 스레드도 DB 읽기(`get_all_rooms`, `get_room_stats`)를 수행
  - SQLite는 **단일 쓰기자(Single Writer)** 모델이므로, 동시 접근 시 `SQLITE_BUSY` 또는 저널 파일 충돌로 DB 손상 발생
- **수정**:
  - `main_window.py`: 각 워커 클래스의 `run()` 메서드 내에서 **전용 `Database()` 인스턴스**를 생성하도록 변경
  - 작업 완료 후 `worker_db.engine.dispose()`로 연결을 명시적으로 해제
  - 수정된 워커: `FileUploadWorker`, `SyncWorker`, `SummaryGeneratorWorker`
- **추가 방어**:
  - `llm_client.py`: API 500/Network 에러 시 최대 3회 재시도(Exponential Backoff) 로직 추가
  - `database.py`: `add_sync_log` 등 주요 쓰기 메서드에 `try-except` 블록을 씌워 로깅 실패가 앱 충돌로 이어지지 않도록 방어

**이슈 4: 앱 강제 종료 (App Crash)**
- **증상**: 요약 생성 도중 또는 파일 업로드 중 앱이 응답 없음 상태가 되거나 강제 종료됨 (특히 MiniMax 모델 사용 시에도 발생)
- **원인**: 디버깅을 위해 추가한 `print()` 문이 반복문 내에서 수천 번 실행되면서 콘솔 출력 버퍼 오버플로우 또는 Windows 콘솔 I/O 블로킹 유발 (UI 스레드와 워커 스레드 간 간섭 심화)
- **수정**:
  - `main_window.py`: 반복문 내의 디버그용 `print()` 구문 전면 제거

**이슈 5: 파일 재업로드 시 모든 요약 삭제 (Mass Invalidation)**
- **증상**: 파일을 재업로드하면 오늘만이 아니라 **모든 날짜**의 요약이 무효화됨
- **원인**: 메시지 수 비교 방식의 부정확성 (포맷 차이로 인한 오감지)
- **수정**: **파일 크기 비교 방식**으로 변경
  - `file_storage.py`: `get_original_file_size()`, `invalidate_summary_if_file_changed()` 추가
  - `main_window.py`: `FileUploadWorker`가 저장 전/후 파일 크기를 비교하여 실제 변경된 날짜만 무효화
  - **효과**: 파일 내용이 동일하면 크기가 동일 → 요약 유지 ✅

---

## ⚠️ 개발 시 주의사항

### 코드 변경 후 재기동
- **LLM 요약 수집 중일 때는 앱 종료 전 요약 완료를 기다려야 함**
- `closeEvent`에서 요약 진행 중이면 확인 다이얼로그를 표시하고, `worker.cancel()` + `wait(5000)`으로 안전하게 종료
- 요약 중간에 강제 종료하면 일부 날짜의 요약이 유실될 수 있음

### 백업/복원 기능 (v2.5.0)

**도구 메뉴 구조:**
```
도구
├── 💾 전체 백업... (Ctrl+B)     - DB + 모든 파일 백업
├── 💾 채팅방 백업...            - 선택된 채팅방만 백업
├── ─────────────
├── 📂 백업에서 복원...          - 백업에서 전체/개별 채팅방 복원
├── ─────────────
├── 🔄 파일에서 DB 재구축...     - 현재 파일에서 DB 재생성 (파괴적)
├── 🔄 누락 채팅방 DB 추가...    - 파일에는 있지만 DB에 없는 채팅방 추가
```

**용어 정리:**
- **백업/복원**: `data/backup/` 스냅샷 관리
- **재구축/DB 추가**: 현재 `data/original/`, `data/summary/` ↔ DB 동기화

---

*마지막 업데이트: 2026-02-10 | 버전: v2.5.1*
