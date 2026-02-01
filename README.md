# 📱 KakaoTalk Chat Summarizer

> **v2.2.3** | 최종 업데이트: 2026-02-01

카카오톡 대화 내보내기 파일을 AI(LLM)를 활용하여 날짜별로 자동 요약하는 **데스크톱 GUI 애플리케이션**입니다.

## ✨ 주요 기능

- 🖥️ **데스크톱 GUI**: PySide6 기반 네이티브 앱 (카카오톡 스타일 UI)
- 📅 **날짜별 요약**: 대화를 날짜별로 파싱하여 각각 요약 생성
- 🤖 **다중 LLM 지원**: GLM, OpenAI, MiniMax, Perplexity 선택 가능
- 🔗 **URL 자동 추출**: 요약본에서 공유된 링크를 별도 탭에서 확인 (최근 3일/1주/전체)
- 📊 **대시보드**: 채팅방 통계 및 최근 요약 확인
- 💾 **자동 백업**: 파일 기반 저장으로 DB 손상 시 복구 가능
- 🔄 **스마트 요약**: 새 날짜 또는 업데이트된 날짜만 요약

---

## 🖥️ 스크린샷

```
┌─────────────────────────────────────────────────────────────────┐
│  🗨️ 카카오톡 대화 분석기                                        │
├───────────────┬─────────────────────────────────────────────────┤
│  채팅방 목록  │  📊 대시보드 | 📅 날짜별 요약 | 🔗 URL 정보     │
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
| Z.AI GLM | `glm` | `ZAI_API_KEY` | glm-4.7 | 기본, 권장 |
| OpenAI | `chatgpt` | `OPENAI_API_KEY` | gpt-4o-mini | ⚠️ Rate Limit |
| MiniMax | `minimax` | `MINIMAX_API_KEY` | MiniMax-M2.1 | 고속 처리 |
| Perplexity | `perplexity` | `PERPLEXITY_API_KEY` | sonar | |

---

## 📋 요약 결과 섹션

| 섹션 | 내용 |
|------|------|
| 🌟 3줄 요약 | 핵심 내용을 3문장으로 압축 |
| ❓ Q&A | 질문과 답변 정리 |
| 💬 주요 토픽 | 논의된 주제와 결론 |
| 💡 꿀팁 | 추천된 도구, 라이브러리, 팁 |
| 🔗 링크/URL | 공유된 중요 링크 |
| 📅 일정/공지 | 일정 및 공지사항 |

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
`.env.local`은 **env.local.example**을 기준으로 만듭니다.  
앱을 처음 실행하면 `.env.local`이 없을 경우 `env.local.example`을 복사해 자동 생성됩니다.  
생성된 `.env.local`을 열어 사용할 LLM의 API 키만 입력하면 됩니다.

(수동으로 만들려면: `cp env.local.example .env.local`)

`.env.local` 예시:
```env
# 사용할 LLM의 API 키만 설정하면 됩니다
ZAI_API_KEY=your-glm-key
OPENAI_API_KEY=your-openai-key
MINIMAX_API_KEY=your-minimax-key
PERPLEXITY_API_KEY=your-perplexity-key
```

---

## 📖 사용 방법

### 1. GUI 앱 실행

```bash
python src/app.py
```

### 2. 기본 워크플로우

1. **채팅방 만들기**: 좌측 하단 `➕ 채팅방 만들기` 클릭 (Enter 키로 즉시 생성)
2. **파일 업로드**: `📤 파일 업로드` 클릭 → 카카오톡 내보내기 .txt 선택
3. **요약 생성**: 메뉴 → 도구 → `LLM 요약 생성` 클릭
4. **채팅방 삭제**: 채팅방 선택 후 메뉴 → 파일 → `채팅방 삭제...` 클릭
5. **결과 확인**: 탭에서 대시보드, 날짜별 요약, URL 정보 확인

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
│   │   ├── main_window.py       # 메인 윈도우 (2600+ lines)
│   │   └── styles.py            # 카카오톡 스타일 테마
│   ├── db/
│   │   ├── database.py          # Database 클래스
│   │   └── models.py            # SQLAlchemy 모델 5개
│   ├── file_storage.py          # FileStorage 클래스
│   ├── full_config.py           # Config 클래스 (LLM 설정)
│   ├── parser.py                # KakaoLogParser 클래스
│   ├── llm_client.py            # LLMClient 클래스
│   ├── chat_processor.py        # ChatProcessor 클래스
│   ├── url_extractor.py         # URL 추출 함수
│   ├── import_to_db.py          # DB import 유틸
│   ├── scheduler/
│   │   └── tasks.py             # SyncScheduler (프레임워크 구현, 앱 미연동)
│   └── manual/                  # CLI 스크립트 (수동 요약용, 레거시)
│
├── data/
│   ├── db/                      # SQLite 데이터베이스
│   │   └── chat_history.db
│   ├── original/<채팅방>/       # 원본 대화 (일별 MD)
│   ├── summary/<채팅방>/        # LLM 요약 (일별 MD)
│   └── url/<채팅방>/            # URL 목록 (3개 파일)
│
├── output/                      # CLI 스크립트 (src/manual/) 출력 디렉터리
├── upload/                      # 파일 업로드 기본 디렉터리
├── logs/                        # 로그 파일
├── docs/                        # 문서
├── env.local.example            # 환경변수 예시
├── requirements.txt
├── CLAUDE.md                    # AI 에이전트 컨텍스트
└── README.md
```

---

## 🔧 CLI 도구 (수동 요약용, 레거시)

`src/manual/` 디렉터리의 CLI 스크립트는 GUI 앱과 별개로 동작합니다.
DB/FileStorage를 사용하지 않으며, 결과는 `output/` 디렉터리에 저장됩니다.

### Full 스크립트 (상세 요약)
src/ 모듈을 재사용합니다 (`full_config`, `parser`, `chat_processor`, `url_extractor`).

```bash
python src/manual/full_date_summary.py data/채팅방.txt
python src/manual/full_yesterday_summary.py --llm minimax data/
python src/manual/full_2days_summary.py data/채팅방.txt
python src/manual/full_today_summary.py --llm glm data/
```

### Simple 스크립트 (간결 요약, 음슴체)
자체 내장 구현으로 외부 모듈 의존 없이 단독 실행 가능합니다.

```bash
python src/manual/simple_date_summary.py data/채팅방.txt
python src/manual/simple_today_summary.py --llm glm data/
```

---

## ⚙️ 환경 변수

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `ZAI_API_KEY` | LLM별 | Z.AI GLM API 키 |
| `OPENAI_API_KEY` | LLM별 | OpenAI API 키 |
| `MINIMAX_API_KEY` | LLM별 | MiniMax API 키 |
| `PERPLEXITY_API_KEY` | LLM별 | Perplexity API 키 |
| `LLM_PROVIDER` | - | 기본 LLM 제공자 (기본: glm) |
| `API_TIMEOUT` | - | API read 타임아웃 초 (기본: 600, connect: 60) |

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
- `data/` 디렉터리 내용은 Git에 포함되지 않음
- API 키는 환경 변수 또는 `.env.local`에만 저장

---

## 📄 라이선스

MIT License
