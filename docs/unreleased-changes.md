# v2.9.20 및 이전 버전 변경 내역

> **앱 표시 버전**: `2.9.20` (`src/app.py`, About 다이얼로그)  
> **작성일**: 2026-10-05  
> 최신: v2.9.20 — 채팅방 전환 지연 개선 + 방 선택 크래시 수정.

---

## 0. 채팅방 전환 지연 개선 + abort 크래시 수정 (v2.9.20)

- **배경**: 방 클릭 시 UI가 수 초 멈춤. NFS 위 630MB/170만 건 DB의 집계 쿼리와 날짜 탭 파일 읽기가 전부 UI 스레드 동기 실행이었음. `QTimer.singleShot(10)` 지연은 같은 UI 스레드 재진입일 뿐 비동기가 아니었고, `setDate`의 `dateChanged` + 명시 호출로 같은 파일을 2회 읽는 버그도 있었음.
- **`RoomStatsWorker`**: `get_room_stats`를 워커로 분리, 결과를 `_room_cache[room_id]["stats"]`에 실제 저장 (기존엔 `loaded` 플래그만 있어 캐시 무의미). 재방문 즉시 표시.
- **`DateTabLoadWorker`**: 날짜 목록 glob + 원본 md + 상세 HTML 읽기를 워커로 이동. seq 가드로 stale 결과 폐기. `setDate` 시 `blockSignals`로 이중 로드 차단.
- **DB 개선**: `get_room_stats` 집계 3쿼리 → 1쿼리 병합. `Base.metadata.create_all`을 프로세스·경로별 1회로 제한 (워커 `Database()` 생성 시 NFS DDL 반복 제거).
- **🐛 방 선택 시 abort(0xc0000409) 수정**: 워커들이 커스텀 `finished` 시그널로 `QThread.finished`를 섀도잉하고 `run()` 안에서 emit — 연결된 `deleteLater`가 스레드 running 중(`finally`의 `engine.dispose()` 실행 중)에 C++ 객체 파괴 → Qt abort. 페이로드 시그널을 `done`으로 분리하고 `deleteLater`·정리는 네이티브 `finished`에 연결. 실행 중 워커는 `_bg_workers` set이 참조 유지, `RoomListLoadWorker`의 `terminate()` 제거(stale 결과는 identity 검사로 폐기).

---

## 이전 버전: v2.9.17 / v2.9.16 / v2.9.15

## 0. 토픽 병합·본문 링크 보정 (v2.9.17)

- **배경**: 하루 대화량이 많으면 LLM이 주제를 40~50개로 잘게 쪼개고, 본문 토픽에는 링크를 빼 맨 아래 URL 모음에만 몰아넣는 현상이 발생 (오픈바이브 2026-08-28: 50토픽 / 본문 `<a>` 0개).
- **프롬프트 병합**: 같은 도구·개념·이슈를 쪼개지 않고 1개로 묶음. 인사/잡담은 연관 토픽에 흡수. 서로 다른 논의는 합치지 않음 (토픽 수 목표는 없음).
- **본문 링크 규칙**: 깃허브·웹·기사 논의 토픽의 `<li>` 끝에 `<a href="실제URL">🔗</a>` 필수. URL 모음 전용 배치는 금지.
- **`auto_link_topics_in_html`**: LLM 응답 후처리. URL 카드와 원본 대화에서 레포명/도메인/제목 키워드를 모아, 본문 `<li>`에 링크가 없으면 보정. `call_detail_llm` 성공 경로에서 `clean_foreign_chars` 직후 실행.

---

## 1. 병렬 LLM 상세 분석 (v2.9.16, `ParallelAllRoomsDetailWorker`)

- **채팅방 레인(Lane) 병렬**: 전체 채팅방 상세 분석을 1~4개 레인(기본 3)으로 동시 실행. 한 방의 날짜는 해당 레인에서 순차 처리 → 파일 충돌 원천 차단.
- **다중 LLM 라운드로빈**: Ctrl+Shift+G 다이얼로그에서 여러 모델 체크 시 채팅방에 순환 배정. 같은 모델 N레인 병렬도 지원.
- **제공자별 동시 호출 상한**: `LLMProvider.max_concurrency`(기본 2) 세마포어 — 동일 제공자 rate limit(429) 방지.
- **NFS SQLite 안전 설계 (핵심)**: 레인 스레드는 LLM 호출 + HTML 파일 저장만 수행하고 DB에 접근하지 않음. DB 쓰기(방별 URL 동기화)는 코디네이터 스레드가 방 완료 이벤트를 받아 **한 번에 한 방씩 직렬** 수행 → 동시 쓰기 충돌이 구조적으로 불가능.
- **레인 현황 표시**: 상태바에 `⏳ 3레인 | 방A 08-12(MiniMax) · 방B 08-03(GLM) — 12/152일`.
- **로딩 게이지 실측 진행률**: 채팅방 목록 로딩을 단일 통짜 쿼리에서 방 단위 개별 집계로 전환. 게이지가 `[12/28] 방이름 집계 중...`과 실제 %만 표시 (65%/89% 고정 및 가상 진행 제거). `(room_id, ...)` 유니크 인덱스를 타므로 총 쿼리 비용은 기존과 동등.
- **업로드 후 목록 스크롤 튐 해소**: 파일 업로드·채팅방 생성 완료 시 전체 DB 재집계 대신 해당 방 1개만 부분 갱신(`_refresh_room_in_cache`) — 로딩 카드 없이 즉시 반영, 스크롤 위치 유지(`_render_room_list` 스크롤 저장/복원).

---

## 2. URL 동기화 멀티스레드 병렬 I/O (NFS 최적화)

- **배경**: NFS 환경에서 상세 분석 HTML 파일 수백 개를 단일 스레드로 순차 조회할 경우 네트워크 왕복 지연시간(RTT)으로 인해 URL 수집이 크게 지연되는 문제 해결.
- **`url_extractor.extract_room_urls_parallel` 구현**:
  - `ThreadPoolExecutor`를 활용하여 디렉터리 스캔 후 날짜별 HTML 파일 읽기 및 URL 정규식 추출을 멀티스레드로 동시 처리.
  - 단일 채팅방 및 전체 채팅방 URL 동기화 속도 10배~50배 향상.
- **`Database.add_urls_batch` 단일 트랜잭션 최적화**:
  - 기존 URL N건마다 개별 트랜잭션을 열던(N+1 쿼리) 방식을 1회 일괄 조회 및 단일 세션 커밋으로 통합하여 SQLite 디스크 I/O 락 완화.
- **상세 분석 완료 시 자동 URL 동기화 고속화**: `_auto_sync_urls`에 병렬 I/O 적용.

---

## 2. Reflextion 안정성 패치

- **채팅방 삭제 시 백업 후 완전 삭제 (고아 방지)**: 삭제 다이얼로그에 `💾 백업 후 완전 삭제(권장)` / `🗑️ DB만 삭제` 선택 제공. 백업 성공 시에만 DB + 파일(원본/상세분석/URL) 삭제, 백업 실패·취소 시 삭제 전체 중단.
- **채팅방 목록 로딩 에러 크래시 방지**: `_show_room_list_loading`에 `sub_text` 지원 및 타입 가드 적용.
- **스레드 중복 시작 제거**: `_load_rooms` 내 `room_list_worker.start()` 중복 호출 제거.
- **백업 목록 용량 표시 개선**: `size_mb <= 0`인 경우 `(0.0 MB)` 대신 `[생성일시]` 표시.
- **채팅방 이름 정렬 개선**: 대소문자 구분 없이 자연스러운 오름차순 정렬 (`.lower()`).
- **보안 및 환경 설정 정비**: `.gitignore`에 `data/detail_summary/` 명시 추가, `env.local.example` 사설 IP 정리.

---

## 3. 대용량 DB(500MB+) 비동기 로딩 및 진행률 표시 (`RoomListLoadWorker`)

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
