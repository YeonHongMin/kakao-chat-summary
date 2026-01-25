# 01. Product Requirements Document (PRD)

## 1. 제품 개요

### 1.1 제품명
**KakaoTalk Chat Summarizer** (카카오톡 대화 요약기)

### 1.2 목적
카카오톡에서 내보낸 대화 텍스트 파일을 분석하여, 다양한 LLM을 활용해 날짜별로 체계적인 요약 리포트를 자동 생성하는 CLI 도구입니다.

### 1.3 대상 사용자
- 오픈채팅방 관리자 및 참여자
- 스터디/커뮤니티 운영자
- 대화 내용을 정리하고 아카이빙하려는 사용자

---

## 2. 핵심 기능

### 2.1 다중 LLM 지원
- **GLM** (Z.AI): glm-4.7 (기본, 권장)
- **MiniMax**: MiniMax-M2.1 (고속 처리)
- **Perplexity**: sonar
- **ChatGPT** (Optional): gpt-4o-mini ⚠️ Rate Limit 3 RPM으로 대량 처리 부적합

> 📌 **API 호환성**: 모든 LLM 제공자는 **OpenAI 호환 API** 형식을 사용합니다. Anthropic(Claude) 형식은 현재 지원하지 않습니다.

### 2.2 대화 파싱 (Parsing)
- 카카오톡 내보내기 텍스트 파일(.txt) 읽기
- 다양한 내보내기 형식 지원 (PC/Mac, 모바일, 심플 형식)
- 날짜별 메시지 그룹화

### 2.3 LLM 기반 요약 (Summarization)
- 구조화된 프롬프트 템플릿 사용
- 6개 섹션으로 체계적 정리:
  - 🌟 3줄 요약
  - ❓ Q&A 및 해결된 문제
  - 💬 주요 토픽 & 논의
  - 💡 꿀팁 및 도구 추천
  - 🔗 링크/URL
  - 📅 일정 및 공지

### 2.4 URL 추출 (URL Extraction)
- 요약 결과에서 공유된 링크 자동 추출
- URL과 설명을 함께 저장
- 중복 URL 제거 및 설명 병합

---

## 3. 입출력 형식

### 3.1 입력
| 항목 | 형식 | 설명 |
|------|------|------|
| 대화 파일 | `.txt` | 카카오톡에서 내보낸 텍스트 파일 |
| LLM 선택 | `--llm` | glm, chatgpt, minimax, perplexity |
| API 키 | 환경변수 | 선택한 LLM에 해당하는 API 키 |

### 3.2 출력
| 파일 | 형식 | 설명 |
|------|------|------|
| `*_summaries.md` | Markdown | 날짜별 통합 요약 리포트 |
| `*_full_summary.md` | Markdown | 어제~오늘 상세 요약 |
| `*_simple_summary.md` | Markdown | 어제~오늘 간결 요약 (음슴체) |
| `*_full_today_summary.md` | Markdown | 오늘 상세 요약 |
| `*_simple_today_summary.md` | Markdown | 오늘 간결 요약 (음슴체) |
| `*_url.txt` | Text | 추출된 URL 목록 |

---

## 4. 기술 스택

| 구분 | 기술 |
|------|------|
| 언어 | Python 3.10+ |
| LLM API | GLM, OpenAI, MiniMax, Perplexity (OpenAI 호환) |
| HTTP 클라이언트 | requests |
| 파일 처리 | pathlib |
| 로깅 | logging (logs/ 디렉터리에 날짜별 상세 기록) |
