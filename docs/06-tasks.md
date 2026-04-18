# 06. Tasks & Development Roadmap

## 1. 완료된 작업 ✅

### Phase 1: 기반 구축
- [x] 프로젝트 구조 설계
- [x] `full_config.py` - 설정 관리 모듈 구현
- [x] `parser.py` - 카카오톡 파싱 모듈 구현

### Phase 2: 핵심 CLI 기능
- [x] `llm_client.py` - 통합 LLM API 클라이언트
- [x] `chat_processor.py` - 요약 처리 모듈 구현
- [x] `url_extractor.py` - URL 추출 모듈
- [x] CLI 스크립트 (full_*, simple_*)

### Phase 3: 다중 LLM 지원
- [x] GLM (Z.AI) 지원
- [x] ChatGPT (OpenAI) 지원
- [x] MiniMax 지원
- [x] Perplexity 지원
- [x] `--llm` CLI 옵션 추가
- [x] 대화형 LLM 선택 모드

### Phase 4: GUI 애플리케이션 (v2.0)
- [x] PySide6 기반 데스크톱 앱
- [x] 카카오톡 스타일 UI 테마
- [x] SQLite 데이터베이스 연동
- [x] SQLAlchemy ORM 모델
- [x] 채팅방 관리 (생성, 목록, 선택)
- [x] 파일 업로드 기능

### Phase 5: 파일 저장소 및 복구
- [x] `file_storage.py` - 파일 기반 저장소
- [x] 일별 원본 대화 저장 (data/original/)
- [x] 일별 요약 저장 (data/summary/)
- [x] DB 복구 기능 (파일 → SQLite)
- [x] 메시지 업데이트 시 요약 무효화 (v2.5.1: 메시지 해시 기반)

### Phase 6: 요약 생성 개선
- [x] 스마트 요약 (신규/업데이트 날짜만)
- [x] 요약 진행 다이얼로그 (실시간 진행률)
- [x] 취소 기능
- [x] LLM 선택 UI (드롭다운)
- [x] LLM 응답 완결성 검증

### Phase 7: UI/UX 개선
- [x] 탭 인터페이스 (대시보드, 날짜별 요약, URL 정보, 기타)
- [x] 달력 날짜 선택
- [x] 상태바 개선 (작업 완료 상태 표시)
- [x] URL 정보 탭 (추출, 정렬, 저장)

### Phase 8: 환경 설정
- [x] `.env.local` 지원
- [x] `env.local.example` 제공
- [x] CLI 스크립트 분리 (src/manual/)

---

## 2. 향후 개선 사항 📋

### 우선순위 높음 (P0)
- [ ] 테스트 코드 작성 (pytest)
- [ ] 다양한 카카오톡 버전 호환성 테스트
- [ ] 에러 핸들링 강화

### 우선순위 중간 (P1)
- [ ] 추가 LLM 지원 (Claude, Gemini 등)
- [ ] 프롬프트 템플릿 외부화 (YAML/JSON)
- [ ] 설정 다이얼로그 개선
- [ ] 자동 동기화 메인 앱 연동 (`SyncScheduler` 프레임워크 구현 완료, 앱 통합 필요)
- [ ] 요약 품질 평가 지표

### 우선순위 낮음 (P2)
- [ ] 웹 서비스화 (FastAPI)
- [ ] 다크 모드 테마
- [ ] 국제화 (i18n)
- [ ] 패키징 (PyInstaller)

---

## 3. 알려진 제한사항 ⚠️

### 3.1 파싱 관련
- 일부 특수한 카카오톡 내보내기 형식은 인식되지 않을 수 있음
- 이미지, 이모티콘은 텍스트로만 표시됨

### 3.2 API 관련
- 각 LLM 제공자별 API 키 필요
- API Rate Limit 존재 (순차 처리로 대응)
- 긴 대화는 토큰 제한에 걸릴 수 있음
- 불완전한 LLM 응답은 저장되지 않음

### 3.3 데이터베이스 관련
- SQLite 동시 접근 제한 (WAL 모드로 완화)
- 대용량 데이터 처리 시 배치 처리 권장

---

## 4. 버전 히스토리

### v2.9.2 (2026-04-18)
- **URL 동기화 작업 표시줄 UI 개선**
- 상태바 구조: `QStatusBar.addPermanentWidget()` → HBox 레이아웃 기반 재설계
- 프로그레스 위젯이 명확하게 표시되도록 개선 (높이 고정 28px, 최소 너비 설정)
- 채팗방별 URL 동기화와 전체 채팅방 URL 동기화 모두 적용
- 작업 중: 기존 상태바 컨테이너 임시 제거 → 프로그레스 위젯 추가 → 완료 후 복원
- 전체 채팅방 URL 동기화의 `all_room_names` undefined 변수 버그 수정

### v2.9.1 (2026-04-14)
- **상세 분석 안정성 및 타임아웃 개선**
- API 타임아웃: 600초 → 1200초(20분) 상향
- LLM 응답 검증 실패 시 재시도 누락 버그 수정 (최대 3회 자동 재시도)
- 소량 대화 날짜 검증 완화: 최소 2개 토픽 → 최소 100자로 변경
- 마크다운 응답 자동 변환: HTML `<h2>` 대신 `##` 사용 시 정규식으로 변환
- 초장문 결과 Silent Drop 버그 수정: 응답 잘림 시 "응답 잘림 경고" UI 삽입 후 저장

### v2.9.0 (2026-04-13)
- **BREAKING: 기본 요약 제거, 상세 분석 전용화**
- 제거: `llm_client.py`, `chat_processor.py`, `src/manual/` CLI, `SyncWorker`, 기본 요약 Workers/Dialogs, `PROMPT_TEMPLATE`
- 상세 분석 옵션 다이얼로그 추가 (Ctrl+G): pending/오늘/어제~오늘/전체 범위 선택
- `file_storage.py`: `get_summarized_dates()`/`get_dates_needing_summary()` → `detail_summary/` 기준
- `url_extractor.py`: `extract_urls_from_html()` 추가 (HTML 파싱)
- URL 동기화: 마크다운 → HTML 파싱 전환
- 전체 채팅방 상세 분석: DB + 파일 저장소 채팅방 통합, `get_available_dates()` 기준
- 대시보드 방 선택 속도 개선 (파일 I/O 제거)

### v2.8.5 (2026-04-12)
- **백그라운드 트레이 연동 및 한글/토큰 한계 대응**
- 트레이 아이콘 연동으로 백그라운드 구동 지속성 확보
- 한글 인코딩 및 토큰 초과 방어: `.env.local` 파서 수정 (`max_input_chars` 적용)

### v2.8.4 (2026-04-09)
- **DeepSeek 컨텍스트 제한 대응 및 프롬프트 개선**
- DeepSeek 32K 컨텍스트 한계 대응: 입력 문자열을 40,000자로 강제 잘라내기 (`max_input_chars` 필드 추가)
- 출력 토큰 제한: 8000으로 설정
- 상세 분석 토픽 추출: '최소 10개' → '최소 20개 이상(많으면 30~40개)'로 상향
- URL 자동 동기화 버그 수정: `NameError: name 'logger' is not defined` 수정

### v2.8.3 (2026-04-08)
- **상세 분석 앱 렌더링 보정**
- `QTextBrowser`의 잘못된 닫힘 태그(`</hp>` 등) 문제 수정
- 제목 스타일이 본문까지 번지는 문제 해결

### v2.8.2 (2026-04-05)
- **URL 정보 강화 및 한자/일본어 후처리**
- 한자→한글 독음 자동 변환 (`hanja` 라이브러리)
- 일본어(히라가나/가타카나) 자동 제거
- 기본 요약과 상세 분석 모두 적용
- URL 정보 포맷 강화: 내용/시사점/활용 구조 추가
- URL 추출기 멀티라인 지원 (새 포맷 호환)
- LLM 모델 업데이트: GLM `glm-5-turbo` → `glm-4.5`, MiniMax `M2.5` → `M2.7`
- 의존성 추가: `hanja>=0.15.0`

### v2.8.1 (2026-04-03)
- **프롬프트 제약 및 무효화 로직 개편**
- LLM 시스템 프롬프트 규칙 강화: 중국어, 일본어, 아랍어 제한
- 한글 설명/영어 용어 사용 강제
- 무효화 로직 개편: `summary` + `detail_summary` HTML 파일 모두 `.bak` 백업

### v2.8.0 (2026-03-29)
- **상세 분석 HTML 생성 기능 (완전한 대체 기능)**
- `src/detail_prompt.py`: 상세 분석 프롬프트 + 다크 테마 HTML 템플릿 + LLM API
- `data/detail_summary/<채팅방>/<채팅방>_YYYYMMDD_detail.html` 저장
- 프롬프트 구조: 키워드 TOP5 → 토픽별 분석 → URL 모음 → 감정/온도 분석 → 핵심 시사점
- 날짜별 요약 탭: 기본/상세 토글 버튼 추가
- 기존 마크다운 요약과 별도로 상세 분석 HTML 렌더링
- 다양한 생성 경로: 단일 날짜, 일괄 생성, 전체 채팅방 생성
- 추론 내용 자동 제거 (`<think>` 태그, `###` 이전 텍스트)
- 백업/복원에 `detail_summary/` 디렉터리 포함
- LLM 모델: GLM `glm-4.7` → `glm-5-turbo`, MiniMax `M2.1` → `M2.5`

### v2.5.1 (2026-02-26)
- **요약 무효화 정확도 개선**: 파일 크기 비교 → 메시지 내용 MD5 해시 비교로 변경
- `get_original_content_hash()`: 헤더/푸터 제외, 메시지 본문만 해시
- `invalidate_summary_if_content_changed()`: 해시 기반 무효화 판단
- 기존 `invalidate_summary_if_file_changed()` deprecated 처리
- **효과**: 동일 메시지 재업로드 시 저장 시각 변동으로 인한 불필요한 LLM 재수행 방지

### v2.5.0 (2026-02-04)
- **백업/복원 기능 강화**
- **채팅방 백업**: 선택된 채팅방만 별도 타임스탬프 디렉터리에 백업
- **백업에서 복원**: 백업 목록에서 선택하여 전체 또는 개별 채팅방 복원
- **메뉴 재구성**: 백업/복원(스냅샷) vs 재구축/DB추가(파일↔DB 동기화) 명확 분리
- **FileStorage 확장**: `backup_room()`, `get_rooms_in_backup()`, `restore_from_backup()` 추가

### v2.4.0 (2026-02-04)
- **데이터 안전성 및 견고성 강화 긴급 패치**
- **[Critical] 스레드 안전성 수정**: 워커 스레드별 독립 `Database()` 인스턴스 생성
- **파일 크기 기반 요약 무효화**: 재업로드 시 파일 크기 변경된 날짜만 요약 무효화
- **전체 백업 기능**: `create_full_backup()`, `get_backup_list()` 추가
- **Data Loss Prevention**: 데이터 감소 시 저장 건너뛰기
- **Summary Backup**: 요약 삭제 시 `.bak` 파일로 백업
- **API Retry**: 최대 3회 재시도 (지수 백오프)

### v2.3.1
- **기타 기능 탭 추가**: 4번째 탭 "🔧 기타" (통계 정보 갱신, 향후 확장용)
- **도구 메뉴에 복구 기능 배치**: DB 전체 복구, 채팅방 복구(비파괴적)
- **채팅방 복구 기능 신규**: 파일 디렉터리에 있지만 DB에 없는 채팅방만 추가
- **URL 탭 동기화/복구 버튼 유지**: 채팅방별 기능이므로 URL 탭에 배치
- **FileStorage.get_all_rooms()**: data/url/ 디렉터리도 스캔하도록 확장
- **도움말 정보**: 버전 2.3.1, 제작자 민연홍, GitHub 링크 추가

### v2.3.0
- **비모달 요약 프로그레스**: `SummaryProgressDialog` (모달) → `SummaryProgressWidget` (상태바 내장)
- **closeEvent 추가**: 요약 진행 중 앱 종료 시 확인 → worker.cancel() + wait(5000)
- **대시보드 카드 컴팩트화**: 아이콘+제목+값 한 줄, 서브텍스트에 대화 기간/요약 진행률
- **DashboardCard.update_card()**: findChild 대신 직접 참조로 값 업데이트
- **DetachedInstanceError 수정**: `sessionmaker(expire_on_commit=False)` 추가
- **SummaryProgressWidget CSS**: 카카오 스타일 (#FFF8E1, #FEE500)

### v2.2.3
- 채팅방 삭제 기능을 ChatRoomWidget ✕ 버튼에서 파일 메뉴로 이동
- CreateRoomDialog에서 Enter 키로 즉시 생성 가능하도록 수정
- 요약 헤더 중복 제거: `chat_processor`의 헤더/푸터 제거, `file_storage`에서만 헤더 추가
- CreateRoomDialog placeholder에서 개인정보(고객명) 제거
- LLM read timeout 300초 → 600초로 증가

### v2.2.2
- LLM 요약 생성 후 DB에도 저장 (파일만 저장되던 버그 수정)
- RecoveryWorker date 타입 버그 수정 (문자열 → date 객체)
- RecoveryWorker 요약 내용 500자 잘림 → 전체 저장으로 변경
- `database.py`에 `delete_summary()` 메서드 추가

### v2.2.1
- 요약 필요 날짜 판단 로직 버그 수정: mtime 비교 → 요약 파일 존재 여부 확인

### v2.2.0
- URL 정보 탭 고도화 (3개 섹션: 최근 3일, 최근 1주, 전체)
- URL 저장소 리팩터링 (data/url/<채팅방>/ 디렉터리)
- URL 정규화 및 중복 제거 강화
- URL DB 테이블 추가 (urls)
- 동기화/복구 버튼
- 채팅방 목록 메시지 개수 기준 정렬
- 파일 업로드 기본 디렉터리 설정 (upload/)
- CLAUDE.md 추가

### v2.1.0
- URL 정보 탭 추가
- 달력 날짜 선택 기능
- 상태바 개선

### v2.0.0
- **PySide6 GUI 애플리케이션** 전환
- SQLite 데이터베이스 도입
- 파일 기반 저장소 (백업/복구)
- 탭 인터페이스
- 스마트 요약 생성
- LLM 응답 완결성 검증
- 요약 진행 다이얼로그
- `.env.local` 지원
- CLI 스크립트 분리 (src/manual/)

### v1.3.0
- 2일 전(엇그제)부터 오늘까지 요약 기능 추가 (`full_2days`, `simple_2days`)
- 간결 요약(단답형/음슴체) 모드 확대 (전체 날짜/2일치)
- 타임스탬프 기반의 정확한 메시지 카운팅 로직 개선

### v1.2.0
- 로그 시스템 고도화 (`logs/` 디렉터리, 파일 로깅)
- 에러 처리 개선 (리포트 오염 방지)
- MiniMax, Perplexity, GLM 연동 안정화
- 대용량 데이터 일괄 처리 검증 (~3,800 msgs/day 처리 확인)

### v1.1.0
- 다중 LLM 지원 (GLM, ChatGPT, MiniMax, Perplexity)
- `--llm` CLI 옵션 추가
- 대화형 LLM 선택 모드

### v1.0.0
- 초기 릴리즈
- 날짜별 대화 요약 기능
- URL 추출 기능
- CLI 인터페이스
