"""Base LLM client interface."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List

from mcp_simple_slackbot.config.settings import DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(self, api_key: str, model: str):
        """Initialize the LLM client.
        
        Args:
            api_key: API key for the LLM provider
            model: Model identifier to use
        """
        self.api_key = api_key
        self.model = model
        self.timeout = DEFAULT_TIMEOUT
        self.max_retries = DEFAULT_MAX_RETRIES

    @abstractmethod
    async def get_response(self, messages: List[Dict[str, str]]) -> str:
        """Get a response from the LLM.
        
        Args:
            messages: List of conversation messages

        Returns:
            Text response from the LLM
            
        Raises:
            NotImplementedError: If the method is not implemented
        """
        raise NotImplementedError("Subclasses must implement get_response")
    
    async def _handle_request_with_retries(
        self, request_func, error_message: str = "Request failed"
    ) -> str:
        """Handle API requests with retries and exponential backoff.
        
        Args:
            request_func: Async function to execute the request
            error_message: Message to include in the error response
            
        Returns:
            API response or error message
        """
        for attempt in range(self.max_retries + 1):
            try:
                result = await request_func()
                return result
            except Exception as e:
                if attempt == self.max_retries:
                    logging.error(f"{error_message}: {str(e)}")
                    return f"{error_message}: {str(e)}"
                await asyncio.sleep(2**attempt)  # Exponential backoff
        
        # This should never be reached, but added to satisfy type checker
        return f"{error_message}: Maximum retries exceeded"


class LLMClient:
    """Client for communicating with LLM APIs."""

    def __init__(self, api_key: str, model: str) -> None:
        """Initialize the LLM client factory.
        
        Args:
            api_key: API key for the LLM provider
            model: Model identifier to use
        """
        self.api_key = api_key
        self.model = model
        self._client = None

    async def get_response(self, messages: List[Dict[str, str]]) -> str:
        """Get a response from the appropriate LLM based on the model.
        
        Args:
            messages: List of conversation messages

        Returns:
            Text response from the LLM
            
        Raises:
            ValueError: If the model is not supported
        """
        from mcp_simple_slackbot.llm.providers.anthropic import AnthropicClient
        from mcp_simple_slackbot.llm.providers.groq import GroqClient
        from mcp_simple_slackbot.llm.providers.openai import OpenAIClient

        if self.model.startswith("gpt-") or self.model.startswith("ft:gpt-"):
            client = OpenAIClient(self.api_key, self.model)
        elif self.model.startswith("llama-"):
            client = GroqClient(self.api_key, self.model)
        elif self.model.startswith("claude-"):
            client = AnthropicClient(self.api_key, self.model)
        else:
            raise ValueError(f"Unsupported model: {self.model}")
        
        return await client.get_response(messages)