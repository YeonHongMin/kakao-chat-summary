# 📱 KakaoTalk Chat Summarizer

> **v2.5.1** | 최종 업데이트: 2026-02-10

카카오톡 대화 내보내기 파일을 AI(LLM)를 활용하여 날짜별로 자동 요약하는 **데스크톱 GUI 애플리케이션**입니다.

## ✨ 주요 기능

- 🖥️ **데스크톱 GUI**: PySide6 기반 네이티브 앱 (카카오톡 스타일 UI)
- 📅 **날짜별 요약**: 대화를 날짜별로 파싱하여 각각 요약 생성
- 🤖 **다중 LLM 지원**: GLM, OpenAI, MiniMax, Perplexity 선택 가능
- 🔗 **URL 자동 추출**: 요약본에서 공유된 링크를 별도 탭에서 확인 (최근 3일/1주/전체)
- 📊 **대시보드**: 채팅방 통계 및 최근 요약 확인
- 💾 **수동/자동 백업**: 파일 기반 저장 + 타임스탬프 전체 백업 (Ctrl+B)
- 🔄 **스마트 요약**: 파일 크기 변경된 날짜만 요약 재생성
- 🛡️ **스레드 안전**: 백그라운드 워커별 독립 DB 인스턴스 (v2.4.0)

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
| Z.AI GLM | `glm` | `ZAI_API_KEY` | glm-4.7 | 기본, 권장 |
| OpenAI | `chatgpt` | `OPENAI_API_KEY` | gpt-4o-mini | ⚠️ Rate Limit |
| MiniMax | `minimax` | `MINIMAX_API_KEY` | MiniMax-M2.1 | 고속 처리 |
| Perplexity | `perplexity` | `PERPLEXITY_API_KEY` | sonar | |

---

## 📋 요약 결과 섹션

| 섹션 | 내용 | 배치 기준 |
|------|------|-----------|
| 🌟 3줄 요약 | 핵심 내용을 3문장으로 압축 | - |
| ❓ Q&A | 명시적 질문(?)과 답변만 | 물음표로 직접 질문한 것만 |
| 💬 주요 토픽 | 논의된 주제와 결론 | Q&A에 포함되지 않은 논의만 |
| 💡 꿀팁 | 추천된 도구, 라이브러리, 팁 | 구체적 도구명/명령어가 있는 것만 |
| 🔗 링크/URL | 공유된 중요 링크 | URL 추출 스크립트 연동 |
| 📅 일정/공지 | 일정 및 공지사항 | 해당 없으면 "없음" 표시 |

> **v2.5.1 개선**: 섹션 간 중복 방지 규칙 적용. 하나의 내용은 가장 적합한 섹션 하나에만 기록되며, 모든 질문/토픽/팁/링크를 빠짐없이 포함합니다.

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
│   │   ├── main_window.py       # 메인 윈도우 (2900+ lines)
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

## 📝 변경 이력

### v2.5.1 (2026-02-10) - 요약 프롬프트 품질 개선
- 🔧 **섹션 간 중복 방지**: Q&A/토픽/꿀팁 각 섹션의 포함·제외 기준 명확화
- 🔧 **빠짐없는 요약**: 모든 질문, 토픽, 팁, 링크를 생략 없이 기록하도록 지시 강화
- 🔧 **Q&A 통합 규칙**: 같은 주제 질문 통합, 미해결 질문 "(미해결)" 표시
- 🔧 **적용 범위**: full_config.py + simple 스크립트 4개 모두 동일 적용

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
