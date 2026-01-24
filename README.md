# 📱 KakaoTalk Chat Summarizer

카카오톡 대화 내보내기 파일을 AI(LLM)를 활용하여 날짜별로 자동 요약하는 CLI 도구입니다.

## ✨ 주요 기능

- 📅 **날짜별 요약**: 대화를 날짜별로 파싱하여 각각 요약 생성
- 🤖 **다중 LLM 지원**: GLM, MiniMax Coding Plan, Perplexity 선택 가능
- 🔗 **URL 자동 추출**: 요약본에서 공유된 링크를 별도 파일로 추출
- 📝 **Markdown 리포트**: 깔끔한 Markdown 형식의 통합 리포트 생성
- ⏰ **어제 날짜 요약**: 어제 날짜 대화만 빠르게 요약하는 별도 스크립트

## 🤖 지원 LLM

| LLM | 키 | 환경변수 | 모델 | API 호환성 | 비고 |
|-----|-----|----------|------|------------|------|
| Z.AI GLM | `glm` | `ZAI_API_KEY` | glm-4.7 | OpenAI | 기본, 권장 |
| MiniMax Coding Plan | `minimax` | `MINIMAX_API_KEY` | MiniMax-M2.1 | OpenAI | 고속 처리 |
| Perplexity | `perplexity` | `PERPLEXITY_API_KEY` | sonar | OpenAI | |

> 💡 **ChatGPT** (`chatgpt`, `OPENAI_API_KEY`, gpt-4o-mini)도 지원하지만, **Rate Limit 3 RPM** 제한으로 대량 처리에는 부적합합니다.

> ℹ️ **API 호환성**: 모든 LLM 제공자는 **OpenAI 호환 API** 형식(`/chat/completions`)을 사용합니다. Anthropic(Claude) 형식은 현재 지원하지 않습니다.

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

### 3. API 키 설정 (선택)
```bash
# 사용할 LLM에 따라 해당 환경변수 설정
export ZAI_API_KEY="your-glm-key"
export MINIMAX_API_KEY="your-minimax-key"
export PERPLEXITY_API_KEY="your-perplexity-key"

# 또는 실행 시 직접 입력 가능
```

---

## 📖 사용 방법

### 1. 카카오톡 대화 내보내기

1. 카카오톡 앱에서 채팅방 진입
2. 우측 상단 메뉴 → **대화 내보내기**
3. **텍스트로 저장** 선택
4. 저장된 `.txt` 파일을 `data/` 폴더에 복사

### 2. 전체 날짜 요약 (date_summarizer.py)

모든 날짜의 대화를 순차적으로 요약합니다. **단일 파일 또는 디렉터리 지원.**

```bash
# 기본 LLM (GLM) 사용
python src/date_summarizer.py data/채팅방.txt

# LLM 지정 (Perplexity 사용)
python src/date_summarizer.py --llm perplexity data/채팅방.txt

# MiniMax Coding Plan 사용
python src/date_summarizer.py --llm minimax data/채팅방.txt

# 디렉터리 일괄 처리
python src/date_summarizer.py --llm glm data/

# 대화형 모드 (LLM 선택 + 파일 선택)
python src/date_summarizer.py
```

**출력 파일**:
- `채팅방_summaries.md` - 날짜별 통합 요약 리포트
- `채팅방_url.txt` - 추출된 URL 목록

### 3. 어제 날짜만 요약 (yesterday_summarizer.py)

어제 날짜의 대화만 빠르게 요약합니다.

```bash
# 기본 LLM 사용
python src/yesterday_summarizer.py data/채팅방.txt

# LLM 지정 (Perplexity 사용)
python src/yesterday_summarizer.py --llm perplexity data/채팅방.txt

# 디렉터리 일괄 처리 (MiniMax 사용)
python src/yesterday_summarizer.py --llm minimax data/

# 대화형 모드
python src/yesterday_summarizer.py
```

**출력 파일**:
- `채팅방_yesterday_summary.md` - 어제 날짜 요약
- `채팅방_yesterday_url.txt` - 어제 날짜 URL 목록

### 4. URL만 추출 (url_extractor.py)

이미 생성된 요약 파일에서 URL을 추출합니다.

```bash
python src/url_extractor.py data/채팅방_summaries.md
```

---

## 📁 프로젝트 구조

```
kakao-chat-summary/
├── src/
│   ├── config.py              # 설정 관리 (다중 LLM 지원)
│   ├── parser.py              # 카카오톡 텍스트 파싱
│   ├── llm_client.py          # 통합 LLM API 클라이언트
│   ├── chat_processor.py      # 채팅 요약 처리
│   ├── date_summarizer.py     # 전체 날짜 요약 (메인)
│   ├── yesterday_summarizer.py # 어제 날짜 요약
│   └── url_extractor.py       # URL 추출
│
├── data/                      # 입력/출력 파일 저장
├── logs/                      # 로그 파일 저장
├── docs/                      # 문서
├── requirements.txt
└── README.md
```

---

## ⚙️ 환경 변수

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `ZAI_API_KEY` | LLM별 | Z.AI GLM API 키 |
| `MINIMAX_API_KEY` | LLM별 | MiniMax Coding Plan API 키 |
| `PERPLEXITY_API_KEY` | LLM별 | Perplexity API 키 |
| `LLM_PROVIDER` | - | 기본 LLM 제공자 (기본: glm) |
| `API_TIMEOUT` | - | API 타임아웃 초 (기본: 180) |

---

## 📋 로깅 시스템

모든 로그는 `logs/` 디렉터리에 날짜별로 저장됩니다.

```
logs/summarizer_20260124.log
```

| 레벨 | 출력 대상 | 용도 |
|------|-----------|------|
| DEBUG/INFO | 파일만 | API 요청/응답, 처리 진행 상황 |
| WARNING | 파일 + 콘솔 | 경고 메시지 |
| ERROR | 파일 + 콘솔 | 에러 상세 (콘솔은 축약) |

> ⚠️ **핵심 원칙**: LLM API 에러 메시지는 `logs/` 디렉터리에만 기록되며, 요약 결과 파일(`*_summaries.md`)에는 오염되지 않습니다.

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

## 📄 라이선스

MIT License
