"""
OpenAI SDK Features Demo
Demonstrates the usage of OpenAI SDK-based features including:
- Function calling
- Batching
- Message management
- Multi-turn dialogue with context

This is a reference implementation showing how to use the new features.
"""
from utils.message_manager import MessageManager
from utils.function_calling import FunctionRegistry, MEETING_SUMMARY_SCHEMA
from utils.batch_processor import BatchProcessor
from services.ai_service import AIService
import json


def demo_message_management():
    """
    Demonstrate message management and multi-turn dialogue.
    
    This shows how to maintain conversation context across multiple turns.
    """
    print("=" * 60)
    print("Demo: Message Management & Multi-turn Dialogue")
    print("=" * 60)
    
    # Initialize message manager
    manager = MessageManager(max_history=50)
    
    # Set system message
    manager.set_system_message(
        "You are a professional meeting assistant. Help users summarize meetings."
    )
    
    # First turn: User asks about summary format
    manager.add_user_message("What format should I use for meeting summaries?")
    
    # Simulate assistant response
    manager.add_assistant_message(
        "I recommend using a structured format with key points, decisions, "
        "action items, and next steps."
    )
    
    # Second turn: User provides transcript
    manager.add_user_message(
        "Here's my meeting transcript: [transcript content]"
    )
    
    # Get messages for API
    messages = manager.get_messages_for_api()
    print(f"\nTotal messages in context: {len(messages)}")
    print("\nMessage structure:")
    for i, msg in enumerate(messages, 1):
        print(f"{i}. {msg['role']}: {msg['content'][:50]}...")
    
    print("\n" + "=" * 60 + "\n")


def demo_function_calling():
    """
    Demonstrate function calling capabilities.
    
    This shows how to define and use functions with OpenAI API.
    """
    print("=" * 60)
    print("Demo: Function Calling")
    print("=" * 60)
    
    # Initialize function registry
    registry = FunctionRegistry()
    
    # Get function definitions for API
    functions = registry.get_function_definitions()
    print(f"\nRegistered functions: {len(functions)}")
    for func in functions:
        print(f"- {func['name']}: {func['description']}")
    
    # Execute a function
    print("\nExecuting function 'get_summary_format':")
    result = registry.execute_function(
        "get_summary_format",
        {"format_type": "structured"}
    )
    print(f"Result: {result}")
    
    # Show mock data schema
    print("\nMeeting Summary Schema:")
    print(json.dumps(MEETING_SUMMARY_SCHEMA, indent=2))
    
    print("\n" + "=" * 60 + "\n")


def demo_batch_processing():
    """
    Demonstrate batch processing capabilities.
    
    This shows how to process multiple requests efficiently.
    """
    print("=" * 60)
    print("Demo: Batch Processing")
    print("=" * 60)
    
    # Initialize batch processor
    processor = BatchProcessor(batch_size=5, timeout=30.0)
    
    # Add multiple requests
    for i in range(10):
        processor.add_request(
            request_id=f"req_{i}",
            data={"transcript": f"Meeting transcript {i}"},
            callback=lambda result: print(f"Callback: {result['id']} processed")
        )
    
    print(f"\nAdded {processor.get_pending_count()} requests to batch")
    
    # Define processor function
    def process_transcript(data):
        """Simulate transcript processing."""
        return {"summary": f"Summary for {data['transcript']}"}
    
    # Process batch
    print("\nProcessing batch...")
    results = processor.process_batch(process_transcript)
    
    print(f"\nProcessed {len(results)} requests")
    print(f"Successful: {sum(1 for r in results if r['success'])}")
    print(f"Failed: {sum(1 for r in results if not r['success'])}")
    
    # Cleanup
    processor.shutdown()
    
    print("\n" + "=" * 60 + "\n")


def demo_multi_turn_dialogue():
    """
    Demonstrate multi-turn dialogue with context preservation.
    
    This shows a complete conversation flow with context management.
    """
    print("=" * 60)
    print("Demo: Multi-turn Dialogue with Context")
    print("=" * 60)
    
    # Initialize message manager
    manager = MessageManager()
    
    # Set system message
    manager.set_system_message(
        "You are a helpful meeting assistant. Maintain context across the conversation."
    )
    
    # Turn 1: User asks about summary
    manager.add_user_message("I need to summarize a meeting about project planning.")
    print("Turn 1 - User: I need to summarize a meeting about project planning.")
    
    # Turn 2: Assistant responds
    manager.add_assistant_message(
        "I can help you summarize the meeting. Please provide the meeting transcript."
    )
    print("Turn 2 - Assistant: I can help you summarize...")
    
    # Turn 3: User provides transcript
    manager.add_user_message(
        "The meeting discussed Q1 goals, budget allocation, and team assignments."
    )
    print("Turn 3 - User: The meeting discussed Q1 goals...")
    
    # Turn 4: Assistant provides summary (with context from previous turns)
    manager.add_assistant_message(
        "Based on our conversation about project planning, here's the summary:\n"
        "- Q1 Goals: Discussed\n"
        "- Budget Allocation: Addressed\n"
        "- Team Assignments: Covered"
    )
    print("Turn 4 - Assistant: Based on our conversation about project planning...")
    
    # Show conversation summary
    print(f"\nConversation Summary:")
    print(manager.get_conversation_summary())
    
    # Get messages for API (with full context)
    messages = manager.get_messages_for_api()
    print(f"\nTotal messages with context: {len(messages)}")
    
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    """
    Run all demos to showcase OpenAI SDK features.
    """
    print("\n" + "=" * 60)
    print("OpenAI SDK Features Demonstration")
    print("=" * 60 + "\n")
    
    # Run all demos
    demo_message_management()
    demo_function_calling()
    demo_batch_processing()
    demo_multi_turn_dialogue()
    
    print("=" * 60)
    print("All demos completed!")
    print("=" * 60)

