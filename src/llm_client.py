"""
llm_client.py - 통합 LLM API 클라이언트 모듈

다중 LLM 제공자(GLM, ChatGPT, MiniMax, Perplexity)를 지원하는
통합 API 클라이언트입니다.
"""

from typing import Dict, Any, Optional
import time
import requests
from config import config, LLM_PROVIDERS

# ChatGPT Rate Limit: 3 RPM (분당 3 요청)
# 안전하게 21초 대기 (60초 / 3 = 20초 + 1초 여유)
CHATGPT_RATE_LIMIT_DELAY = 21


class LLMClient:
    """
    통합 LLM API 클라이언트 클래스.
    
    config에서 선택된 LLM 제공자를 사용하여 API를 호출합니다.
    모든 제공자는 OpenAI 호환 API 형식을 사용합니다.
    """
    
    # ChatGPT 마지막 요청 시간 (클래스 변수로 공유)
    _last_chatgpt_request_time: float = 0
    
    def __init__(self, provider: Optional[str] = None):
        """
        LLMClient 인스턴스를 초기화합니다.
        
        Args:
            provider: LLM 제공자 (기본값: config의 현재 제공자)
        """
        if provider:
            config.set_provider(provider)
        
        self.provider_info = config.get_provider_info()
        self.api_key = config.get_api_key()
        self.logger = config.logger
        
        if not self.api_key:
            self.logger.warning(f"{self.provider_info.env_key} is not set.")

    def _wait_for_rate_limit(self):
        """
        ChatGPT Rate Limit 대기.
        ChatGPT만 분당 3 요청 제한이 있으므로, 요청 간 21초 대기.
        """
        if config.current_provider != "chatgpt":
            return
        
        elapsed = time.time() - LLMClient._last_chatgpt_request_time
        if elapsed < CHATGPT_RATE_LIMIT_DELAY and LLMClient._last_chatgpt_request_time > 0:
            wait_time = CHATGPT_RATE_LIMIT_DELAY - elapsed
            self.logger.info(f"[ChatGPT Rate Limit] Waiting {wait_time:.1f}s...")
            time.sleep(wait_time)

    def summarize(self, text: str) -> Dict[str, Any]:
        """
        카카오톡 대화 텍스트를 요약합니다.
        
        Args:
            text: 요약할 카카오톡 대화 텍스트
            
        Returns:
            API 응답 결과 딕셔너리:
            - success: 요청 성공 여부 (bool)
            - content: 요약 결과 텍스트 (성공 시)
            - usage: 토큰 사용량 정보 (성공 시)
            - error: 에러 메시지 (실패 시)
        """
        if not self.api_key:
             return {"success": False, "error": f"API Key is missing. Set {self.provider_info.env_key}"}

        # ChatGPT Rate Limit 대기
        self._wait_for_rate_limit()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.provider_info.model,
            "max_tokens": 4000,
            "temperature": 0.5,
            "messages": [
                {"role": "user", "content": config.PROMPT_TEMPLATE.format(text=text)}
            ]
        }

        try:
            self.logger.info(f"[{self.provider_info.name}] Sending request...")
            
            # ChatGPT 요청 시간 기록
            if config.current_provider == "chatgpt":
                LLMClient._last_chatgpt_request_time = time.time()
            
            response = requests.post(
                self.provider_info.api_url, 
                headers=headers, 
                json=payload, 
                timeout=config.api_timeout
            )
            
            if response.status_code != 200:
                error_msg = f"API Error {response.status_code}: {response.text}"
                self.logger.error(error_msg)
                return {"success": False, "error": error_msg}
            
            return self._parse_response(response.json())
            
        except requests.exceptions.Timeout:
            self.logger.error("Request timed out.")
            return {"success": False, "error": "Request timed out."}
        except Exception as e:
            self.logger.exception("An unexpected error occurred during API call.")
            return {"success": False, "error": str(e)}

    def _parse_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        OpenAI 호환 API 응답을 파싱합니다.
        """
        try:
            # MiniMax 에러 응답 체크
            if "base_resp" in data and data["base_resp"].get("status_code") != 0:
                error_msg = data["base_resp"].get("status_msg", "Unknown error")
                self.logger.error(f"API returned error: {error_msg}")
                return {"success": False, "error": error_msg}
            
            # OpenAI 호환 형식 파싱
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return {
                "success": True,
                "content": content,
                "usage": usage
            }
        except (KeyError, IndexError) as e:
            # 에러 시 응답 내용 로깅
            self.logger.error(f"Response parsing failed: {e}")
            self.logger.error(f"Response data: {data}")
            return {
                "success": False,
                "error": f"Response parsing failed: {e}"
            }


# 하위 호환성을 위한 별칭
GLMClient = LLMClient
