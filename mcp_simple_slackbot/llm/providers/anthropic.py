"""Anthropic API integration."""

import httpx
from typing import Dict, List

from mcp_simple_slackbot.config.settings import (
    ANTHROPIC_API_URL,
    ANTHROPIC_API_VERSION,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
)
from mcp_simple_slackbot.llm.client import BaseLLMClient


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic API."""

    async def get_response(self, messages: List[Dict[str, str]]) -> str:
        """Get a response from the Anthropic API."""
        headers = {
            "anthropic-version": ANTHROPIC_API_VERSION,
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        # Convert messages to Anthropic format
        system_message = None
        anthropic_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            elif msg["role"] == "user":
                anthropic_messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                anthropic_messages.append({"role": "assistant", "content": msg["content"]})

        payload = {
            "model": self.model,
            "messages": anthropic_messages,
            "temperature": DEFAULT_TEMPERATURE,
            "max_tokens": DEFAULT_MAX_TOKENS,
        }

        if system_message:
            payload["system"] = system_message

        async def make_request():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
                response.raise_for_status()
                response_data = response.json()
                return response_data["content"][0]["text"]

        return await self._handle_request_with_retries(
            make_request, "Error getting response from Anthropic"
        )