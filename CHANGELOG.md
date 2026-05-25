# 변경 이력 (Changelog)

형식: [Semantic Versioning](https://semver.org/)에 가깝게 **주.부.패치**로 표기합니다.  
이전 버전의 상세 히스토리는 `README.md`의 “변경 이력” 절과 `docs/06-tasks.md`를 참고하세요.

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
