# 💬 카카오톡 대화 분석기 (KakaoTalk Chat Summarizer)

> **v2.9.9** | 최종 업데이트: 2026-07-05

카카오톡 대화 내보내기 파일을 AI(LLM)를 활용하여 날짜별로 **상세 분석 HTML**을 생성하는 **데스크톱 GUI 애플리케이션**입니다.

## ✨ 주요 기능

- 🖥️ **데스크톱 GUI**: PySide6 기반 네이티브 앱 (카카오톡 스타일 UI)
- 🔍 **상세 분석 HTML**: 토픽별 심층 분석 + URL 모음 + 감정 분석을 다크 테마 HTML로 생성
- 🤖 **다중 LLM 지원**: GLM, OpenAI, MiniMax, Perplexity, Grok, OpenRouter, Kilo, **MiMo**, Ollama
- 🌐 **전체 채팅방 일괄 처리**: 모든 채팅방 상세 분석/URL 동기화를 한 번에 수행
- 🔗 **URL 자동 추출**: 상세 분석 HTML에서 공유된 링크를 별도 탭에서 확인
- 📊 **대시보드**: 채팅방 통계 확인
- 💾 **수동/자동 백업**: 파일 기반 저장 + 타임스탬프 전체 백업 (Ctrl+B)
- 🔄 **스마트 무효화**: 메시지 내용 해시 비교로 실제 변경된 날짜만 재생성
- 🛡️ **스레드 안전**: 백그라운드 워커별 독립 DB 인스턴스

---

## 🖥️ 스크린샷

```
┌─────────────────────────────────────────────────────────────────┐
│  🗨️ 카카오톡 대화 분석기                                        │
├───────────────┬─────────────────────────────────────────────────┤
│  채팅방 목록  │  📊 대시보드 | 📅 날짜별 요약 | 🔗 URL | 🔧 기타 │
│  ───────────  │  ─────────────────────────────────────────────  │
│  📁 개발팀   │  💬 메시지    👥 참여자    📝 요약              │
│  📁 스터디방  │   1,234        15         30                   │
│               │  ─────────────────────────────────────────────  │
│  [➕ 채팅방]  │  📅 최근 요약                                   │
│  [📤 업로드]  │  2026-02-01: 새 프로젝트 킥오프...              │
│               │  2026-01-31: 기술 스택 논의...                  │
├───────────────┴─────────────────────────────────────────────────┤
│  ✅ 준비                                             (15:30:25) │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🤖 지원 LLM

| LLM | 키 | 환경변수 | 모델 | 비고 |
|-----|-----|----------|------|------|
| MiniMax | `minimax` | `MINIMAX_API_KEY` | MiniMax-M3 | 무제한 입력 / 최대 32,768출력 (**기본, 권장**, 고용량 200k) |
| Z.AI GLM | `glm` | `ZAI_API_KEY` | glm-5.2 | 입력 1.45M chars / 최대 32,768출력 (1M context) |
| OpenAI | `chatgpt` | `OPENAI_API_KEY` | gpt-4o-mini | 무제한 입력 / 최대 16,000출력 (⚠️ Rate Limit) |
| Perplexity | `perplexity` | `PERPLEXITY_API_KEY` | sonar | 무제한 입력 / 최대 16,000출력 |
| DeepSeek(OR) | `qwen-or` | `OPENROUTER_API_KEY` | deepseek-chat | ⚠️ **최대 4만자 입력** / 8,000출력 제한 |
| DeepSeek(Kilo)| `qwen-kilo` | `KILO_API_KEY` | deepseek-chat | ⚠️ **최대 4만자 입력** / 8,000출력 제한 |

> **💡 LLM 모델 컨텍스트 제약 사항**
> 대화량이 방대할 경우, **GLM-5.2(1M)**·**MiniMax-M3(512K~1M)**·**MiMo(1M)** 등 장문 컨텍스트 모델 사용을 권장합니다. OpenRouter/Kilo 기본 모델(grok-4.1-fast)은 2M context이며 앱에서 입력 자르기를 하지 않습니다(0).

---

## 📋 상세 분석 결과 구조

| 섹션 | 내용 |
|------|------|
| 🧠 핵심 제목 + 키워드 TOP 20 | 대화 핵심 흐름 요약 |
| 📝 토픽별 분석 (20~40개) | 발언자 인용 + 근거 + 시사점 |
| 📊 감정/온도 분석 | 과열/성장/주의/패러다임 전환 신호 |
| 🎯 핵심 시사점 | 대화에서 얻을 수 있는 인사이트 |
| 🔗 공유된 URL 모음 | 내용/시사점/활용 구조 |

---

## 🚀 설치

### 1. 저장소 클론
```bash
git clone https://github.com/your-repo/kakao-chat-summary.git
cd kakao-chat-summary
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. API 키 설정

**방법 A — 설정 다이얼로그 (v2.9.8, 권장)**  
앱 실행 후 **도구 → 설정**에서 LLM 제공자를 선택하고 API 키를 입력한 뒤 확인합니다.  
`LLM_PROVIDER`와 API 키가 `.env.local`에 저장되며, 재시작 후에도 유지됩니다.  
키 입력란을 비운 채 확인하면 기존 `.env.local`의 키는 그대로 둡니다.

**방법 B — `.env.local` 직접 편집**  
`.env.local`은 **env.local.example**을 기준으로 만듭니다.  
앱을 처음 실행하면 `.env.local`이 없을 경우 `env.local.example`을 복사해 자동 생성됩니다.

(수동으로 만들려면: `cp env.local.example .env.local`)

`.env.local` 예시:
```env
LLM_PROVIDER=minimax
MINIMAX_API_KEY=your-minimax-key
ZAI_API_KEY=your-glm-key
MIMO_API_KEY=your-mimo-key
```

---

## 📖 사용 방법

### 1. GUI 앱 실행

```bash
python src/app.py
```

### 2. 기본 워크플로우

1. **채팅방 만들기**: 좌측 하단 `➕ 채팅방 만들기` 클릭 (Enter 키로 즉시 생성)
2. **파일 업로드**: `📤 파일 업로드` 클릭 → 카카오톡 내보내기 .txt 또는 .csv 파일 선택
3. **상세 분석 생성**: 메뉴 → 도구 → `🔍 상세 분석 생성` (Ctrl+G)
4. **전체 채팅방 일괄 분석**: 메뉴 → 도구 → `🌐 전체 채팅방 상세 분석 생성` (Ctrl+Shift+G)
5. **전체 채팅방 URL 동기화**: 메뉴 → 도구 → `🌐 전체 채팅방 URL 동기화` (Ctrl+Shift+U)
6. **채팅방 삭제**: 채팅방 선택 후 메뉴 → 파일 → `채팅방 삭제...` 클릭
7. **결과 확인**: 탭에서 대시보드, 날짜별 요약, URL 정보 확인

### 3. 카카오톡 대화 내보내기

1. 카카오톡 앱에서 채팅방 진입
2. 우측 상단 메뉴 → **대화 내보내기**
3. **텍스트로 저장** 선택

---

## 📁 프로젝트 구조

```
kakao-chat-summary/
├── src/
│   ├── app.py                   # GUI 앱 진입점
│   ├── ui/
│   │   ├── main_window.py       # 메인 윈도우 (2900+ lines)
│   │   └── styles.py            # 카카오톡 스타일 테마
│   ├── db/
│   │   ├── database.py          # Database 클래스
│   │   └── models.py            # SQLAlchemy 모델 5개
│   ├── file_storage.py          # FileStorage 클래스
│   ├── full_config.py           # Config 클래스 (LLM 설정)
│   ├── parser.py                # KakaoLogParser 클래스
│   ├── detail_prompt.py         # 상세 분석 프롬프트 + HTML 템플릿 + LLM API
│   ├── url_extractor.py         # URL 추출 (마크다운 + HTML 파싱)
│   ├── import_to_db.py          # DB import 유틸
│   └── scheduler/
│       └── tasks.py             # SyncScheduler (프레임워크 구현, 앱 미연동)
│
├── data/
│   ├── db/                      # SQLite 데이터베이스
│   │   └── chat_history.db
│   ├── original/<채팅방>/       # 원본 대화 (일별 MD)
│   ├── detail_summary/<채팅방>/ # 상세 분석 HTML
│   └── url/<채팅방>/            # URL 목록 (3개 파일)
│
├── upload/                      # 파일 업로드 기본 디렉터리
├── logs/                        # 로그 파일
├── docs/                        # 문서
├── env.local.example            # 환경변수 예시
├── requirements.txt
├── CLAUDE.md                    # AI 에이전트 컨텍스트
└── README.md
```

---

## ⚙️ 환경 변수

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `ZAI_API_KEY` | LLM별 | Z.AI GLM API 키 |
| `ZAI_MODEL` | - | GLM 모델 ID (기본: `glm-5.2`, 1M 명시: `glm-5.2[1m]`) |
| `ZAI_MAX_TOKENS` | - | GLM 최대 출력 토큰 (기본: 32768, API 상한 131072) |
| `ZAI_MAX_INPUT_CHARS` | - | GLM 입력 문자 상한 (기본: 1450848, 1M context 기준) |
| `OPENAI_API_KEY` | LLM별 | OpenAI API 키 |
| `OPENAI_MAX_TOKENS` | - | gpt-4o-mini 최대 출력 (기본: 16384) |
| `OPENAI_MAX_INPUT_CHARS` | - | OpenAI 입력 문자 상한 (기본: 167424) |
| `MINIMAX_API_KEY` | LLM별 | MiniMax API 키 (기본 LLM) |
| `MINIMAX_MAX_TOKENS` | - | MiniMax 최대 출력 (기본: 32768) |
| `MINIMAX_MAX_INPUT_CHARS` | - | MiniMax 입력 문자 상한 (기본: 718848, 512K context 기준) |
| `PERPLEXITY_API_KEY` | LLM별 | Perplexity API 키 |
| `PERPLEXITY_MAX_TOKENS` | - | sonar 최대 출력 (기본: 16000) |
| `PERPLEXITY_MAX_INPUT_CHARS` | - | sonar 입력 문자 상한 (기본: 168000) |
| `XAI_API_KEY` | LLM별 | xAI Grok API 키 |
| `XAI_MAX_TOKENS` | - | Grok 최대 출력 (기본: 16000) |
| `XAI_MAX_INPUT_CHARS` | - | Grok 입력 상한 (기본: 0=무제한, 2M context) |
| `OPENROUTER_API_KEY` | LLM별 | OpenRouter API 키 |
| `OPENROUTER_MAX_TOKENS` | - | OpenRouter 최대 출력 (기본: 30000) |
| `OPENROUTER_MAX_INPUT_CHARS` | - | OpenRouter 입력 상한 (기본: 0) |
| `KILO_API_KEY` | LLM별 | Kilo AI Gateway API 키 |
| `KILO_MAX_TOKENS` | - | Kilo 최대 출력 (기본: 30000) |
| `KILO_MAX_INPUT_CHARS` | - | Kilo 입력 상한 (기본: 0) |
| `MIMO_API_KEY` | LLM별 | Xiaomi MiMo API 키 |
| `MIMO_MAX_TOKENS` | - | MiMo 최대 출력 (기본: 32768, API 상한 128K) |
| `MIMO_MAX_INPUT_CHARS` | - | MiMo 입력 문자 상한 (기본: 1450848, 1M context 기준) |
| `LLM_PROVIDER` | - | 기본 LLM (`glm`, `chatgpt`, `minimax`, `perplexity`, `grok`, `qwen-or`, `qwen-kilo`, `mimo`, `ollama`) |
| `API_TIMEOUT` | - | API read 타임아웃 초 (기본: 1200, connect: 60) |

---

## 📋 로깅 시스템

모든 로그는 `logs/` 디렉터리에 날짜별로 저장됩니다.

```
logs/summarizer_20260201.log
```

| 레벨 | 출력 대상 | 용도 |
|------|-----------|------|
| DEBUG/INFO | 파일만 | API 요청/응답, 처리 진행 상황 |
| WARNING | 파일 + 콘솔 | 경고 메시지 |
| ERROR | 파일 + 콘솔 | 에러 상세 |

---

## 📝 지원하는 카카오톡 형식

다양한 카카오톡 내보내기 형식을 자동 인식합니다:

```
# PC/Mac 형식
--------------- 2024년 1월 24일 수요일 ---------------
[홍길동] [오전 10:00] 안녕하세요

# 모바일 형식
2024년 1월 24일 수요일
홍길동 : 안녕하세요

# 심플 형식
2024. 1. 24.
```

---

## 🔒 데이터 보안

- `.env.local` 파일은 `.gitignore`에 포함되어 버전 관리에서 제외
- `data/`, `logs/`, `upload/` 디렉터리 내용은 Git에 포함되지 않음
- API 키는 환경 변수 또는 `.env.local`에만 저장 (평문; 클라우드 동기화 폴더에 두지 마세요)
- **LLM 전송**: 상세 분석 생성 시 해당 날짜의 대화 원문이 선택한 LLM API 서버로 전송됩니다. 민감한 대화는 **Ollama(로컬)** 등 신뢰할 수 있는 환경에서만 사용하세요
- **로그**: `logs/`에 채팅방명·날짜가 기록될 수 있습니다. 로그 파일도 커밋하지 마세요

---

## 📝 변경 이력

자세한 수정 내역은 [`CHANGELOG.md`](CHANGELOG.md)를 참고하세요.

### v2.9.9 (2026-07-05) - URL 탭 렌더링·설명 누적 수정
- 🐛 **URL 탭 들여쓰기**: `</nbsp;` 등 깨진 HTML 조각 제거 + 표시 시 이스케이프
- 🐛 **URL 설명 누적**: 같은 URL은 최신 날짜 설명만 유지 (`merge_urls_by_date`)
- 🔒 **README**: 데이터 보안 섹션 보강

### v2.9.8 (2026-07-04) - 설정 다이얼로그·MiMo·컨텍스트 상한 정비
- ⚙️ **설정 다이얼로그**: 도구 → 설정에서 LLM 제공자·API 키를 `.env.local`에 영구 저장 (재시작 후 유지)
- 🛡️ **빈 키 보호**: API 키 입력란을 비운 채 확인해도 기존 `.env.local` 키를 덮어쓰지 않음
- 🆕 **Xiaomi MiMo**: `mimo-v2.5-pro` 제공자 추가 (`MIMO_API_KEY`, API 호환 payload)
- 📏 **입력 컨텍스트 상한**: 공식 스펙 기준 `(context − max_tokens) × 1.5` chars로 제공자별 기본값 정비
- 🔄 **GLM-5.2**: `glm-4.5` → `glm-5.2` (1M context), `ZAI_MAX_INPUT_CHARS=1450848`

### v2.9.7 (2026-06-08) - Windows cp949 콘솔 인코딩 호환
- 🐛 **업로드 시 `UnicodeEncodeError: 'cp949' codec can't encode character 'ℹ'` 수정**: Windows 콘솔 기본 인코딩에서 ℹ️(U+2139) 등 이모지 `print()` 실패로 워커가 종료되던 버그
- 🔧 **`src/app.py`** 진입 시점에 `sys.stdout`/`sys.stderr`를 `utf-8 + errors="replace"`로 재설정. `reconfigure` 미지원·`None` 스트림은 안전 스킵
- 🍎 **크로스 플랫폼**: macOS/Linux는 이미 UTF-8이라 no-op, Windows에서만 실질 동작

### v2.9.6 (2026-05-25) - 성능 튜닝 및 UI 반응성 개선
- **지연 로딩(Lazy Loading) 적용**: 탭 전환(날짜별 요약, URL 정보) 시 필요한 데이터만 지연 로드하여 방 클릭 시 즉각적인 반응성 확보
- **UI 멈춤(Freezing) 해결**: 채팅방 전환 시 무거운 HTML 파일 및 JSON 데이터를 동기적으로 렌더링하던 병목 현상 제거
- **QTimer 이벤트 분산**: 채팅방 목록 클릭 시 즉시 하이라이트 효과가 적용되도록 이벤트 루프 분산 처리 추가

### v2.9.5 (2026-05-05) - 토큤·로그·예제 env 정비
- **MiniMax**: 기본 `max_tokens` 32768, `MINIMAX_MAX_TOKENS` 지원. 출력 잘림(`length`) 시 `<h2>` 없으면 부분 분석용 헤더 삽입으로 불필요 재시도 완화
- **GLM**: 기본 `ZAI_MAX_TOKENS` 8192 → **32768** (상세 HTML 잘림 완화)
- **로그**: `detail_prompt` API 로그에 `[채팅방 | 날짜]` 접두사 (`summarizer_*.log` / `info_*.log`)
- **env.local.example**: 템플릿 복구·`ZAI_MAX_*` 등 `full_config` 대응 주석 정리
- **UI**: `QTextBrowser` 선택 영역 스타일 (링크와 구분)

### v2.9.4 (2026-05-04) - 기본 LLM MiniMax 및 설정·LLM UI 정비
- **기본 LLM**: 앱 기본 제공자를 MiniMax(`MiniMax-M2.7`)로 설정 (`full_config.Config.DEFAULT_PROVIDER`, 상세 분석 API 기본 인자, 워커 기본값)
- **`LLM_PROVIDER` 처리**: `.env`에서 빈 값·미지원 값이면 기본 제공자로 정규화 (콤보박스가 첫 항목 Z.AI GLM으로 떨어지던 현상 방지)
- **상세 분석 LLM 선택**: 전체/단일/일괄·Ctrl+G 옵션에서 현재 provider가 목록에 없을 때 `DEFAULT_PROVIDER`로 폴백
- **설정 창 LLM**: 하드코딩 목록 제거 → `LLM_PROVIDERS`와 동일 목록 표시, 확인 시 `config.set_provider()`로 세션 내 반영
- **`env.local.example`**: 기본 LLM 안내 및 예시 `LLM_PROVIDER=minimax` 주석 정리
- **버전 표시 통일**: `QApplication` 버전·도움말 정보를 v2.9.4로 통일

### v2.9.3 (2026-04-24) - 채팅방 선택 캐시 최적화 및 UX 개선
- 🚀 **채팅방 데이터 캐시**: 같은 채팅방 재클릭 시 DB 쿼리 + 파일 I/O를 스킵하여 즉시 응답
- 🔧 **캐시 무효화 전략**: 상세 분석 생성, 파일 업로드, 채팅방 삭제/복구 시에만 캐시 무효화
- 🎨 **채팅방 선택 하이라이트**: 선택된 채팅방에 카카오 노랑 배경 + 왼쪽 보더 유지하여 현재 선택 상태를 명확히 표시
- 🔧 대시보드 전환 체감 속도 대폭 개선

### v2.9.0 (2026-04-13) - 기본 요약 제거, 상세 분석 전용화
- **BREAKING**: 기본 요약(마크다운) 파이프라인 완전 제거 — 상세 분석(HTML)이 유일한 요약 경로
- 🗑️ `llm_client.py`, `chat_processor.py`, `src/manual/` CLI 스크립트, `SyncWorker`, 기본 요약 Workers/Dialogs 제거
- 🆕 **상세 분석 옵션 다이얼로그** (Ctrl+G): pending/오늘/어제~오늘/전체 범위 + LLM 선택
- 🔧 URL 추출을 마크다운 → HTML 파싱으로 전환 (`extract_urls_from_html`)
- 🔧 전체 채팅방 상세 분석에서 DB + 파일 저장소 채팅방 통합
- 🔧 대시보드 방 선택 속도 개선 (파일 I/O 제거)
- 📦 `data/summary/` 기존 데이터 보존 (삭제 안 함)

### v2.8.5 (2026-04-12) - 백그라운드 트레이 연동 및 한글/토큰 한계 대응
- **시스템 트레이(상태표시줄) 확장**: 앱을 닫아도 백그라운드 트레이를 통해 상태 유지 기능을 정식 지원합니다.
- **문자 인코딩 및 구동 최적화**: 윈도우 PowerShell 한글 깨짐 및 `pythonw` 숨김 창 문제를 완전히 수정했습니다.
- **Ollama 환경의 Context Overflow 차단**: `max_input_chars` 및 `max_tokens` `.env.local` 로드 제어를 지원합니다.

### v2.8.4 (2026-04-09) - DeepSeek 허용치 오버플로우 방지 및 정책 개선
- 🔧 **DeepSeek 컨텍스트 오버플로우 방지**: `qwen-or` 및 `qwen-kilo` 제공자에 대해 입력 문자열을 40,000자로 제약 및 출력 토큰을 8000으로 제한하여 내부 API 400 에러 사전 방지.
- 🔧 **상세 분석 토픽 추출량 상향**: 상세 분석 프롬프트의 토픽 추출 개수 제약을 최소 20개 이상(최대 수십 개) 생산해내도록 변경하여 훨씬 밀도 높은 데이터 조회를 도모.
- 🐛 **자동 동기화 버그 픽스**: `main_window.py` - 자동 동기화 기능에서 발생하는 Logger NameError 해결.

### v2.8.3 (2026-04-08) - 상세 분석 앱 렌더링 보정
- `QTextBrowser`에서 일반 브라우저보다 엄격하게 처리되는 잘못된 닫힘 태그(`</hp>` 등)를 앱 표시 시 보정
- 상세 분석 HTML은 브라우저용 원본 파일을 유지하고, 앱 내부 렌더링에서만 임시 보정 적용

### v2.8.1 (2026-04-03) - 프롬프트 제약 및 무효화 로직 개편
- 🔧 **LLM 시스템 프롬프트 언어 제약 추가**: 중국어, 일본어, 아랍어 등 원치 않는 외국어 출력을 방지하고 한글 설명 및 영어 용어만 사용하도록 규칙 강화
- 🔧 **상세 분석 무효화 로직 수정**: 원본 내용 변경에 따른 무효화 수행(메시지 10개 이상) 시 기본 요약 외에도 상세 분석 HTML(.html) 파일이 함께 무효화(백업)되도록 파일 저장소 로직 수정

### v2.8.0 (2026-03-29) - 상세 분석 HTML 생성
- 🆕 **상세 분석 HTML 생성**: 토픽별 심층 분석 + URL 모음 + 감정/온도 분석을 다크 테마 HTML로 생성
  - `detail_prompt.py`: 전용 프롬프트 + HTML 템플릿 + LLM API 호출
  - 날짜 탭 단일 생성, 일괄 생성, 전체 채팅방 상세 분석 (Ctrl+Shift+D)
- 🆕 **날짜별 요약 탭 토글 뷰**: [📝 기본 요약] / [🔍 상세 분석] 전환, 뷰별 액션 버튼
- 🆕 **LLM 요약 시 상세 분석 연동**: 체크박스로 기본 요약 후 자동 상세 생성
- 🔧 **LLM 추론 내용 제거**: `<think>` 태그 및 본문 이전 추론 텍스트 자동 제거
- 🔧 **LLM 모델 업데이트**: GLM glm-5-turbo, MiniMax M2.5
- 🔧 **백업/복원에 상세 분석 포함**: detail_summary/ 디렉터리

### v2.7.0 (2026-03-28) - 전체 채팅방 일괄 처리
- 🆕 **전체 채팅방 LLM 요약 생성**: 도구 메뉴에서 모든 채팅방의 요약을 한 번에 생성 (Ctrl+Shift+G)
  - `AllRoomsSummaryOptionsDialog`: 채팅방별 현황 표시, LLM/범위 선택
  - `AllRoomsSummaryWorker`: 모든 채팅방을 순회하며 날짜별 요약 생성
  - 상태바에 실시간 진행 표시 + 취소 지원
- 🆕 **전체 채팅방 URL 동기화**: 도구 메뉴에서 모든 채팅방의 URL을 한 번에 수집 (Ctrl+Shift+U)
  - `AllRoomsUrlSyncWorker`: 모든 채팅방의 요약에서 URL 추출 → DB/파일(3개) 저장
  - 채팅방별 결과 요약 다이얼로그 표시

### v2.5.1 (2026-02-26) - 요약 무효화 정확도 개선
- 🔧 **메시지 해시 기반 요약 무효화**: 파일 크기 대신 메시지 내용 MD5 해시로 변경 여부 판단
  - 동일 메시지 재업로드 시 저장 시각 변동으로 인한 불필요한 요약 재수행 방지
  - `get_original_content_hash()`, `invalidate_summary_if_content_changed()` 추가
  - 기존 `invalidate_summary_if_file_changed()` deprecated 처리

### v2.5.0 (2026-02-04) - 백업/복원 기능 강화
- 🆕 **채팅방 백업**: 선택된 채팅방만 별도 백업 (타임스탬프 디렉터리)
- 🆕 **백업에서 복원**: 백업 목록에서 선택하여 전체 또는 개별 채팅방 복원
- 🆕 **메뉴 재구성**: 백업/복원 vs 재구축/DB추가 명확히 분리

### v2.4.0 (2026-02-04) - 안정성 및 스레드 안전성 개선
- 🔧 **[Critical Fix] DB 손상 문제 해결**: 워커 스레드별 독립 `Database` 인스턴스 사용으로 SQLite 동시 접근 충돌 방지
- 🔧 **파일 크기 기반 요약 무효화**: 재업로드 시 실제 변경된 날짜만 요약 갱신
- 🔧 **전체 백업 기능**: 도구 메뉴에서 DB + 파일 전체를 타임스탬프 디렉터리에 백업 (Ctrl+B)
- 🔧 **Data Loss Prevention**: 파일 저장 시 데이터 감소 감지 → 저장 건너뛰기
- 🔧 **Summary Backup**: 요약 삭제 시 `.bak` 파일로 백업
- 🔧 **API Retry**: LLM API 500 에러 및 네트워크 오류 시 최대 3회 재시도

### v2.3.1 (2026-02-02)
- 기타 기능 탭 추가
- 도구 메뉴에 복구 기능 배치
- 채팅방 복구 기능 신규

### v2.3.0 (2026-02-01)
- 비모달 요약 프로그레스 (상태바 내장)
- 대시보드 카드 컴팩트화

---

## 📄 라이선스

MIT License
