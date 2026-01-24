# 06. Tasks & Development Roadmap

## 1. 완료된 작업 ✅

### Phase 1: 기반 구축
- [x] 프로젝트 구조 설계
- [x] `config.py` - 설정 관리 모듈 구현
- [x] `parser.py` - 카카오톡 파싱 모듈 구현

### Phase 2: 핵심 기능
- [x] `llm_client.py` - 통합 LLM API 클라이언트
- [x] `chat_processor.py` - 요약 처리 모듈 구현
- [x] `date_summarizer.py` - 날짜별 요약 오케스트레이터
- [x] `yesterday_summarizer.py` - 어제 날짜 요약
- [x] `url_extractor.py` - URL 추출 모듈

### Phase 3: 다중 LLM 지원
- [x] GLM (Z.AI) 지원
- [x] ChatGPT (OpenAI) 지원
- [x] MiniMax 지원
- [x] Perplexity 지원
- [x] `--llm` CLI 옵션 추가
- [x] 대화형 LLM 선택 모드

### Phase 4: 사용성 개선
- [x] 대화형 파일 선택 모드
- [x] 디렉터리 일괄 처리
- [x] 런타임 API 키 입력
- [x] 처리 진행률 표시

### Phase 5: 코드 품질
- [x] 모듈화 및 리팩터링
- [x] 타입 힌트 추가
- [x] 한글 주석 작성
- [x] 문서화 (PRD, TRD, User Flow 등)

---

## 2. 향후 개선 사항 📋

### 우선순위 높음 (P0)
- [ ] 테스트 코드 작성 (pytest)
- [ ] 다양한 카카오톡 버전 호환성 테스트

### 우선순위 중간 (P1)
- [ ] 추가 LLM 지원 (Claude, Gemini 등)
- [ ] 프롬프트 템플릿 외부화 (YAML/JSON)
- [ ] 설정 파일 지원 (config.yaml)
- [ ] 캐싱 (동일 입력 재처리 방지)

### 우선순위 낮음 (P2)
- [ ] GUI 인터페이스
- [ ] 웹 서비스화 (FastAPI)
- [ ] 요약 품질 평가 지표

---

## 3. 알려진 제한사항 ⚠️

### 3.1 파싱 관련
- 일부 특수한 카카오톡 내보내기 형식은 인식되지 않을 수 있음
- 이미지, 이모티콘은 텍스트로만 표시됨

### 3.2 API 관련
- 각 LLM 제공자별 API 키 필요
- API Rate Limit 존재 (순차 처리로 대응)
- 긴 대화는 토큰 제한에 걸릴 수 있음

---

## 4. 버전 히스토리

### v1.2.0 (현재)
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
