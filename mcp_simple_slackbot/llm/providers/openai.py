"""OpenAI API integration."""

import httpx
from typing import Dict, List

from mcp_simple_slackbot.config.settings import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE, OPENAI_API_URL
from mcp_simple_slackbot.llm.client import BaseLLMClient


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI API."""

    async def get_response(self, messages: List[Dict[str, str]]) -> str:
        """Get a response from the OpenAI API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": DEFAULT_TEMPERATURE,
            "max_tokens": DEFAULT_MAX_TOKENS,
        }

        async def make_request():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(OPENAI_API_URL, json=payload, headers=headers)
                response.raise_for_status()
                response_data = response.json()
                return response_data["choices"][0]["message"]["content"]

        return await self._handle_request_with_retries(
            make_request, "Error getting response from OpenAI"
        )