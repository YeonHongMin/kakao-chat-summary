# 02. Technical Requirements Document (TRD)

## 1. 시스템 아키텍처 (v2.9.11)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        app.py (메인 진입점)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  ui/main_window.py                           │   │
│  │                   (PySide6 GUI)                              │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │   │
│  │  │ 대시보드 │  │날짜별요약│  │ URL 정보 │  │ 🔧 기타  │    │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │   │
│  │  HBox 레이아웃 상태바 (v2.9.2: 좌/중앙/우) │               │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                             │                                       │
│  ┌──────────────────────────┼──────────────────────────────────┐   │
│  │              비즈니스 로직 & 데이터 처리                    │   │
│  │  ┌─────────┐  ┌────────────┐  ┌──────────────┐  ┌────────┐ │   │
│  │  │parser.py│  │detail_prompt│  │file_storage.py│ │url_extr│ │   │
│  │  │(파싱)   │  │.py (상세분석)│  │(파일 저장소)  │ │actor  │ │   │
│  │  └────┬────┘  └─────┬──────┘  └──────┬───────┘  └───┬────┘ │   │
│  │       │             │                │               │       │   │
│  │       │      ┌──────┴──────┐        │               │       │   │
│  │       │      │full_config.py│       │               │       │   │
│  │       │      │(다중 LLM API)│       │               │       │   │
│  │       │      └──────┬──────┘        │               │       │   │
│  │       │             │                │               │       │   │
│  │       └─────────────┼────────────────┼───────────────┘       │   │
│  │                     │                │                       │   │
│  │           ┌─────────┴─────────┐  ┌──┴────────────┐           │   │
│  │           │   db/database.py  │  │  (SQLite)    │           │   │
│  │           │  (SQLAlchemy ORM) │  │  chat_history│           │   │
│  │           └───────────────────┘  │     .db      │           │   │
│  │                                   └──────────────┘           │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 모듈 상세

### 2.1 app.py
**역할**: 애플리케이션 진입점

```python
# PySide6 애플리케이션 초기화
app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())
```

---

### 2.2 ui/main_window.py
**역할**: 메인 GUI 윈도우

**주요 클래스** (v2.9.11 기준):
| 클래스 | 설명 |
|--------|------|
| `MainWindow` | 메인 윈도우 (탭, 메뉴, 상태바). 기동 시 `_load_rooms()` QTimer 지연 |
| `FileUploadWorker` | 파일 업로드 백그라운드 처리 |
| `UrlLoadWorker` | URL 탭 DB·파일 로드 (UI 스레드 비블로킹, v2.9.10) |
| `DetailSummaryWorker` | 단일 날짜 상세 분석 생성 (QThread, `cancel_event` 지원) |
| `DetailBatchWorker` | 다중 날짜 상세 분석 일괄 생성 (QThread, `cancel_event` 지원) |
| `AllRoomsDetailWorker` | 전체 채팅방 상세 분석 일괄 생성 (QThread, `cancel_event` 지원) |
| `AllRoomsUrlSyncWorker` | 전체 채팅방 URL 동기화 (QThread) |
| `BackupWorker` | 전체/채팅방 백업 (진행률·취소, v2.9.11) |
| `RecoveryWorker` | DB 복구 백그라운드 처리 |
| `CreateRoomDialog` | 채팅방 생성 다이얼로그 |
| `UploadFileDialog` | 파일 업로드 다이얼로그 |
| `DetailSummaryOptionsDialog` | 상세 분석 옵션 다이얼로그 (Ctrl+G) |
| `SummaryProgressDialog` | 요약 진행률 다이얼로그 (레거시, 보존) |
| `SummaryProgressWidget` | 상태바 내장 비모달 프로그레스 위젯 (v2.9.2: HBox 레이아웃) |
| `DashboardCard` | 대시보드 통계 카드 (컴팩트, update_card 메서드) |
| `SettingsDialog` | 설정 다이얼로그 (LLM 제공자·API 키 → `.env.local` 영구 저장) |

**탭 구조**:
1. **📊 대시보드**: 채팅방 통계
2. **📅 날짜별 상세 분석**: 달력, 상세 분석 HTML 보기/생성
3. **🔗 URL 정보**: 공유된 URL 목록 (섹션당 화면 50개), 동기화/복구 버튼
4. **🔧 기타**: 통계 갱신, 채팅방 백업/복원

---

### 2.3 db/database.py
**역할**: SQLite 데이터베이스 관리

**클래스**: `Database`

**주요 메서드**:
| 메서드 | 설명 |
|--------|------|
| `create_room(name, file_path=None)` | 채팅방 생성 |
| `get_all_rooms()` | 채팅방 목록 (메시지 수 내림차순) |
| `get_all_rooms_with_message_counts()` | 채팅방 + 메시지 수 단일 쿼리 (기동 N+1 방지, v2.9.10) |
| `get_room_by_id(room_id)` | 채팅방 조회 |
| `get_room_by_name(name)` | 이름으로 채팅방 조회 |
| `get_room_stats(room_id)` | 채팅방 통계 조회 |
| `delete_room(room_id)` | 채팅방 삭제 |
| `add_messages(room_id, messages, batch_size=500)` | 메시지 일괄 추가 (중복 체크) |
| `get_messages_by_room(room_id, start_date, end_date)` | 메시지 조회 |
| `get_message_count_by_date(room_id, target_date)` | 날짜별 메시지 수 |
| `add_summary(room_id, summary_date, summary_type, content, llm_provider)` | 요약 저장 |
| `get_summaries_by_room(room_id, summary_type)` | 요약 목록 조회 |
| `delete_summary(room_id, summary_date)` | 요약 삭제 |
| `add_urls_batch(room_id, urls)` | URL 일괄 추가 |
| `get_urls_by_room(room_id)` | URL 목록 조회 |
| `clear_urls_by_room(room_id)` | URL 전체 삭제 |

**SQLite 최적화**:
- WAL 모드 활성화
- `expire_on_commit=False` (세션 종료 후 ORM 객체 속성 접근 허용)
- 배치 처리 (500개 단위)
- 중복 메시지 체크

---

### 2.4 db/models.py
**역할**: SQLAlchemy ORM 모델 정의

| 모델 | 테이블 | 설명 |
|------|--------|------|
| `ChatRoom` | `chat_rooms` | 채팅방 정보 |
| `Message` | `messages` | 메시지 (UniqueConstraint) |
| `Summary` | `summaries` | 날짜별 요약 |
| `URL` | `urls` | 추출된 URL (UniqueConstraint: room_id, url) |
| `SyncLog` | `sync_logs` | 동기화 로그 |

---

### 2.5 file_storage.py
**역할**: 파일 기반 데이터 저장 (백업/복구용)

**주요 메서드**:
| 메서드 | 설명 |
|--------|------|
| `save_daily_original(room, date, messages)` | 원본 대화 저장 |
| `save_daily_summary(room, date, content, llm_provider)` | 요약 저장 |
| `load_daily_original(room, date)` | 원본 대화 로드 |
| `load_daily_summary(room, date)` | 요약 로드 |
| `get_available_dates(room)` | 원본 존재 날짜 목록 |
| `get_summarized_dates(room)` | 요약 존재 날짜 목록 |
| `get_dates_needing_summary(room)` | 요약 필요 날짜 (신규/업데이트) |
| `get_original_file_size(room, date)` | 원본 파일 크기 (바이트) |
| `invalidate_summary_if_file_changed(room, date, old_size, new_size)` | 파일 크기 변경 시 요약 무효화 |
| `get_all_rooms()` | 모든 채팅방 목록 (디렉터리 스캔) |
| `create_full_backup(progress_callback=None, cancel_check=None)` | 전체 백업 (파일 단위 진행률, v2.9.11) |
| `get_backup_list()` | 백업 목록 조회 (v2.4.0) |
| `backup_room(room, progress_callback=None, cancel_check=None)` | 개별 채팅방 백업 (v2.9.11 진행률) |
| `get_rooms_in_backup(backup_path)` | 백업 내 채팅방 목록 (`detail_summary` 포함, v2.9.11) |
| `restore_from_backup(backup_path, room=None)` | 백업에서 복원 (전체 복원 시 WAL/SHM 세트 교체, v2.9.11) |

---

### 2.6 full_config.py
**역할**: 전역 설정 및 다중 LLM 제공자 관리

**LLM 제공자 설정**:
| Provider | API URL | Model | 환경변수 |
|----------|---------|-------|----------|
| glm | .../api/coding/paas/v4/chat/completions | glm-5.2 | ZAI (1M ctx, 입력 1450848 chars) |
| chatgpt | .../v1/chat/completions | gpt-4o-mini | OPENAI_API_KEY |
| minimax | .../v1/chat/completions | MiniMax-M3 (**기본**) | MINIMAX_API_KEY |
| perplexity | .../chat/completions | sonar | PERPLEXITY_API_KEY |
| grok | .../v1/chat/completions | grok-4-1-fast-non-reasoning | XAI_API_KEY |
| qwen-or | openrouter.ai | (OPENROUTER_MODEL) | OPENROUTER_API_KEY |
| qwen-kilo | kilo.ai gateway | (KILO_MODEL) | KILO_API_KEY |
| mimo | token-plan-sgp.xiaomimimo.com (tp-) / api.xiaomimimo.com (sk-) | mimo-v2.5-pro | MIMO (1M ctx) |
| ollama | (OLLAMA_BASE_URL) | (OLLAMA_MODEL) | (없음) |

**Config 주요 메서드** (v2.9.8):
- `save_provider_to_env(provider)` — `LLM_PROVIDER`를 `.env.local`에 저장
- `save_api_key_to_env(api_key, provider)` — API 키 저장 (빈 값이면 파일 미갱신)
- `_input_chars_from_context(context_tokens, reserved_output_tokens)` — 입력 chars 상한 계산

**입력 컨텍스트 기본값** (v2.9.8, `(context − max_tokens) × 1.5` chars):

| Provider | Context | max_tokens | max_input_chars |
|----------|---------|------------|-----------------|
| glm | 1M | 32768 | 1450848 |
| chatgpt | 128K | 16384 | 167424 |
| minimax | 512K | 32768 | 718848 |
| perplexity | 128K | 16000 | 168000 |
| mimo | 1M | 32768 | 1450848 |
| grok / qwen-or / qwen-kilo / ollama | 2M / — | — | 0 (무제한) |

**환경 변수 로드**:
- `.env.local` (우선순위 높음)
- `.env`

---

### 2.7 llm_client.py (제거됨, v2.9.0)
기본 마크다운 요약 클라이언트는 삭제되었습니다. LLM 호출은 `detail_prompt.call_detail_llm()`이 담당합니다 (`cancel_event` 지원, v2.9.10).

---

### 2.8 parser.py
**역할**: 카카오톡 텍스트 파일 파싱

**클래스**: `KakaoLogParser`

**지원 형식**:
```
# PC/Mac: --------------- 2024년 1월 24일 ---------------
# 모바일: 2024년 1월 24일 수요일
# 심플: 2024. 1. 24.
```

---

### 2.9 chat_processor.py
**역할**: 채팅 텍스트 처리 및 포맷팅

**클래스**: `ChatProcessor(provider)`

| 메서드 | 설명 |
|--------|------|
| `process_summary(text)` | LLM으로 요약 후 본문만 반환 (헤더/푸터는 `file_storage`에서 추가) |
| `_format_as_markdown(content)` | 마크다운 포맷팅 (v2.2.3에서 헤더/푸터 제거, content.strip()만 반환) |

---

### 2.10 import_to_db.py
**역할**: CLI 기반 대량 DB import 유틸

**클래스**:
| 클래스 | 설명 |
|--------|------|
| `MessageParser` | 메시지 라인 파싱 (닉네임, 시간, 내용 추출) |
| `DataImporter` | 파일/디렉터리 일괄 import, 통계 표시 |

```bash
python src/import_to_db.py <파일 또는 디렉터리> [--stats] [--daily]
```

---

### 2.11 url_extractor.py
**역할**: URL 추출, 정규화 및 저장

| 함수 | 설명 |
|------|------|
| `extract_urls_from_text(text)` | 텍스트에서 URL 추출 |
| `extract_url_with_description(line)` | 단일 라인에서 URL+설명 추출 |
| `normalize_url(url)` | URL 정규화 (특수문자, fragment 제거) |
| `deduplicate_urls(urls_dict)` | URL 중복 제거 및 설명 병합 |
| `save_urls_to_file(dict, path)` | URL 목록 파일 저장 |

---

## 3. 데이터 흐름

### 3.1 파일 업로드 흐름
```
[파일 선택] → [FileUploadWorker]
       │
       ▼
[KakaoLogParser] → 날짜별 메시지 그룹화
       │
       ▼
[Database.add_messages] → SQLite 저장 (중복 체크)
       │
       ▼
[FileStorage.save_daily_original] → Markdown 파일 저장
       │
       ▼
[기존 요약 무효화] → 메시지 증가 시 요약 삭제
```

### 3.2 상세 분석 생성 흐름
```
[상세 분석 옵션 선택] → [DetailSummaryWorker / DetailBatchWorker / AllRoomsDetailWorker]
       │
       ▼
[FileStorage.get_dates_needing_summary] → 상세 분석 필요 날짜 확인
       │
       ▼
[FileStorage.load_daily_original] → 원본 대화 로드
       │
       ▼
[call_detail_llm] → LLM API 호출 (cancel_event로 즉시 취소 가능)
       │
       ▼
[응답 검증 + wrap_detail_html] → HTML 래핑
       │
       ▼
[FileStorage.save_detail_summary] → data/detail_summary/ 저장
```

### 3.3 백업 흐름 (v2.9.11)
```
[전체 백업 / 채팅방 백업] → [_busy_guard]
       │
       ▼
[BackupWorker] → 파일 목록 집계 → 파일 단위 복사 (진행률 시그널)
       │
       ▼
[취소 시] 부분 백업 디렉터리 삭제  /  [완료] data/backup/<timestamp>/
```

### 3.4 CLI 스크립트 (제거됨, v2.9.0)
`src/manual/` CLI와 `chat_processor`/`llm_client` 기반 마크다운 요약은 더 이상 제공되지 않습니다.

---

## 4. 에러 처리

| 에러 유형 | 처리 방식 |
|-----------|-----------|
| 파일 없음 | 경고 다이얼로그 |
| API 키 없음 | 설정 안내 메시지 |
| API 타임아웃 | 로그 기록, 다음 날짜 진행 |
| 불완전 LLM 응답 | 저장 거부, 경고 메시지 |
| DB 손상 | 복구 기능 제공 |

---

## 5. 로깅 시스템

**로그 파일**: `logs/summarizer_YYYYMMDD.log`

| 레벨 | 출력 대상 | 용도 |
|------|-----------|------|
| DEBUG | 파일만 | API 요청/응답 상세 정보 |
| INFO | 파일만 | 처리 진행 상황 |
| WARNING | 파일 + 콘솔 | 경고 메시지 |
| ERROR | 파일 + 콘솔 | 에러 상세 |
