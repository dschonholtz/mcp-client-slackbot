"""Unit tests for conversation manager."""

import pytest

from mcp_simple_slackbot.conversation.manager import ConversationManager


class TestConversationManager:
    """Test the ConversationManager class."""
    
    def test_initialization(self):
        """Test conversation manager initialization."""
        manager = ConversationManager()
        assert manager.conversations == {}
    
    def test_get_or_create_conversation(self):
        """Test get_or_create_conversation method."""
        manager = ConversationManager()
        
        # Get a non-existent conversation (should create)
        conv = manager.get_or_create_conversation("test-conv")
        assert conv == {"messages": []}
        assert "test-conv" in manager.conversations
        
        # Get an existing conversation
        conv2 = manager.get_or_create_conversation("test-conv")
        assert conv is conv2  # Should be the same object
    
    def test_add_message(self):
        """Test add_message method."""
        manager = ConversationManager()
        
        # Add a message to a new conversation
        manager.add_message("test-conv", "user", "Hello")
        
        # Check that the message was added
        assert manager.conversations["test-conv"]["messages"] == [
            {"role": "user", "content": "Hello"}
        ]
        
        # Add another message
        manager.add_message("test-conv", "assistant", "Hi there")
        
        # Check that both messages are present
        assert manager.conversations["test-conv"]["messages"] == [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]
        
    def test_add_message_with_metadata(self):
        """Test add_message method with metadata."""
        manager = ConversationManager()
        
        # Add a message with metadata
        metadata = {"channel": "C12345", "thread_ts": "1234567890.123456", "user": "U67890"}
        manager.add_message("test-conv", "user", "Hello", metadata=metadata)
        
        # Check that the message and metadata were added
        assert manager.conversations["test-conv"]["messages"] == [
            {
                "role": "user", 
                "content": "Hello", 
                "metadata": metadata
            }
        ]
        
        # Add another message without metadata
        manager.add_message("test-conv", "assistant", "Hi there")
        
        # Check that both messages are present with correct metadata
        assert manager.conversations["test-conv"]["messages"] == [
            {
                "role": "user", 
                "content": "Hello", 
                "metadata": metadata
            },
            {"role": "assistant", "content": "Hi there"}
        ]
    
    def test_get_messages(self):
        """Test get_messages method."""
        manager = ConversationManager()
        
        # Add multiple messages
        manager.add_message("test-conv", "user", "Hello")
        manager.add_message("test-conv", "assistant", "Hi there")
        manager.add_message("test-conv", "user", "How are you?")
        
        # Get all messages (default limit)
        messages = manager.get_messages("test-conv")
        assert len(messages) == 3
        
        # Get limited messages
        messages = manager.get_messages("test-conv", limit=2)
        assert len(messages) == 2
        assert messages[0]["content"] == "Hi there"
        assert messages[1]["content"] == "How are you?"
        
        # Get messages from non-existent conversation
        messages = manager.get_messages("non-existent")
        assert messages == []
    
    def test_clear_conversation(self):
        """Test clear_conversation method."""
        manager = ConversationManager()
        
        # Add a message
        manager.add_message("test-conv", "user", "Hello")
        
        # Clear the conversation
        manager.clear_conversation("test-conv")
        
        # Check that messages are cleared
        assert manager.conversations["test-conv"]["messages"] == []
        
        # Clear non-existent conversation (should not error)
        manager.clear_conversation("non-existent")