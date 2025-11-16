"""
Function Calling Module
Defines and manages function calling capabilities for OpenAI API.
Supports structured function definitions and execution.
"""
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass, field
import json


@dataclass
class FunctionParameter:
    """
    Represents a parameter in a function definition.
    
    Attributes:
        type: Parameter type (string, integer, number, boolean, object, array)
        description: Parameter description
        enum: Optional list of allowed values
        properties: Optional nested properties for object type
        required: Whether this parameter is required
    """
    type: str
    description: str
    enum: Optional[List[Any]] = None
    properties: Optional[Dict[str, Any]] = None
    required: Optional[bool] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert parameter to dictionary format."""
        param_dict: Dict[str, Any] = {
            "type": self.type,
            "description": self.description
        }
        
        if self.enum is not None:
            param_dict["enum"] = self.enum
        
        if self.properties is not None:
            param_dict["properties"] = self.properties
        
        if self.required is not None:
            param_dict["required"] = self.required
        
        return param_dict


@dataclass
class FunctionDefinition:
    """
    Represents a function definition for OpenAI function calling.
    
    Attributes:
        name: Function name
        description: Function description
        parameters: Function parameters schema
        handler: Optional handler function to execute
    """
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Optional[Callable] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert function definition to OpenAI API format.
        
        Returns:
            Dictionary in OpenAI function calling format
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


class FunctionRegistry:
    """
    Registry for managing function definitions and handlers.
    Supports dynamic function registration and execution.
    """
    
    def __init__(self):
        """Initialize FunctionRegistry."""
        self.functions: Dict[str, FunctionDefinition] = {}
        self._register_default_functions()
    
    def register_function(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Optional[Callable] = None
    ) -> None:
        """
        Register a function for OpenAI function calling.
        
        Args:
            name: Function name
            description: Function description
            parameters: Function parameters schema (JSON Schema format)
            handler: Optional handler function to execute
        """
        func_def = FunctionDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler
        )
        self.functions[name] = func_def
    
    def get_function_definitions(self) -> List[Dict[str, Any]]:
        """
        Get all registered function definitions in OpenAI format.
        
        Returns:
            List of function definition dictionaries
        """
        return [func.to_dict() for func in self.functions.values()]
    
    def execute_function(
        self,
        name: str,
        arguments: Dict[str, Any]
    ) -> str:
        """
        Execute a registered function.
        
        Args:
            name: Function name
            arguments: Function arguments
            
        Returns:
            Function result as JSON string
            
        Raises:
            ValueError: If function not found or execution fails
        """
        if name not in self.functions:
            raise ValueError(f"Function '{name}' not found in registry")
        
        func_def = self.functions[name]
        
        if func_def.handler is None:
            # No handler registered, return arguments as result
            return json.dumps(arguments, ensure_ascii=False)
        
        try:
            # Execute handler function
            result = func_def.handler(**arguments)
            
            # Convert result to JSON string
            if isinstance(result, str):
                return result
            else:
                return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            raise ValueError(f"Error executing function '{name}': {str(e)}")
    
    def _register_default_functions(self) -> None:
        """Register default functions for meeting summary use cases."""
        
        # Function: Get meeting summary format
        self.register_function(
            name="get_summary_format",
            description="Get the preferred format for meeting summaries",
            parameters={
                "type": "object",
                "properties": {
                    "format_type": {
                        "type": "string",
                        "description": "The type of summary format requested",
                        "enum": ["bullet_points", "paragraph", "structured", "action_items"]
                    }
                },
                "required": ["format_type"]
            },
            handler=lambda format_type: {
                "format": format_type,
                "message": f"Summary will be formatted as: {format_type}"
            }
        )
        
        # Function: Extract action items
        self.register_function(
            name="extract_action_items",
            description="Extract action items from meeting transcript",
            parameters={
                "type": "object",
                "properties": {
                    "transcript": {
                        "type": "string",
                        "description": "The meeting transcript to extract action items from"
                    }
                },
                "required": ["transcript"]
            },
            handler=lambda transcript: {
                "action_items": [],
                "message": "Action items extraction requested"
            }
        )


# Mock data schema for meeting summaries
MEETING_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {
            "type": "string",
            "description": "Meeting topic or title"
        },
        "date": {
            "type": "string",
            "description": "Meeting date"
        },
        "participants": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of meeting participants"
        },
        "key_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Key discussion points"
        },
        "decisions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Decisions made during the meeting"
        },
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "assignee": {"type": "string"},
                    "deadline": {"type": "string"}
                }
            },
            "description": "Action items with assignees and deadlines"
        },
        "next_steps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Next steps or follow-up items"
        }
    },
    "required": ["topic", "key_points"]
}

