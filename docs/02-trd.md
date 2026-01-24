# 02. Technical Requirements Document (TRD)

## 1. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│              date_summarizer.py / yesterday_summarizer.py    │
│                      (메인 오케스트레이터)                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌────────────────┐  ┌──────────────────┐ │
│  │   parser.py  │  │ chat_processor │  │  url_extractor   │ │
│  │  (파싱 모듈) │  │   (요약 모듈)   │  │   (URL 추출)     │ │
│  └──────┬──────┘  └───────┬────────┘  └────────┬─────────┘ │
│         │                 │                     │           │
│         │         ┌───────┴────────┐           │           │
│         │         │  llm_client.py │           │           │
│         │         │ (통합 LLM API)  │           │           │
│         │         └───────┬────────┘           │           │
│         │                 │                     │           │
│         └─────────────────┼─────────────────────┘           │
│                           │                                 │
│                   ┌───────┴────────┐                       │
│                   │   config.py    │                       │
│                   │ (다중 LLM 설정) │                       │
│                   └────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 모듈 상세

### 2.1 config.py
**역할**: 전역 설정 및 다중 LLM 제공자 관리

**LLM 제공자 설정**:
| Provider | API URL | Model | 환경변수 | 비고 |
|----------|---------|-------|----------|------|
| glm | .../api/coding/paas/v4/chat/completions | glm-4.7 | ZAI_API_KEY | 기본, 권장 |
| minimax | .../v1/chat/completions | MiniMax-M2.1 | MINIMAX_API_KEY | 고속 |
| perplexity | .../chat/completions | sonar | PERPLEXITY_API_KEY | |
| chatgpt | .../v1/chat/completions | gpt-4o-mini | OPENAI_API_KEY | ⚠️ 3 RPM |

**주요 메서드**:
| 메서드 | 설명 |
|--------|------|
| `set_provider(provider)` | LLM 제공자 변경 |
| `get_provider_info()` | 현재 제공자 정보 반환 |
| `get_api_key(provider)` | 지정 제공자의 API 키 반환 |
| `set_api_key(key, provider)` | 런타임 API 키 설정 |

---

### 2.2 llm_client.py
**역할**: 통합 LLM API 클라이언트

**클래스**: `LLMClient`

모든 LLM 제공자는 OpenAI 호환 API 형식을 사용합니다.
- **Rate Limit**: ChatGPT의 경우 분당 3회 요청 제한을 준수하기 위해 요청 간 21초 대기 로직이 포함되어 있습니다.

| 메서드 | 반환 타입 | 설명 |
|--------|-----------|------|
| `summarize(text)` | `Dict[str, Any]` | 텍스트 요약 요청 |

**응답 구조**:
```python
# 성공
{"success": True, "content": "요약...", "usage": {...}}

# 실패
{"success": False, "error": "에러 메시지"}
```

---

### 2.3 parser.py
**역할**: 카카오톡 텍스트 파일 파싱

**클래스**: `KakaoLogParser`

**지원 형식**:
```
# PC/Mac: --------------- 2024년 1월 24일 ---------------
# 모바일: 2024년 1월 24일 수요일
# 심플: 2024. 1. 24.
```

---

### 2.4 chat_processor.py
**역할**: 채팅 텍스트 처리 및 포맷팅

**클래스**: `ChatProcessor(provider)`

| 메서드 | 설명 |
|--------|------|
| `process_summary(text)` | LLM으로 요약 후 Markdown 포맷팅 |

---

### 2.5 date_summarizer.py
**역할**: 날짜별 전체 요약 오케스트레이터

**CLI 옵션**:
```bash
python date_summarizer.py [--llm PROVIDER] <file_or_directory>
```

**클래스**:
- `DateSummarizer(filepath, provider)`: 단일 파일 처리
- `BatchProcessor(directory, provider)`: 디렉터리 일괄 처리

---

### 2.6 yesterday_summarizer.py
**역할**: 어제 날짜만 요약

**CLI 옵션**:
```bash
python yesterday_summarizer.py [--llm PROVIDER] <file_or_directory>
```

---

### 2.7 url_extractor.py
**역할**: URL 추출 및 저장

| 함수 | 설명 |
|------|------|
| `extract_urls_from_text(text)` | 텍스트에서 URL 추출 |
| `save_urls_to_file(dict, path)` | URL 목록 파일 저장 |

---

## 3. 데이터 흐름

```
[CLI 인자: --llm provider, file/directory]
       │
       ▼
┌──────────────────┐
│  config.py       │  ← LLM 제공자 설정
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  KakaoLogParser   │  ← 날짜별 메시지 그룹화
└────────┬─────────┘
         │
         ▼  (날짜별 반복)
┌──────────────────┐
│  ChatProcessor    │  ← LLMClient 호출
│  + LLMClient      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  DateSummarizer   │  ← 통합 리포트 생성
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  url_extractor    │  ← URL 추출
└────────┬─────────┘
         │
         ▼
[출력: _summaries.md, _url.txt]
```

---

## 4. 에러 처리

| 에러 유형 | 처리 방식 |
|-----------|-----------|
| 파일 없음 | 로그 에러 출력 후 종료 |
| API 키 없음 | 대화형 입력 요청 |
| 잘못된 LLM 제공자 | 사용 가능 목록 출력 후 종료 |
| API 타임아웃 | 에러 메시지 반환, 다음 날짜 계속 |
| API 응답 오류 | 로그 파일에 상세 에러 기록, 콘솔에는 축약 메시지 출력 |

---

## 5. 로깅 시스템

**로그 파일**: `logs/summarizer_YYYYMMDD.log`

| 레벨 | 출력 대상 | 용도 |
|------|-----------|------|
| DEBUG | 파일만 | API 요청/응답 상세 정보 |
| INFO | 파일만 | 처리 진행 상황 |
| WARNING | 파일 + 콘솔 | 경고 메시지 |
| ERROR | 파일 + 콘솔 | 에러 상세 (콘솔은 축약) |

**핵심 원칙**: LLM API 에러 메시지는 `logs/` 디렉터리의 로그 파일에만 기록되며, 요약 결과 파일(`*_summaries.md`)에는 오염되지 않습니다.
