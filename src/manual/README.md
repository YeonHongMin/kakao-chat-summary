# 📂 Manual Scripts

CLI에서 직접 실행할 수 있는 독립 실행형 스크립트입니다.

## 🚀 사용법

```bash
# src/manual 디렉터리에서 실행
cd src/manual

# 또는 프로젝트 루트에서 실행
python src/manual/<script_name>.py <filepath>
```

## 📋 스크립트 목록

### Full 버전 (상세 요약)
| 스크립트 | 설명 |
|---------|------|
| `full_today_summary.py` | 오늘 대화 요약 |
| `full_yesterday_summary.py` | 전체 기간 대화 요약 |
| `full_2days_summary.py` | 엇그제~오늘 대화 요약 |
| `full_date_summary.py` | 날짜별 통합 리포트 생성 |

### Simple 버전 (간결 요약 - 음슴체)
| 스크립트 | 설명 |
|---------|------|
| `simple_today_summary.py` | 오늘 대화 간결 요약 |
| `simple_yesterday_summary.py` | 전체 기간 간결 요약 |
| `simple_2days_summary.py` | 엇그제~오늘 간결 요약 |
| `simple_date_summary.py` | 날짜별 간결 리포트 생성 |

## 📖 공통 옵션

```bash
# 단일 파일 처리
python <script>.py data/KakaoTalk_xxx.txt

# 디렉터리 일괄 처리
python <script>.py data/

# LLM 지정 (기본: zhipu)
python <script>.py --llm chatgpt data/KakaoTalk_xxx.txt

# 대화형 모드
python <script>.py
```

## 🔧 환경 설정

API 키는 환경변수 또는 `.env` 파일에 설정:

```bash
# Z.AI (기본)
export ZHIPU_API_KEY="your_api_key"

# OpenAI
export OPENAI_API_KEY="your_api_key"

# Anthropic
export ANTHROPIC_API_KEY="your_api_key"
```

## 📁 출력 위치

- 요약 결과: `output/<채팅방>_<날짜>_summary.md`
- URL 목록: `output/<채팅방>_<날짜>_urls.md`
- 로그: `logs/summarizer_<날짜>.log`
