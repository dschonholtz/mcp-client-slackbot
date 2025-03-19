"""Unit tests for configuration module."""

import os
from unittest import mock

import pytest

from mcp_simple_slackbot.config.config import Configuration


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    with mock.patch.dict(os.environ, {
        "SLACK_BOT_TOKEN": "xoxb-test-token",
        "SLACK_APP_TOKEN": "xapp-test-token",
        "OPENAI_API_KEY": "sk-test-openai",
        "GROQ_API_KEY": "gsk-test-groq",
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "LLM_MODEL": "test-model",
    }):
        yield


class TestConfiguration:
    """Test the Configuration class."""
    
    def test_init_loads_env_vars(self, mock_env_vars):
        """Test that init loads environment variables."""
        config = Configuration()
        
        assert config.slack_bot_token == "xoxb-test-token"
        assert config.slack_app_token == "xapp-test-token"
        assert config.openai_api_key == "sk-test-openai"
        assert config.groq_api_key == "gsk-test-groq"
        assert config.anthropic_api_key == "sk-ant-test"
        assert config.llm_model == "test-model"
    
    def test_llm_api_key_openai(self, mock_env_vars):
        """Test llm_api_key property with OpenAI model."""
        config = Configuration()
        config.llm_model = "gpt-4"
        
        assert config.llm_api_key == "sk-test-openai"
    
    def test_llm_api_key_groq(self, mock_env_vars):
        """Test llm_api_key property with Groq model."""
        config = Configuration()
        config.llm_model = "llama-3"
        
        assert config.llm_api_key == "gsk-test-groq"
    
    def test_llm_api_key_anthropic(self, mock_env_vars):
        """Test llm_api_key property with Anthropic model."""
        config = Configuration()
        config.llm_model = "claude-3"
        
        assert config.llm_api_key == "sk-ant-test"
    
    def test_llm_api_key_fallback(self, mock_env_vars):
        """Test llm_api_key property with unknown model."""
        config = Configuration()
        config.llm_model = "unknown-model"
        
        # Should fallback to first available key
        assert config.llm_api_key == "sk-test-openai"
    
    def test_llm_api_key_error(self):
        """Test llm_api_key property with no keys available."""
        with mock.patch.dict(os.environ, {}, clear=True):
            # Create a config with no API keys
            config = Configuration()
            config.openai_api_key = None
            config.groq_api_key = None
            config.anthropic_api_key = None
            
            with pytest.raises(ValueError):
                _ = config.llm_api_key