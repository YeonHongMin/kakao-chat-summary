# 04. Data Design

## 1. 데이터 구조

이 프로젝트는 데이터베이스를 사용하지 않고 파일 기반으로 동작합니다.

---

## 2. 입력 데이터 형식

### 2.1 카카오톡 내보내기 파일 (.txt)

**PC/Mac 형식**:
```
[채팅방 이름] 카카오톡 대화
저장한 날짜 : 2024-01-24 15:00:00

--------------- 2024년 1월 20일 토요일 ---------------
[홍길동] [오전 10:00] 안녕하세요
[김철수] [오전 10:01] 네, 안녕하세요!
[홍길동] [오전 10:02] 오늘 회의 시간이 어떻게 되나요?

--------------- 2024년 1월 21일 일요일 ---------------
[홍길동] [오후 2:00] 회의록 공유드립니다
[홍길동] [오후 2:00] https://notion.so/meeting-notes
```

**모바일 형식**:
```
2024년 1월 20일 토요일
홍길동 : 안녕하세요
김철수 : 네, 안녕하세요!
```

---

## 3. 내부 데이터 구조

### 3.1 ParseResult (parser.py)

```python
@dataclass
class ParseResult:
    messages_by_date: Dict[str, List[str]]
    # 예시:
    # {
    #     "2024-01-20": [
    #         "[홍길동] [오전 10:00] 안녕하세요",
    #         "[김철수] [오전 10:01] 네, 안녕하세요!"
    #     ],
    #     "2024-01-21": [
    #         "[홍길동] [오후 2:00] 회의록 공유드립니다"
    #     ]
    # }
    
    total_dates: int
    # 예시: 2
```

### 3.2 API 응답 구조 (llm_client.py)

**성공 시**:
```python
{
    "success": True,
    "content": "### 🌟 3줄 요약\n1. ...\n\n### ❓ Q&A...",
    "usage": {
        "prompt_tokens": 1500,
        "completion_tokens": 800,
        "total_tokens": 2300
    }
}
```

**실패 시**:
```python
{
    "success": False,
    "error": "API Error 401: Unauthorized"
}
```

### 3.3 URL 추출 결과 (url_extractor.py)

```python
# Dict[str, List[str]]
{
    "https://fastapi.tiangolo.com": ["FastAPI 공식 문서"],
    "https://github.com/example": ["프로젝트 레포", "소스코드 저장소"],
    "https://notion.so/wiki": []  # 설명 없음
}
```

---

## 4. 출력 데이터 형식

### 4.1 요약 리포트 (_summaries.md)

```
파일명: {원본파일명}_summaries.md
인코딩: UTF-8
형식: Markdown

구조:
├── 헤더 (메타정보)
│   ├── 원본 파일명
│   ├── 총 대화 일수
│   └── 생성 일시
│
└── 날짜별 섹션 (반복)
    ├── ## 📅 YYYY-MM-DD (N msg)
    ├── ### 🌟 3줄 요약
    ├── ### ❓ Q&A 및 해결된 문제
    ├── ### 💬 주요 토픽 & 논의
    ├── ### 💡 꿀팁 및 도구 추천
    ├── ### 🔗 링크/URL
    └── ### 📅 일정 및 공지
```

### 4.2 URL 목록 (_url.txt)

```
파일명: {원본파일명}_url.txt
인코딩: UTF-8
형식: Plain Text

구조:
├── 헤더
│   ├── 채팅방 이름
│   ├── 생성 시간
│   └── 총 URL 개수
│
└── URL 목록 (알파벳순 정렬)
    └── {URL} ({설명})
```

---

## 5. 디렉터리 구조

```
kakao-chat-summary/
├── data/                          # 데이터 디렉터리
│   ├── 입력파일.txt               # 원본 대화 파일
│   ├── 입력파일_summaries.md      # 생성된 요약 리포트
│   └── 입력파일_url.txt           # 추출된 URL 목록
│
├── logs/                          # 로그 디렉터리
│   └── summarizer_YYYYMMDD.log    # 날짜별 상세 로그
│
├── src/                           # 소스 코드
│   ├── full_config.py                  # 설정 관리 (다중 LLM)
│   ├── parser.py                  # 카카오톡 파싱
│   ├── llm_client.py              # 통합 LLM API 클라이언트
│   ├── chat_processor.py          # 채팅 요약 처리
│   ├── full_date_summary.py         # 전체 날짜 요약 (메인)
│   ├── full_yesterday_summary.py    # 어제 날짜 요약
│   └── url_extractor.py           # URL 추출
│
├── docs/                          # 문서
└── requirements.txt               # 의존성
```
