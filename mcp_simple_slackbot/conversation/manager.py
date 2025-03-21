"""Conversation context management."""

from typing import Dict, List, Optional, Any

from mcp_simple_slackbot.config.settings import DEFAULT_CONVERSATION_HISTORY_LIMIT


class ConversationManager:
    """Manages conversation contexts for different channels."""
    
    def __init__(self) -> None:
        """Initialize the conversation manager."""
        self.conversations: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    
    def get_or_create_conversation(self, conversation_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Get or create a conversation context.
        
        Args:
            conversation_id: Unique identifier for the conversation
            
        Returns:
            Conversation context dictionary
        """
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = {"messages": []}
        
        return self.conversations[conversation_id]
    
    def add_message(self, conversation_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a message to the conversation history.
        
        Args:
            conversation_id: Unique identifier for the conversation
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata about the message (such as thread info, user info)
        """
        conversation = self.get_or_create_conversation(conversation_id)
        message: Dict[str, Any] = {"role": role, "content": content}
        if metadata:
            message["metadata"] = metadata
        conversation["messages"].append(message)
    
    def get_messages(
        self, conversation_id: str, limit: int = DEFAULT_CONVERSATION_HISTORY_LIMIT
    ) -> List[Dict[str, Any]]:
        """Get recent messages from conversation history.
        
        Args:
            conversation_id: Unique identifier for the conversation
            limit: Maximum number of messages to return
            
        Returns:
            List of recent messages
        """
        conversation = self.get_or_create_conversation(conversation_id)
        return conversation["messages"][-limit:] if conversation["messages"] else []
    
    def clear_conversation(self, conversation_id: str) -> None:
        """Clear conversation history.
        
        Args:
            conversation_id: Unique identifier for the conversation
        """
        if conversation_id in self.conversations:
            self.conversations[conversation_id] = {"messages": []}