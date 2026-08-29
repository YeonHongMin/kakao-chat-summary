# v2.9.14 변경 내역

> **앱 표시 버전**: `2.9.14` (`src/app.py`, About 다이얼로그)  
> **작성일**: 2026-08-29  
> v2.9.14 릴리스 상세 변경 내역입니다.

---

## 1. 대용량 DB(500MB+) 비동기 로딩 및 진행률 표시 (`RoomListLoadWorker`)

- **UI Freezing(Hang) 해결**: 500MB+ SQLite DB에서 전체 메시지 수 및 채팅방 목록을 조회하는 작업을 백그라운드 QThread로 분리.
- **실시간 % 게이지 제공**: `10%` -> `40%` -> `65%` -> `90%` -> `100%` 단계별 프로그레스 바 및 메시지 렌더링.

---

## 2. 백업 확인 팝업 지연(1분 멈춤 현상) 완화

- `get_backup_list()` 호출 시 기존 백업 내 30,000+ 개 파일 크기 전수 조사를 기본적으로 생략하여 백업 버튼 클릭 시 1초 내 확인 창 표시.

---

## 3. 채팅방 목록 정렬 인메모리 처리 및 가운데 정렬 UI

- **인메모리 캐시**: 정렬 콤보박스 변경 시 527MB DB 재조회 없이 0.01초 내 메모리 즉시 재정렬.
- **가운데 정렬**: `CenterAlignComboBoxStyle` (QProxyStyle) 적용으로 버튼 내부 텍스트 및 드롭다운 항목 가운데 정렬.

---

## 4. 전체 채팅방 상세 분석(요약) 순서 정렬 옵션 추가

**위치**: 도구 > 전체 채팅방 상세 분석 생성 다이얼로그 (`Ctrl+Shift+G`)

| 옵션 | 정렬 기준 |
|------|-----------|
| 요약 필요 많은 순 (기본) | 미요약 일수 많은 방 우선 (대용량 우선) |
| 요약 필요 적은 순 | 미요약 일수 적은 방 우선 (빠른 완료) |
| 메시지 많은 순 | 전체 메시지 개수 내림차순 |
| 이름순 | 채팅방명 가나다/ABC 오름차순 |
| 최신 업데이트순 | `last_sync_at` 최신 순 |

- **실시간 프리뷰 연동**: 다이얼로그 내 `요약 순서` 드롭다운 변경 시 상단 채팅방 목록 프리뷰가 즉시 재정렬되어 표시됨.
- **워커 순서 반영**: 지정된 순서대로 `AllRoomsDetailWorker`가 대상 채팅방을 순회하며 요약 수행.

---

## 5. DeepSeek V4 Flash 출력 잘림 수정 (v2.9.13/v2.9.14)

**증상**: 상세 분석 시 `completion_tokens`가 ~8191에서 `finish_reason=length`로 잘림.

**원인**: DeepSeek API는 `max_tokens`를 사용. `max_completion_tokens`만내면 무시되고 서버 기본 한도(~8K) 적용.

**수정** (`src/detail_prompt.py`, `src/full_config.py`):

- DeepSeek: `max_tokens` + `thinking: disabled`
- `LLMProvider.max_tokens_api_field` / `thinking_disabled`로 제공자별 필드 명시

| 제공자 | 출력 한도 API 필드 | thinking |
|--------|-------------------|----------|
| MiniMax | `max_completion_tokens` | — |
| MiMo | `max_completion_tokens` | disabled |
| DeepSeek | `max_tokens` | disabled |
| GLM·ChatGPT·Grok·Perplexity·OR·Kilo·Ollama | `max_tokens` (기본) | — |

**환경 변수** (`.env.local` / `env.local.example`):

- `DEEPSEEK_MAX_TOKENS` — 기본 32768 (코드 기본값과 동일; 필드명 버그와 무관)
- `DEEPSEEK_MODEL`, `DEEPSEEK_API_KEY`

**로그**: 잘림 시 `{필드}={요청값} 요청, completion_tokens={실제}` 출력.

---

## 2. NFS/SMB SQLite 안정화 (v2.9.13 본편)

- 네트워크 경로(`F:` → NFS) 감지 시 `journal_mode=DELETE` (DB 경로 `data/db/` **공유 유지**)
- 로컬 디스크는 WAL 유지
- 선택 env: `SQLITE_JOURNAL_MODE`, `CHAT_DB_PATH` (개인 PC만, 전역 기본 변경 없음)
- 백업/복원이 `resolve_chat_db_path()` 실제 경로를 따름

---

## 3. 채팅방 목록 비동기 로딩 및 인메모리 정렬 캐싱

- **대용량 DB(500MB+) 비동기 로딩 (`RoomListLoadWorker`)**:
  - 메인 UI 스레드를 멈추지 않고 백그라운드 QThread에서 방 목록 및 메시지 수를 조회하여 UI Freezing(Hang) 원천 방지.
  - 로딩 중 카카오 스타일 로딩 안내 카드(`⏳ 대용량 데이터베이스를 안전하게 읽고 있습니다`) 시각적 제공.
- **정렬 변경 시 100% 인메모리 캐시 처리 (`_cached_rooms_with_counts`)**:
  - 정렬 콤보박스 변경 시 527MB DB 재조회 없이 메모리 캐시에서 즉시 0.01초 내 재정렬 및 렌더링.
- **NFS SQLite I/O 최적화 (`src/db/database.py`)**:
  - `synchronous="NORMAL"` 및 `busy_timeout=30000` 적용으로 NFS I/O 병목 및 락 대기 시간 완화.

---

## 4. 채팅방 목록 정렬 UI

**위치**: 좌측 패널 `💬 채팅방` 헤더 오른쪽 콤보박스

| 옵션 | 정렬 |
|------|------|
| 메시지 수 (기본) | 메시지 개수 내림차순 |
| 최신 업데이트 | `last_sync_at` 최근 순 (없으면 아래) |
| 이름순 | 채팅방명 오름차순 |

**파일**: `src/ui/main_window.py` (`ROOM_SORT_OPTIONS`, `_sort_rooms_with_counts`)  
**DB**: `get_all_rooms_with_message_counts()` — 정렬은 UI에서 수행

---

## 5. DeepSeek V4 Flash 제공자 (v2.9.12)

- 키: `deepseek`, 모델 `deepseek-v4-flash`, env `DEEPSEEK_API_KEY`
- 1M context, `DEEPSEEK_MAX_INPUT_CHARS` 기본 1450848

---

## 6. 전체 채팅방 상세 분석(요약) 순서 정렬 옵션 추가

**위치**: 도구 > 전체 채팅방 상세 분석 생성 다이얼로그 (`Ctrl+Shift+G`)

| 옵션 | 정렬 기준 |
|------|-----------|
| 요약 필요 많은 순 (기본) | 미요약 일수 많은 방 우선 (대용량 우선) |
| 요약 필요 적은 순 | 미요약 일수 적은 방 우선 (빠른 완료) |
| 메시지 많은 순 | 전체 메시지 개수 내림차순 |
| 이름순 | 채팅방명 가나다/ABC 오름차순 |
| 최신 업데이트순 | `last_sync_at` 최신 순 |

- **실시간 프리뷰 연동**: 다이얼로그 내 `요약 순서` 드롭다운 변경 시 상단 채팅방 목록 프리뷰가 즉시 재정렬되어 표시됨.
- **워커 순서 반영**: 지정된 순서대로 `AllRoomsDetailWorker`가 대상 채팅방을 순회하며 요약 수행.

---

## 재기동

```powershell
.\start_background.ps1
```

## 확인 체크리스트

- [ ] 좌측 채팅방 헤더에 정렬 콤보 표시
- [ ] DeepSeek 상세 분석: 로그 `completion_tokens`가 8191 근처가 아님 (장문일 때)
- [ ] NFS에서 채팅방 생성/조회 시 `disk I/O error` 재발 여부
- [ ] `logs/summarizer_*.log`에 `journal_mode=DELETE` (네트워크 경로 시)
