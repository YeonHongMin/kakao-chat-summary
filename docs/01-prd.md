# 01. Product Requirements Document (PRD)

## 1. 제품 개요

### 1.1 제품명
**KakaoTalk Chat Summarizer** (카카오톡 대화 요약기)

### 1.2 목적
카카오톡에서 내보낸 대화 텍스트 파일을 분석하여, 다양한 LLM을 활용해 날짜별로 체계적인 요약 리포트를 자동 생성하는 **데스크톱 GUI 애플리케이션**입니다.

### 1.3 대상 사용자
- 오픈채팅방 관리자 및 참여자
- 스터디/커뮤니티 운영자
- 대화 내용을 정리하고 아카이빙하려는 사용자

---

## 2. 핵심 기능

### 2.1 데스크톱 GUI 애플리케이션
- **PySide6 기반** 네이티브 데스크톱 앱
- **카카오톡 스타일** UI (노란색 테마)
- **탭 인터페이스**: 대시보드, 날짜별 요약, URL 정보
- **실시간 진행률 표시** 및 취소 기능

### 2.2 다중 LLM 지원
| Provider | 모델 | 환경변수 | 비고 |
|----------|------|----------|------|
| Z.AI GLM | glm-4.7 | `ZAI_API_KEY` | 기본, 권장 |
| OpenAI | gpt-4o-mini | `OPENAI_API_KEY` | ⚠️ Rate Limit |
| MiniMax | MiniMax-M2.1 | `MINIMAX_API_KEY` | 고속 처리 |
| Perplexity | sonar | `PERPLEXITY_API_KEY` | |

> 📌 **API 호환성**: 모든 LLM 제공자는 **OpenAI 호환 API** 형식을 사용합니다.

### 2.3 채팅방 관리
- **채팅방 생성** (Enter 키로 즉시 생성 가능)
- **채팅방 삭제** (파일 메뉴 → 현재 선택된 채팅방 삭제, 확인 다이얼로그)
- **파일 업로드** (카카오톡 내보내기 .txt)
- **중복 메시지 자동 처리**
- **채팅방별 통계** (메시지 수, 참여자 수, 요약 수)

### 2.4 대화 파싱 (Parsing)
- 카카오톡 내보내기 텍스트 파일(.txt) 읽기
- 다양한 내보내기 형식 지원 (PC/Mac, 모바일, 심플 형식)
- 날짜별 메시지 그룹화

### 2.5 LLM 기반 요약 (Summarization)
- 구조화된 프롬프트 템플릿 사용
- 6개 섹션으로 체계적 정리:
  - 🌟 3줄 요약
  - ❓ Q&A 및 해결된 문제
  - 💬 주요 토픽 & 논의
  - 💡 꿀팁 및 도구 추천
  - 🔗 링크/URL
  - 📅 일정 및 공지
- **스마트 요약 생성**: 새 날짜 또는 업데이트된 날짜만 요약
- **LLM 응답 완결성 검증**: 불완전한 응답 저장 방지

### 2.6 URL 추출 (URL Extraction)
- 요약 결과에서 공유된 링크 자동 추출
- URL과 설명을 함께 표시
- URL 정규화 및 중복 제거 (백틱, 따옴표 등 특수문자 정리)
- 3개 섹션으로 분류 (최근 3일, 최근 1주, 전체)
- DB + 파일 이중 저장 (동기화/복구 가능)

### 2.7 데이터 복구
- **파일 기반 백업**: original/, summary/ 디렉터리에 일별 Markdown 저장
- **DB 복구 기능**: 파일에서 SQLite DB 재구축

---

## 3. 데이터 저장 구조

### 3.1 SQLite 데이터베이스
| 테이블 | 설명 |
|--------|------|
| `chat_rooms` | 채팅방 정보 |
| `messages` | 메시지 (날짜, 발신자, 내용) |
| `summaries` | 날짜별 요약 결과 |
| `urls` | 추출된 URL 목록 |
| `sync_logs` | 동기화 로그 |

### 3.2 파일 저장소
```
data/
├── original/<채팅방>/<채팅방>_YYYYMMDD_full.md     # 원본 대화
├── summary/<채팅방>/<채팅방>_YYYYMMDD_summary.md  # LLM 요약
└── url/<채팅방>/                                   # URL 목록
    ├── <채팅방>_urls_recent.md                    # 최근 3일
    ├── <채팅방>_urls_weekly.md                    # 최근 1주
    └── <채팅방>_urls_all.md                       # 전체
```

---

## 4. 기술 스택

| 구분 | 기술 |
|------|------|
| 언어 | Python 3.11+ |
| GUI | PySide6 (Qt for Python) |
| 데이터베이스 | SQLite + SQLAlchemy ORM |
| LLM API | GLM, OpenAI, MiniMax, Perplexity (OpenAI 호환) |
| HTTP 클라이언트 | requests |
| 환경 설정 | python-dotenv |
| 파일 처리 | pathlib |
| 로깅 | logging (logs/ 디렉터리에 날짜별 상세 기록) |

---

## 5. CLI 도구 (수동 요약용, 레거시)

`src/manual/` 디렉터리에 독립 실행 가능한 CLI 스크립트 제공. GUI 앱과 별개로 동작하며, DB/FileStorage를 사용하지 않고 `output/` 디렉터리에 직접 파일을 저장합니다.

### 5.1 Full 스크립트 (상세 요약)
src/ 모듈을 재사용합니다 (`full_config`, `parser`, `chat_processor`, `url_extractor`).

| 스크립트 | 설명 |
|----------|------|
| `full_today_summary.py` | 오늘 상세 요약 |
| `full_yesterday_summary.py` | 어제~오늘 상세 요약 |
| `full_2days_summary.py` | 엇그제~오늘 상세 요약 |
| `full_date_summary.py` | 전체 날짜 상세 요약 |

### 5.2 Simple 스크립트 (간결 요약, 음슴체)
자체 내장 구현(`SimpleConfig`, `SimpleParser`, `SimpleLLMClient`)으로 외부 모듈 의존 없이 단독 실행 가능합니다.

| 스크립트 | 설명 |
|----------|------|
| `simple_today_summary.py` | 오늘 간결 요약 |
| `simple_yesterday_summary.py` | 어제~오늘 간결 요약 |
| `simple_2days_summary.py` | 엇그제~오늘 간결 요약 |
| `simple_date_summary.py` | 전체 날짜 간결 요약 |

### 5.3 실행 방법
```bash
python src/manual/<스크립트>.py <파일 또는 디렉터리> [--llm <provider>]
```
