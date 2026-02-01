"""
chat_processor.py - 채팅 텍스트 처리 모듈

이 모듈은 카카오톡 대화 텍스트를 받아 LLM API를 통해 요약하고,
Markdown 형식으로 결과를 포맷팅하는 기능을 제공합니다.
"""

from datetime import datetime
from typing import Optional
from full_config import config
from llm_client import LLMClient


class ChatProcessor:
    """
    채팅 텍스트 처리 클래스.
    
    LLM API를 통해 대화를 요약하고, 결과를 Markdown 형식으로 포맷팅합니다.
    """
    
    def __init__(self, provider: Optional[str] = None):
        """
        ChatProcessor 인스턴스를 초기화합니다.
        
        Args:
            provider: LLM 제공자 (glm, chatgpt, minimax, perplexity)
        """
        self.client = LLMClient(provider)
        self.logger = config.logger

    def process_summary(self, text: str) -> str:
        """
        대화 텍스트를 요약합니다.
        
        Args:
            text: 요약할 카카오톡 대화 텍스트
            
        Returns:
            Markdown 형식으로 포맷팅된 요약 결과 문자열.
            실패 시 '[ERROR]'로 시작하는 에러 메시지 반환.
        """
        self.logger.info("=== Chat Processing Started ===")
        
        result = self.client.summarize(text)
        
        if not result["success"]:
            error_msg = f"[ERROR] Summary failed: {result.get('error')}"
            self.logger.error(error_msg)
            return error_msg

        raw_content = result["content"]
        tokens = result.get("usage", {})
        self.logger.info(f"API Call Success. Tokens used: {tokens}")

        return self._format_as_markdown(raw_content)

    def _format_as_markdown(self, content: str) -> str:
        """
        요약 결과를 Markdown 형식으로 포맷팅합니다.
        file_storage._format_summary_content()에서 헤더/푸터를 추가하므로 여기서는 본문만 정리.
        """
        return content.strip()
