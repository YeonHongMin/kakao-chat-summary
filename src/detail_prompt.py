"""
detail_prompt.py - 상세 분석 요약 프롬프트 및 HTML 템플릿

기존 요약(full_config.py PROMPT_TEMPLATE)과 독립적으로 동작하는
심층 분석 요약 모듈입니다. LLM에게 HTML 태그로 직접 출력하도록 요청하고,
다크 테마 CSS 템플릿으로 래핑하여 저장합니다.
"""

import re
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any

import hanja
import requests

logger = logging.getLogger("KakaoSummarizer")

# ChatGPT Rate Limit (LLMClient와 공유하지 않으므로 별도 관리)
_last_chatgpt_request_time: float = 0
_CHATGPT_RATE_LIMIT_DELAY = 21


# ==================== 프롬프트 템플릿 ====================

DETAIL_PROMPT_TEMPLATE = """다음은 카카오톡 오픈채팅방 '{room_name}'의 {date_str} 대화 내용입니다.
이 대화를 심층 분석하여, 아래 구조의 **HTML 태그**로 작성해주세요.

**출력 규칙:**
- 마크다운이 아닌 순수 HTML 태그만 사용하세요.
- 출력은 반드시 <h1> 태그로 시작하세요.
- 사고 과정, 분석 계획, 추론 내용은 절대 출력하지 마세요.
- <h1> 앞에 어떤 텍스트도 넣지 마세요.

## 필수 출력 구조

<h1>🧠 핵심 주제를 반영한 제목 ({date_str})</h1>
<blockquote><p><strong>데이터:</strong> {room_name} 카카오톡 채팅 분석 | <strong>주요 키워드 TOP 20:</strong> 키워드1(빈도), 키워드2(빈도), ..., 키워드20(빈도) (대화에서 실제 등장한 키워드가 20개 미만이면 있는 만큼만 표기)</p></blockquote>
<p>전체 대화의 핵심 흐름을 2~3문장으로 요약하는 개요 문단</p>

--- 아래를 토픽 수만큼 반복 (대화에서 논의된 모든 주제를 빠짐없이 토픽으로 만드세요. 최소 5개, 대화량이 많으면 10~20개 이상도 가능합니다. 짧은 언급이라도 독립 토픽으로 분리하세요.) ---

<h2>N. 토픽 제목</h2>
<p>토픽 설명 3~5문장. 실제 발언자 @닉네임을 인용하여 근거를 제시하세요.</p>
<ul>
<li><strong>근거 제목</strong> — 구체적 설명 (@발언자) <a href="실제URL">🔗</a></li>
<li><strong>근거 제목</strong> — 구체적 설명 (@발언자) <a href="실제URL">🔗</a></li>
</ul>
<blockquote>
<p><strong>시사점:</strong> 이 토픽에서 얻을 수 있는 인사이트 1~2문장</p>
<p class="tags">#해시태그1 #해시태그2 #해시태그3</p>
</blockquote>

--- 토픽 반복 끝 ---

<h2>📊 오늘의 감정/온도 분석</h2>
<ul>
<li>🔴 <strong>과열 신호:</strong> 토픽명 (시간대) — 과열 이유</li>
<li>🟢 <strong>실질적 성장:</strong> 토픽명 (시간대) — 성장 근거</li>
<li>🟡 <strong>주의 필요:</strong> 토픽명 (시간대) — 주의 사유</li>
<li>🔵 <strong>패러다임 전환:</strong> 토픽명 (시간대) — 전환 내용</li>
</ul>

<h2>🎯 핵심 시사점</h2>
<ol>
<li><strong>시사점 제목:</strong> 상세 설명</li>
<li><strong>시사점 제목:</strong> 상세 설명</li>
<li><strong>시사점 제목:</strong> 상세 설명</li>
</ol>

<h2>🔗 공유된 URL 모음</h2>
<!-- 아래 url-card 구조를 URL 개수만큼 반복 -->
<div class="url-card">
<p><a href="실제URL">실제URL</a></p>
<h3>제목 또는 사이트/리포지토리명 (@공유자)</h3>
<ul class="url-details">
<li><strong>내용</strong> · 어떤 내용인지 구체적으로 요약</li>
<li><strong>시사점</strong> · 대화에서 이 링크가 논의된 맥락, 의미, 참여자들의 반응</li>
<li><strong>활용</strong> · 이 링크를 어떻게 참고하거나 활용하면 좋을지 방안</li>
</ul>
</div>
<!-- 반복 끝 -->

## 작성 규칙
- HTML 태그만 사용 (<h1>, <h2>, <p>, <ul>, <ol>, <li>, <blockquote>, <strong>, <a> 등)
- **URL 처리 (최우선 규칙 — 반드시 준수)**:
  - 대화 텍스트에서 http:// 또는 https://로 시작하는 **모든 URL을 하나도 빠짐없이 100% 추출** (누락 시 시스템 에러 발생)
  - YouTube(youtube.com, youtu.be), GitHub, X(twitter/x.com), 블로그, 뉴스, npm, PyPI 등 **모든 도메인** 포함
  - 짧은 URL(youtu.be/...), 리다이렉트 URL, 쿼리 파라미터가 긴 URL도 원본 그대로 포함
  - 단순 도메인 URL(예: https://www.minimax.io/)도 반드시 포함
  - 각 토픽의 근거 항목에 관련 URL이 있으면 <a href="URL">🔗</a>로 포함
  - "🔗 공유된 URL 모음" 섹션에 대화의 **모든 URL을 빠짐없이** 모아 정리 — 대화 텍스트를 처음부터 끝까지 스캔하여 URL을 하나씩 확인하세요
  - 각 URL은 <div class="url-card"> 구조를 사용하여 '내용', '시사점', '활용' 방안을 구체적으로 작성하고 공유자(@닉네임) 표기
  - 토픽과 관련 없는 URL이라도 "🔗 공유된 URL 모음"에는 반드시 포함
  - URL이 없는 대화라면 이 섹션을 생략
- 발언자를 @닉네임 형태로 인용
- 각 근거는 실제 대화 내용 기반
- 키워드 빈도는 실제 대화에서 해당 키워드가 언급된 횟수를 세어 표기
- **"한글 설명"과 "영어 용어"로만 답변**: "중국어", "일본어", "아랍어" 등 다른 언어는 절대 사용하지 마세요. 모든 내용은 한글과 영어로만 작성

---
{text}
---

[최종 검토 규칙] - 매우 중요
절대로 한자(예: 推荐, 们, 中, 无)나 일본어(예: の間, が)를 출력하지 마세요. 모든 단어는 반드시 한글(한국어)로 번역해서 출력하세요. 
예: "도구 推荐" -> "도구 추천", "내용中" -> "내용 중", "の間에서" -> "사이에서".
출력 결과에 한자나 일본어가 단 하나라도 있으면 시스템 에러가 발생합니다! 오직 한글과 영어만 사용하세요.

아래에 <h1>부터 바로 시작하세요. 사고 과정이나 설명 없이 HTML만 출력:"""


# ==================== HTML 템플릿 (다크 테마, 파일 저장용) ====================

DETAIL_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🧠 {room_name} AI 상세 분석 {date_str}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans KR",
                   "Apple SD Gothic Neo", sans-serif;
      background: #0d1117;
      color: #c9d1d9;
      line-height: 1.75;
      padding: 2.5rem 1rem 4rem;
    }}
    .container {{ max-width: 820px; margin: 0 auto; }}
    h1 {{
      font-size: 1.65rem; font-weight: 700; color: #f0f6fc;
      border-bottom: 2px solid #1f6feb;
      padding-bottom: 0.6rem; margin-bottom: 0.4rem;
    }}
    .meta {{ font-size: 0.8rem; color: #484f58; margin-bottom: 2rem; }}
    h2 {{
      font-size: 1.1rem; font-weight: 600; color: #79c0ff;
      background: rgba(31, 111, 235, 0.08);
      border-left: 3px solid #1f6feb;
      padding: 0.55rem 0.9rem;
      margin-top: 2.5rem; margin-bottom: 0.8rem;
      border-radius: 0 6px 6px 0;
    }}
    h3 {{
      font-size: 0.95rem; font-weight: 600; color: #d2a8ff;
      margin-top: 1.4rem; margin-bottom: 0.4rem;
    }}
    p {{ margin: 0.6rem 0; color: #c9d1d9; }}
    ul {{ margin: 0.5rem 0 0.5rem 1.3rem; }}
    ol {{ margin: 0.5rem 0 0.5rem 1.3rem; }}
    li {{ margin: 0.45rem 0; color: #c9d1d9; line-height: 1.65; }}
    li p {{ margin: 0; }}
    .url-card {{
      background: rgba(31, 111, 235, 0.05);
      border: 1px solid rgba(88, 166, 255, 0.2);
      border-radius: 6px;
      padding: 1.2rem;
      margin-bottom: 1rem;
    }}
    .url-card p {{ margin: 0 0 0.4rem 0; }}
    .url-card p a {{ font-size: 0.9rem; color: #79c0ff; word-break: break-all; border-bottom: none; }}
    .url-card p a:hover {{ border-bottom: 1px solid #79c0ff; }}
    .url-card h3 {{
      font-size: 1.05rem; color: #f0f6fc; margin: 0.2rem 0 0.8rem 0;
    }}
    .url-card .url-details {{ margin: 0; padding: 0; list-style-type: none; }}
    .url-card .url-details li {{
      margin-bottom: 0.3rem; line-height: 1.5; font-size: 0.95rem; color: #c9d1d9;
    }}
    .url-card .url-details li strong {{ color: #8b949e; font-weight: 600; margin-right: 0.2rem; }}
    blockquote {{
      border-left: 3px solid #6e40c9;
      padding: 0.45rem 0.9rem; margin: 0.8rem 0;
      background: rgba(110, 64, 201, 0.08);
      border-radius: 0 6px 6px 0;
      color: #d2a8ff; font-size: 0.93rem;
    }}
    blockquote p {{ color: #d2a8ff; }}
    .tags {{ font-size: 0.85rem; color: #8b949e; margin-top: 0.3rem; }}
    a {{
      color: #58a6ff; text-decoration: none;
      border-bottom: 1px solid rgba(88, 166, 255, 0.3);
    }}
    a:hover {{ border-color: #58a6ff; color: #79c0ff; }}
    code {{
      background: rgba(110, 64, 201, 0.18);
      padding: 0.1em 0.4em; border-radius: 4px;
      font-size: 0.88em; color: #d2a8ff;
    }}
    strong {{ color: #f0f6fc; }}
    em {{ color: #8b949e; font-style: normal; }}
    hr {{ border: none; border-top: 1px solid #21262d; margin: 2.5rem 0; }}
    .footer {{ font-size: 0.75rem; color: #484f58; text-align: center; margin-top: 3rem; }}
  </style>
</head>
<body>
  <div class="container">
    <p class="meta">{room_name} 카카오톡 채팅 분석 | {date_display} | {llm_provider} | {timestamp}</p>
    {content}
    <p class="footer">Generated by KakaoTalk Chat Summary — Detail Analysis</p>
  </div>
</body>
</html>"""


# ==================== 유틸리티 함수 ====================

def generate_detail_prompt(text: str, room_name: str, date_str: str) -> str:
    """상세 분석 프롬프트 생성."""
    return DETAIL_PROMPT_TEMPLATE.format(
        room_name=room_name,
        date_str=date_str,
        text=text
    )


def wrap_detail_html(content: str, room_name: str, date_str: str,
                     llm_provider: str = "Unknown") -> str:
    """LLM 출력을 다크 테마 HTML로 래핑."""
    return DETAIL_HTML_TEMPLATE.format(
        room_name=room_name,
        date_str=date_str,
        date_display=date_str,
        llm_provider=llm_provider,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        content=content
    )


def strip_reasoning(content: str) -> str:
    """LLM 추론(thinking) 내용 제거."""
    # <think>...</think> 블록 제거
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
    # HTML 출력 시작점(<h1>) 이전의 추론 텍스트 제거
    match = re.search(r'<h1>', content)
    if match and match.start() > 50:
        content = content[match.start():]
    return content.strip()


def clean_foreign_chars(content: str) -> str:
    """한자 → 한글 독음 변환, 일본어(히라가나/가타카나) 제거."""
    # 1) 한자(CJK) → 한글 독음 변환
    content = hanja.translate(content, 'substitution')
    # 2) 일본어 히라가나(\u3040-\u309f), 가타카나(\u30a0-\u30ff) 제거
    content = re.sub(r'[\u3040-\u309f\u30a0-\u30ff]+', '', content)
    return content


def validate_detail_response(content: str) -> Dict[str, Any]:
    """상세 분석 응답 검증."""
    if len(content) < 200:
        return {"valid": False, "reason": f"응답이 너무 짧습니다 ({len(content)}자)"}
    if "<h2>" not in content:
        return {"valid": False, "reason": "토픽 섹션(h2)이 없습니다"}
    if content.count("<h2>") < 2:
        return {"valid": False, "reason": "토픽이 2개 미만입니다"}
    return {"valid": True, "reason": ""}


def call_detail_llm(text: str, room_name: str, date_str: str,
                    provider: str = "glm") -> Dict[str, Any]:
    """
    상세 분석을 위한 LLM API 호출.

    기존 LLMClient를 수정하지 않고, full_config의 설정만 재사용합니다.

    Returns:
        {"success": bool, "content": str, "error": str}
    """
    global _last_chatgpt_request_time

    from full_config import config, LLM_PROVIDERS

    provider_info = LLM_PROVIDERS.get(provider)
    if not provider_info:
        return {"success": False, "error": f"Unknown provider: {provider}"}

    api_key = config.get_api_key(provider)
    if not api_key and provider_info.env_key:
        return {"success": False, "error": f"API Key가 설정되지 않았습니다: {provider_info.env_key}"}

    # ChatGPT Rate Limit
    if provider == "chatgpt":
        elapsed = time.time() - _last_chatgpt_request_time
        if elapsed < _CHATGPT_RATE_LIMIT_DELAY and _last_chatgpt_request_time > 0:
            wait_time = _CHATGPT_RATE_LIMIT_DELAY - elapsed
            logger.info(f"[Detail/ChatGPT] Rate Limit 대기 {wait_time:.1f}s...")
            time.sleep(wait_time)

    prompt = generate_detail_prompt(text, room_name, date_str)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": provider_info.model,
        "max_tokens": provider_info.max_tokens,
        "temperature": 0.5,
        "messages": [
            {"role": "system", "content": "You are a native South Korean AI assistant. You MUST write your response ONLY in pure Korean (Hangul) and English. You are STRICTLY FORBIDDEN from outputting any Chinese characters (Hanzi/漢字/中文, e.g., 們, 推荐, 暂), Japanese characters (Hiragana/Katakana/Kanji, e.g., なし, が), or Arabic. Translate everything into natural Korean. If there is no data, say '없음'."},
            {"role": "user", "content": prompt}
        ]
    }
    if provider_info.reasoning_effort:
        payload["reasoning_effort"] = provider_info.reasoning_effort

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            logger.info(f"[Detail/{provider_info.name}] 요청 전송... (시도 {attempt + 1}/{max_retries})")
            request_start = time.time()

            if provider == "chatgpt":
                _last_chatgpt_request_time = time.time()

            response = requests.post(
                provider_info.api_url,
                headers=headers,
                json=payload,
                timeout=(60, 600),
                stream=True
            )

            elapsed = time.time() - request_start

            if response.status_code == 200:
                data = json.loads(response.content.decode('utf-8'))

                # MiniMax 에러 체크
                if "base_resp" in data and data["base_resp"].get("status_code") != 0:
                    error_msg = data["base_resp"].get("status_msg", "Unknown error")
                    return {"success": False, "error": error_msg}

                choice = data["choices"][0]
                content = choice["message"]["content"]

                # 추론 내용 제거 + 한자/일본어 후처리
                content = strip_reasoning(content)
                content = clean_foreign_chars(content)

                # finish_reason 체크
                finish_reason = choice.get("finish_reason", "unknown")
                if finish_reason == "length":
                    return {"success": False, "error": "응답이 잘렸습니다 (max_tokens 초과)"}

                # 검증
                validation = validate_detail_response(content)
                if not validation["valid"]:
                    logger.warning(f"[Detail/{provider_info.name}] ⚠️ 응답 검증 실패 ({elapsed:.0f}초): {validation['reason']}")
                    return {"success": False, "error": validation["reason"]}

                logger.info(f"[Detail/{provider_info.name}] ✅ 성공 ({elapsed:.0f}초)")
                return {"success": True, "content": content}

            elif response.status_code >= 500:
                logger.warning(f"API Error {response.status_code}. 재시도 대기 {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            else:
                return {"success": False, "error": f"API Error {response.status_code}: {response.text[:200]}"}

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.warning(f"Network Error: {e}. 재시도 대기 {retry_delay}s...")
            time.sleep(retry_delay)
            retry_delay *= 2
            continue
        except Exception as e:
            logger.exception("상세 분석 API 호출 중 예외 발생")
            return {"success": False, "error": str(e)}

    return {"success": False, "error": f"{max_retries}회 재시도 후 실패"}
