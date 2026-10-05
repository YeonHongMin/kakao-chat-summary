# 변경 이력 (Changelog)

형식: [Semantic Versioning](https://semver.org/)에 가깝게 **주.부.패치**로 표기합니다.  
이전 버전의 상세 히스토리는 `README.md`의 “변경 이력” 절과 `docs/06-tasks.md`를 참고하세요.

## [2.9.20] — 2026-10-05

### 채팅방 전환 지연 개선 (NFS 환경 UI 프리징 수정)

- **증상**: 채팅방을 클릭해 옮길 때마다 UI가 수 초씩 멈춤
- **원인**: 방 전환 경로의 무거운 I/O가 전부 UI 스레드에서 동기 실행됨. NFS 위 630MB / 170만 건 DB의 집계 쿼리(`get_room_stats` 3회 스캔)와 날짜 탭 파일 읽기(디렉터리 glob, 원본 md, 상세 HTML — 게다가 `dateChanged` 시그널 + 명시 호출로 2회 중복 실행)가 매 전환마다 네트워크 왕복을 유발
- **수정 (`src/ui/main_window.py`)**:
  - `RoomStatsWorker` 추가: 방 통계를 백그라운드 조회하고, 결과를 `_room_cache[room_id]["stats"]`에 실제로 저장 (기존에는 `loaded` 플래그만 저장해 캐시가 사실상 무의미했음). 재방문 시 즉시 표시
  - `DateTabLoadWorker` 추가: 날짜 목록 glob + 원본/상세 파일 읽기를 워커로 이동. 방 전환·날짜 변경 모두 비동기, seq 가드로 stale 결과 폐기
  - `_update_date_tab_for_room`의 이중 호출 제거 — `setDate` 시 `blockSignals`로 `dateChanged` 재진입 차단
  - 방 이름 조회를 목록 캐시(`_room_name_for`)로 전환해 선택 경로의 DB 왕복 추가 제거
  - 캐시 무효화 시 현재 방 통계를 백그라운드 재조회해 대시보드 최신 유지
  - 🐛 **Qt abort (0xc0000409) 크래시 수정**: 워커들이 `finished`라는 이름으로 `QThread.finished`를 섀도잉한 커스텀 시그널을 `run()` 안에서 emit하고, 거기 `deleteLater`가 연결되어 있어 스레드가 아직 running 상태(finally의 `engine.dispose()` 실행 중)일 때 C++ 객체가 파괴 → 프로세스 abort. 페이로드 시그널을 `done`으로 분리하고 정리/파괴는 `run()` 완전 종료 후 발생하는 네이티브 `finished`에 연결
  - `RoomListLoadWorker` 재시작 시 `terminate()` 제거 — NFS 블로킹 I/O는 강제 종료 불가, 참조 유지 + stale 검사로 대체. 실행 중 워커는 `_bg_workers` set에 보관해 종료 전 GC 방지
- **수정 (`src/db/database.py`)**:
  - `get_room_stats`: COUNT·COUNT DISTINCT·MIN/MAX를 단일 집계 쿼리로 병합 (인덱스 범위 스캔 3회 → 1회)
  - `Base.metadata.create_all`을 프로세스·경로별 1회로 제한 — 워커용 `Database()` 생성 때마다 NFS 스키마 DDL이 반복되던 것 제거
- **비고**: DB는 공유 디렉터리(NFS)에 유지 — 로컬 이동 없이 코드만으로 개선

### 버전 표시

- `app.py`, About 다이얼로그, `start_background.ps1` → `2.9.20`

---

## [2.9.19] — 2026-10-03

### 파일 업로드 대기열 (크래시 수정)

- **증상**: 업로드 진행 중 다른 파일을 업로드하면 앱이 강제 종료 (`pythonw.exe`, `Qt6Core.dll`, `0xc0000409`)
- **원인**: 업로드 버튼이 작업 중에도 활성 상태라 `self.upload_worker`가 새 워커로 교체됨 → 실행 중이던 이전 `QThread`가 GC되어 Qt가 프로세스를 abort. 두 업로드가 동시에 NFS SQLite에 쓰는 위험도 있었음
- **수정 (`src/ui/main_window.py`)**:
  - 업로드를 대기열(`_upload_queue`)에 넣고 한 번에 하나씩 순차 처리. 대기 중 상태바에 `N개 대기`, 진행 중 `[2/3] [방이름] ...` 표시
  - 다음 파일 시작 전 이전 워커 `wait()` — `finished`가 `run()` 안에서 emit되므로 스레드 종료를 보장
  - 파일별 팝업 대신 전체 완료 후 `성공 N개 / 실패 M개` 요약 1회, 마지막 성공 채팅방 선택
  - `_busy_guard`에 업로드 포함 (업로드 중 백업/복원/DB 복구 차단)
  - 종료 시 업로드 진행 중이면 확인 후 대기열 취소, 현재 파일만 마무리

### 버전 표시

- `app.py`, About 다이얼로그, `start_background.ps1` → `2.9.19`

---

## [2.9.18] — 2026-08-30

### 토픽 과압축 핫픽스

- **프롬프트 복구**: v2.9.17의 “묶으세요/잡담 흡수” 문구가 50여 개 토픽을 5개로 압축하는 문제를 일으켜, 기존 세분화 규칙(모든 주제 빠짐없이, 적어도 20개·많으면 30~40개, 짧은 언급도 독립 토픽, 토픽 수 축소 금지)을 복구
- **남는 제한은 쪼개기만**: 하나의 연속 토론을 개념/통계/증상처럼 여러 `<h2>`로 나누지 말 것. 다른 도구·URL·사업은 각각 별도 토픽
- 본문 🔗 필수 규칙과 `auto_link_topics_in_html` 후처리는 유지

### 버전 표시

- `app.py`, About 다이얼로그 → `2.9.18`

---

## [2.9.17] — 2026-08-30

### 상세 분석 토픽 병합·본문 링크

- **토픽 병합 프롬프트**: 같은 주제(개념/통계/증상)를 쪼개지 않고 1개로 통합. 인사·잡담은 연관 토픽에 흡수. 서로 다른 논의는 합치지 않음
- **본문 URL 링크 필수화**: 깃허브·웹·기사 논의 토픽의 `<li>` 끝에 `<a href="실제URL">🔗</a>`를 넣도록 규칙 강화. URL 모음에만 넣고 본문에서 빼는 것을 금지
- **사후 자동 링크 보정 (`auto_link_topics_in_html`)**: LLM이 본문 링크를 빠뜨려도 URL 카드/원본 대화의 레포명·도메인 키워드로 `<li>` 끝에 🔗를 보정

### 버전 표시

- `app.py`, About 다이얼로그 → `2.9.17`

---

## [2.9.16] — 2026-08-29

### 병렬 LLM 상세 분석 (`ParallelAllRoomsDetailWorker`)

- **채팅방 레인(Lane) 병렬 처리**: 전체 채팅방 상세 분석을 1~4개 레인으로 동시 실행 (기본 3레인, 이론상 최대 3배 단축)
- **다중 LLM 모델 선택**: Ctrl+Shift+G 다이얼로그에서 여러 모델 체크 → 채팅방에 라운드로빈 배정 (같은 모델 N레인도 지원)
- **제공자별 동시 호출 상한**: `LLMProvider.max_concurrency`(기본 2) 세마포어로 rate limit 429 방지
- **NFS SQLite 안전 설계**: 레인 스레드는 LLM 호출 + HTML 파일 저장만 수행 (DB 접근 금지), DB 쓰기(방별 URL 동기화)는 코디네이터 스레드가 단독 직렬 수행 — 동시 쓰기 충돌 구조적 차단
- **레인 현황 실시간 표시**: 상태바에 `⏳ 3레인 | 방A 08-12(MiniMax) · 방B 08-03(GLM) — 12/152일` 형식
- **방 완료 즉시 URL 자동 동기화**: 병렬 상세 분석 완료된 방은 코디네이터가 바로 URL 수집 (별도 Ctrl+Shift+U 불필요)

### UI

- **채팅방 목록 로딩 진행률 실측화**: 단일 통짜 집계 쿼리(진행률 보고 불가, 65% 고정 현상) 대신 방 단위 개별 집계로 전환 — 게이지가 `[12/28] 방이름 집계 중...`과 함께 실제 진행률만 표시 (가상 % 제거). 로딩 카드는 재생성 없이 갱신
- **업로드 후 목록 스크롤 튐 해소**: 파일 업로드/채팅방 생성 완료 시 전체 DB 재집계(`_load_rooms`) 대신 해당 방 1개만 부분 갱신(`_refresh_room_in_cache`) — 로딩 카드 없이 즉시 반영되고 스크롤 위치 유지
- **목록 재렌더링 스크롤 보존**: `_render_room_list`가 재렌더링 전 스크롤 위치를 저장하고 복원

### 버전 표시

- `app.py`, About 다이얼로그 → `2.9.16`

---

## [2.9.15] — 2026-08-29

### 성능 최적화 (NFS I/O & DB)

- **URL 동기화 멀티스레드 병렬 I/O (`url_extractor.extract_room_urls_parallel`)**:
  - 상세 분석 HTML 파일 순차 읽기/파싱을 `ThreadPoolExecutor` 기반 병렬 처리로 개편
  - NFS 네트워크 지연(RTT) 병목을 해소하여 단일 및 전체 채팅방 URL 수집 속도 10배~50배 향상
- **DB URL 일괄 저장 단일 트랜잭션 최적화 (`Database.add_urls_batch`)**:
  - 매 URL마다 열고 닫던 트랜잭션(N+1 쿼리)을 1회 일괄 조회 및 단일 세션 커밋으로 통합
- **상세 분석 생성 후 자동 URL 동기화 고속화**: `_auto_sync_urls`에 병렬 I/O 적용

### 안정성 및 버그 수정 (Reflextion 반영)

- **채팅방 삭제 시 백업 후 완전 삭제 (고아 방지)**: 삭제 다이얼로그에 `💾 백업 후 완전 삭제(권장)` / `🗑️ DB만 삭제` 선택 제공. 백업 성공 시에만 DB + 파일(원본/상세분석/URL) 삭제, 실패·취소 시 전체 중단
- **채팅방 목록 로딩 에러 핸들러 크래시 방지**: `_show_room_list_loading`에 `sub_text` 파라미터 지원 및 타입 가드 추가로 DB 오류 시 `TypeError` 예방
- **스레드 시작 중복 호출 제거**: `_load_rooms` 내 `room_list_worker.start()` 중복 제거
- **백업 목록 용량 표시 개선**: `size_mb <= 0`인 경우 `(0.0 MB)` 대신 `[생성일시]` 표시
- **채팅방 이름 정렬 개선**: 대소문자 구분 없이 자연스러운 오름차순 정렬 (`.lower()`)
- **보안 및 환경 설정 정비**: `.gitignore`에 `data/detail_summary/` 명시 추가, `env.local.example` 사설 IP 정리

### 버전 표시

- `app.py`, About 다이얼로그 → `2.9.15`

---

## [2.9.14] — 2026-08-29

### UI · UX

- **채팅방 목록 정렬 텍스트 가운데 정렬**: 헤더 영역 정렬 콤보박스의 텍스트 표시 및 드롭다운 항목을 가운데 정렬로 개선
- **대용량 DB(500MB+) 비동기 로딩**: `RoomListLoadWorker`를 추가하여 기동/새로고침 시 UI Freezing(Hang) 원천 방지 및 로딩 안내 카드 제공
- **채팅방 목록 인메모리 정렬 캐싱**: 정렬 변경 시 DB 재조회 없이 0.01초 내 메모리 즉시 재정렬
- **전체 채팅방 상세 분석 요약 순서 정렬 옵션**: `Ctrl+Shift+G` 다이얼로그에 요약 순서 옵션(대용량 우선/빠른 완료/메시지순/이름순/최신순) 및 실시간 프리뷰 추가

### 버전 표시

- `app.py`, About 다이얼로그 → `2.9.14`

---

## [2.9.13] — 2026-08-16

### 데이터 안전

- **NFS/SMB SQLite 안정화 (`src/db/database.py`)**
  - 네트워크 경로 감지 시 `journal_mode=DELETE` (기본 DB 경로 `data/db/` 유지, 공유 DB 분리 없음)
  - 로컬 디스크는 기존처럼 WAL
  - 선택: `SQLITE_JOURNAL_MODE`, `CHAT_DB_PATH` (개인 PC만, 기본값 변경 없음)
  - 백업/복원이 실제 DB 경로를 따름 (`file_storage.py`)

### LLM · 상세 분석

- **DeepSeek V4 Flash 출력 잘림 수정**: API는 `max_tokens` 사용 (`max_completion_tokens` 무시 → ~8K 잘림)
- **제공자별 출력 API 필드 예방** (`max_tokens_api_field`): MiniMax/MiMo `max_completion_tokens`, DeepSeek `max_tokens`
- 잘림 로그: 요청 한도 필드·값과 `completion_tokens` 함께 기록

### UI

- **채팅방 목록 정렬**: `💬 채팅방` 헤더 옆 콤보 — 메시지 수 / 최신 업데이트 / 이름순

### 문서

- 동일 버전(`2.9.13`) 추가 변경 상세: [`docs/unreleased-changes.md`](unreleased-changes.md)

### 버전 표시

- 앱 전반 버전 `2.9.13` (번호 변경 없음)

---

## [2.9.12] — 2026-08-16

### 기능

- **DeepSeek V4 Flash LLM 제공자 (`deepseek`)**
  - `full_config.py`: `deepseek-v4-flash`, 1M context, `DEEPSEEK_API_KEY`
  - `detail_prompt.py`: `thinking: disabled` (기본 thinking ON 대응)
  - 설정 다이얼로그·상세 분석 LLM 선택 목록에 자동 반영 (`LLM_PROVIDERS`)
  - *(v2.9.13 추가)* 출력 한도는 `max_tokens` 필드 — 상세는 `docs/unreleased-changes.md`

### 버전 표시

- 앱 전반 버전 `2.9.12` (`src/app.py`, About 다이얼로그)

---

## [2.9.11] — 2026-08-16

### UX

- **백업 진행률 (`src/ui/main_window.py`, `src/file_storage.py`)**
  - `BackupWorker` — 전체/채팅방 백업을 UI 스레드 밖에서 파일 단위 복사
  - 상태바 프로그레스 + 취소 (취소 시 부분 백업 디렉터리 삭제)

### 데이터 안전

- **복원·복구 동시 실행 방지**: `_busy_guard`를 백업/복원/DB 복구/누락 채팅방 추가에 적용
- **전체 복원 SQLite WAL**: 기존 `-wal`/`-shm` 정리 후 백업본이 있으면 세트로 복원, 복원 전 `reset_db()`
- **`get_rooms_in_backup()`**: `detail_summary` 디렉터리도 스캔

### 버전 표시

- 앱 전반 버전 `2.9.11` (`src/app.py`, About 다이얼로그)

---

## [2.9.10] — 2026-08-14

### 성능 및 UX

- **기동 속도 (`src/ui/main_window.py`, `src/db/database.py`)**
  - 채팅방 목록 DB 조회 N+1 제거 — `get_all_rooms_with_message_counts()` 단일 쿼리
  - `MainWindow` 생성 시 `_load_rooms()`를 `QTimer`로 지연 — **창을 먼저 표시**하고 목록은 비동기 로드
  - 기동 중 "채팅방 목록 로드 중..." 플레이스홀더 표시
- **URL 탭 (`src/ui/main_window.py`)**
  - `UrlLoadWorker` — DB·파일 I/O를 UI 스레드 밖에서 수행
  - 섹션당 최대 50개 URL만 HTML 렌더링 (1주·전체 포함)
  - URL 로드 중 방 전환 시 UI 블로킹 제거 (`worker.wait()` 제거, 시퀀스로 stale 결과 무시)
- **상세 분석 취소 (`src/detail_prompt.py`, `src/ui/main_window.py`)**
  - `call_detail_llm()`에 `cancel_event` — API 대기·재시도 sleep 중 즉시 취소 (기존: 현재 날짜 LLM 호출 완료까지 대기)
  - `DetailSummaryWorker` / `DetailBatchWorker` / `AllRoomsDetailWorker`에 `threading.Event` 연동

### 기타

- **`start_background.ps1`**: 기동 전 `python`/`pythonw` 앱 프로세스 모두 정리, `logs/startup_stderr.txt`에 stderr 기록
- 앱 전반 버전 `2.9.10` (`src/app.py`, About 다이얼로그)

---

## [2.9.9] — 2026-07-05

### 버그 수정

- **URL 탭 들여쓰기 깨짐 (`src/url_extractor.py`, `src/ui/main_window.py`)**
  - LLM 상세 분석 HTML의 잘못된 태그(`</nbsp;` 등)가 설명에 남아 URL 탭 렌더링이 밀리던 문제
  - `_strip_html_to_text()`로 추출 시 태그 조각 제거, 표시 시 `html.escape` 적용
- **URL 설명 무한 누적 (`src/url_extractor.py`, `src/ui/main_window.py`)**
  - 같은 URL이 여러 날짜 상세 분석에 등장할 때 설명 블록이 계속 합쳐지던 문제
  - `merge_urls_by_date()` 도입 — 동일 URL은 **가장 최근 날짜** 설명만 유지 (전체/채팅방/자동 동기화 공통)

### 기타

- `.gitignore`에 `startup_log.txt` 추가
- `README.md` 데이터 보안 섹션 보강 (LLM 전송·로그 주의)
- 앱 전반 버전 `2.9.9` (`src/app.py`, About 다이얼로그)

---

## [2.9.8] — 2026-07-04

### 추가 및 변경

- **설정 다이얼로그(UI)에서 API 키·LLM 제공자 저장 (`src/ui/main_window.py`, `src/full_config.py`)**
  - 도구 → 설정에서 LLM 제공자와 API 키를 입력해 `.env.local`에 영구 저장
  - 제공자 콤보박스 변경 시 해당 키를 불러옴 (Ollama는 키 불필요)
  - `LLM_PROVIDER`도 `.env.local`에 저장되어 재시작 후에도 유지
  - 빈 API 키로 확인 시 기존 `.env.local` 값을 덮어쓰지 않음
- **Xiaomi MiMo LLM 제공자 추가 (`full_config.py`, `detail_prompt.py`, `env.local.example`)**
  - 모델 `mimo-v2.5-pro`, `MIMO_API_KEY` 환경 변수
  - MiMo API 호환: `max_completion_tokens`, `thinking: {type: disabled}`, `api-key` 헤더
  - MiMo Token Plan(`tp-`) 전용 Base URL 자동/수동 설정 (`MIMO_BASE_URL`, 종량제 `sk-`와 URL 혼용 시 401)
- **LLM별 입력 컨텍스트 상한 정비 (`full_config.py`, `env.local.example`)**
  - `_input_chars_from_context()` 도입: `(공식 컨텍스트 tokens − max_tokens) × 1.5` (한글 대화 근사)
  - **GLM-5.2 업그레이드**: `glm-4.5` → `glm-5.2` (1M context, 출력 128K), `ZAI_MAX_INPUT_CHARS=1450848`, `ZAI_MODEL` env 지원
  - gpt-4o-mini 128K → `OPENAI_MAX_INPUT_CHARS=167424` (신규 `OPENAI_MAX_TOKENS`)
  - MiniMax-M3 512K(표준 요금) → `MINIMAX_MAX_INPUT_CHARS=718848`
  - sonar 128K → `PERPLEXITY_MAX_INPUT_CHARS=168000` (신규 `PERPLEXITY_MAX_TOKENS`)
  - MiMo 1M → `MIMO_MAX_INPUT_CHARS=1450848`, `MIMO_MAX_TOKENS=32768`
  - Grok/OpenRouter/Kilo/Ollama: 기본 `*_MAX_INPUT_CHARS=0` (자르기 없음)
  - 잘못된 GLM/MiMo `1500000` chars·MiMo 1 MiB bytes 가정 제거
- **문서**: `README.md`, `CLAUDE.md`, `docs/02-trd.md`, `docs/03-user-flow.md`, `docs/06-tasks.md` v2.9.8 반영
- 앱 전반 버전 `2.9.8` (`src/app.py`, About 다이얼로그)

---

## [2.9.7] — 2026-06-08

### 버그 수정

- **Windows cp949 콘솔 인코딩 호환 (`src/app.py`)**
  - 증상: Windows에서 `python.exe src/app.py`로 띄운 뒤 파일 업로드 시 `UnicodeEncodeError: 'cp949' codec can't encode character 'ℹ' in position 0`로 워커가 종료됨
  - 원인: 일별 원본 파일 저장 후 `print(f"ℹ️ ... 과거 날짜 원본 파일 보호")` 호출 지점에서 Windows 콘솔 기본 인코딩(cp949)이 ℹ️(U+2139)를 인코딩하지 못함
  - 수정: 앱 진입 시점에 `sys.stdout` / `sys.stderr`를 `utf-8 + errors="replace"`로 재설정. `reconfigure` 미지원이거나 `None`인 스트림(pythonw, 리다이렉트)은 안전 스킵
  - 크로스 플랫폼: macOS/Linux는 stdout이 이미 UTF-8이라 no-op, Windows에서만 실질 동작

---

## [2.9.6] — 2026-05-25

### 성능 최적화 및 UI 튜닝

- **지연 로딩(Lazy Loading) 적용 (`src/ui/main_window.py`)**
  - 채팅방 전환 시 탭 이동(날짜별 요약, URL 정보)에 필요한 파일 I/O 및 파싱 작업을 탭 활성화 시점까지 지연
- **UI 프리징(Freezing) 해결**
  - 무거운 HTML 파일 및 여러 개의 JSON 데이터를 동기적으로 렌더링하면서 발생하던 메인 스레드 멈춤 현상 제거
- **타이머 기반 비동기화 분산**
  - `QTimer.singleShot`을 활용해 채팅방 목록 클릭 시 즉시 하이라이트 효과가 적용되도록 이벤트 루프 처리 순서를 최적화

---

## [2.9.5] — 2026-05-05

### 변경

- **MiniMax (`full_config` / `detail_prompt`)**
  - 기본 `max_tokens` **32768** (`MINIMAX_MAX_TOKENS`로 조절).
  - API 응답이 **`finish_reason=length`** 로 잘렸는데 본문에 `<h2>`가 없을 때, 부분 분석용 `<h2>`·래퍼를 넣어 **검증 실패로 인한 긴 재시도**를 줄임.
- **GLM (`full_config`)**
  - 기본 **`ZAI_MAX_TOKENS` 8192 → 32768** (상세 분석 HTML 출력 잘림 완화). `.env.local`에 값이 있으면 그대로 우선.
- **로그 (`detail_prompt.call_detail_llm`)**
  - `KakaoSummarizer` 로그 메시지 앞에 **`[채팅방이름 | YYYY-MM-DD]`** 접두사를 붙여 `logs/summarizer_*.log`, `logs/info_*.log`에서 작업 단위 구분이 쉬움.
- **환경 예제 (`env.local.example`)**
  - 파일 복구·정리. `ZAI_MAX_TOKENS`, `ZAI_MAX_INPUT_CHARS` 등 `full_config.py`의 `os.getenv` 항목과 주석 대응. 실제 비밀/개인 설정이 아닌 **플레이스홀더만** 유지.
- **UI (`src/ui/styles.py`)**
  - `QTextBrowser` 선택 영역 배경/글자색 (카카오 노랑 계열)로 링크 색과 구분.

### 버전 표시

- 앱: `src/app.py` `setApplicationVersion`, 도움말 About (`main_window.py`) **2.9.5**
- 문서: `README.md`, `CLAUDE.md`, `docs/02-trd.md`, `docs/06-tasks.md` 헤더/히스토리 갱신

---

## [2.9.4] — 2026-05-04

- 기본 LLM MiniMax, `LLM_PROVIDER` 빈 값 정규화, 상세 분석 다이얼로그 콤보 폴백, 설정 창 `LLM_PROVIDERS` 연동·`set_provider`, 버전 문자열 통일 등.  
  (상세 bullet은 `README.md` / `CLAUDE.md` 참고.)

---

이전 릴리스는 저장소의 `README.md` “📝 변경 이력”에 역순으로 정리되어 있습니다.
