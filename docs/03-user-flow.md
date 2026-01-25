# 03. User Flow

## 1. 기본 실행 흐름

```
┌─────────────────────────────────────────────────────────────┐
│                      사용자 시작                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  --llm 옵션 확인        │
              │  (glm/chatgpt/minimax/ │
              │   perplexity)          │
              └───────────┬────────────┘
                          │
                          ▼
              ┌────────────────────────┐
              │  파일/디렉터리 인자 확인 │
              └───────────┬────────────┘
                          │
           ┌──────────────┴──────────────┐
           │                             │
           ▼                             ▼
   ┌───────────────┐           ┌─────────────────┐
   │ 인자 있음      │           │ 인자 없음       │
   └───────┬───────┘           │ (대화형 모드)   │
           │                   └────────┬────────┘
           │                            │
           │                            ▼
           │               ┌────────────────────────┐
           │               │ 1. LLM 제공자 선택     │
           │               │ 2. 파일/디렉터리 선택  │
           │               └───────────┬────────────┘
           │                           │
           └───────────────┬───────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  API 키 확인           │
              │  (환경변수 또는 입력)   │
              └───────────┬────────────┘
                          │
                          ▼
              ┌────────────────────────┐
              │  파일 파싱 시작        │
              └───────────┬────────────┘
                          │
                          ▼
              ┌────────────────────────┐
              │  선택된 LLM으로 요약    │
              └───────────┬────────────┘
                          │
                          ▼
              ┌────────────────────────┐
              │  결과 파일 저장        │
              └────────────────────────┘
```

---

## 2. 사용 시나리오

### 시나리오 A: LLM 지정하여 실행

```bash
# ChatGPT로 전체 요약
python src/full_date_summary.py --llm chatgpt data/chat.txt

# Perplexity로 어제~오늘 요약
python src/full_yesterday_summary.py --llm perplexity data/chat.txt

# MiniMax로 오늘 요약
python src/full_today_summary.py --llm minimax data/chat.txt

# 간결 요약 (음슴체)
python src/simple_yesterday_summary.py --llm minimax data/chat.txt
python src/simple_today_summary.py --llm minimax data/chat.txt
```

**콘솔 출력 예시**:
```
Processing 5 dates -> 'chat_summaries.md'
  ▶ [1/5] 2024-01-20 (42 msgs) 요약 중...
  ▶ [2/5] 2024-01-21 (38 msgs) 요약 중...
  ...
  🔗 URL 추출 중...
    ✅ 12개 URL 추출 -> chat_url.txt

  📋 날짜별 결과:
    - 2024-01-20: ✅ 성공
    - 2024-01-21: ✅ 성공
    ...
```

---

### 시나리오 B: 대화형 실행

```bash
python src/full_date_summary.py
```

**콘솔 출력 예시**:
```
Usage:
  python full_date_summary.py <file>
  python full_date_summary.py <directory>
  python full_date_summary.py --llm chatgpt <file>

🤖 LLM 제공자 선택:
  1. Z.AI GLM (glm)
  2. OpenAI ChatGPT (chatgpt)
  3. MiniMax (minimax)
  4. Perplexity (perplexity)

선택 (1-4, 기본=1): 2

Available files:
  1. 코딩모임_KakaoTalk.txt
  2. 스터디방_KakaoTalk.txt
  A. 전체 디렉터리 처리

Select (number/A/Enter to exit): 1

==================================================
🔑 API 인증 설정 (OpenAI ChatGPT)
==================================================
환경 변수 OPENAI_API_KEY가 설정되지 않았습니다.
👉 OpenAI ChatGPT API Key: ********
✅ API Key가 설정되었습니다.

Processing 3 dates -> '코딩모임_KakaoTalk_summaries.md'
...
```

---

### 시나리오 C: 디렉터리 일괄 처리

```bash
python src/full_date_summary.py --llm minimax data/
```

**콘솔 출력 예시**:
```
============================================================
📁 디렉터리 일괄 처리
============================================================
📂 디렉터리: data/
🤖 LLM: MiniMax
📄 파일 수: 3개
============================================================

   1. 코딩모임.txt
   2. 스터디방.txt
   3. 프로젝트.txt

계속 진행하시겠습니까? (Y/n): Y

------------------------------------------------------------

[1/3] 📄 코딩모임.txt
Processing 5 dates -> '코딩모임_summaries.md'
...

[2/3] 📄 스터디방.txt
...

============================================================
📋 최종 결과
============================================================
  ✅ 성공 코딩모임.txt
  ✅ 성공 스터디방.txt
  ✅ 성공 프로젝트.txt
------------------------------------------------------------
총 3개 | ✅ 성공: 3 | 기타: 0
```

---

## 3. 출력 결과물

### 3.1 요약 리포트 (_summaries.md)

```markdown
# 📚 카카오톡 대화 요약 리포트
- **원본 파일**: chat.txt
- **총 대화 일수**: 5일
- **LLM**: OpenAI ChatGPT
- **생성 일시**: 2024-01-24 15:30:00
---

## 📅 2024-01-20 (42 msg)

### 🌟 3줄 요약
1. 새 프로젝트 킥오프 미팅 진행
2. 기술 스택 논의 (Python, FastAPI)
3. 다음 주 스프린트 계획 수립

### ❓ Q&A 및 해결된 문제
...
```

### 3.2 URL 목록 (_url.txt)

```
🔗 [chat] URL 목록
생성 시간: 2024-01-24 15:30:00
총 12개 URL
============================================================

https://fastapi.tiangolo.com (FastAPI 공식 문서)
https://github.com/example/project (프로젝트 레포)
...
```
