"""
Message Management Module
Handles conversation history and message management for multi-turn dialogues.
Provides context-aware message handling for OpenAI API.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Message:
    """
    Represents a single message in a conversation.
    
    Attributes:
        role: Message role (system, user, assistant, function)
        content: Message content
        name: Optional name for function calls
        function_call: Optional function call data
        timestamp: When the message was created
    """
    role: str  # 'system', 'user', 'assistant', 'function'
    content: str
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert message to dictionary format for OpenAI API.
        
        Returns:
            Dictionary representation of the message
        """
        message_dict: Dict[str, Any] = {
            "role": self.role,
            "content": self.content
        }
        
        if self.name:
            message_dict["name"] = self.name
        
        if self.function_call:
            message_dict["function_call"] = self.function_call
        
        return message_dict


class MessageManager:
    """
    Manages conversation history and message context.
    Supports multi-turn dialogues with context preservation.
    """
    
    def __init__(self, max_history: int = 50):
        """
        Initialize MessageManager.
        
        Args:
            max_history: Maximum number of messages to keep in history
        """
        self.messages: List[Message] = []
        self.max_history = max_history
        self.system_message: Optional[Message] = None
    
    def set_system_message(self, content: str) -> None:
        """
        Set or update the system message.
        
        Args:
            content: System message content
        """
        self.system_message = Message(
            role="system",
            content=content,
            timestamp=datetime.now()
        )
    
    def add_user_message(self, content: str) -> None:
        """
        Add a user message to the conversation.
        
        Args:
            content: User message content
        """
        message = Message(
            role="user",
            content=content,
            timestamp=datetime.now()
        )
        self.messages.append(message)
        self._trim_history()
    
    def add_assistant_message(
        self,
        content: str,
        function_call: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an assistant message to the conversation.
        
        Args:
            content: Assistant message content
            function_call: Optional function call data
        """
        message = Message(
            role="assistant",
            content=content,
            function_call=function_call,
            timestamp=datetime.now()
        )
        self.messages.append(message)
        self._trim_history()
    
    def add_function_message(self, name: str, content: str) -> None:
        """
        Add a function result message to the conversation.
        
        Args:
            name: Function name
            content: Function result content
        """
        message = Message(
            role="function",
            content=content,
            name=name,
            timestamp=datetime.now()
        )
        self.messages.append(message)
        self._trim_history()
    
    def get_messages_for_api(self) -> List[Dict[str, Any]]:
        """
        Get all messages in format suitable for OpenAI API.
        Includes system message if set.
        
        Returns:
            List of message dictionaries
        """
        api_messages: List[Dict[str, Any]] = []
        
        # Add system message first if exists
        if self.system_message:
            api_messages.append(self.system_message.to_dict())
        
        # Add conversation messages
        for message in self.messages:
            api_messages.append(message.to_dict())
        
        return api_messages
    
    def get_recent_messages(self, count: int = 10) -> List[Message]:
        """
        Get recent messages from conversation history.
        
        Args:
            count: Number of recent messages to retrieve
            
        Returns:
            List of recent messages
        """
        return self.messages[-count:] if len(self.messages) > count else self.messages
    
    def clear_history(self) -> None:
        """Clear conversation history (but keep system message)."""
        self.messages.clear()
    
    def clear_all(self) -> None:
        """Clear all messages including system message."""
        self.messages.clear()
        self.system_message = None
    
    def _trim_history(self) -> None:
        """Trim message history if it exceeds max_history."""
        if len(self.messages) > self.max_history:
            # Keep system message and recent messages
            self.messages = self.messages[-self.max_history:]
    
    def get_conversation_summary(self) -> str:
        """
        Get a summary of the conversation.
        
        Returns:
            String summary of conversation
        """
        if not self.messages:
            return "No conversation history."
        
        summary_parts = [
            f"Total messages: {len(self.messages)}",
            f"First message: {self.messages[0].timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Last message: {self.messages[-1].timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        ]
        
        return "\n".join(summary_parts)

