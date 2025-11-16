"""
Prompt Builder Module
Builds optimized prompts for AI summarization with well-crafted templates.
Supports multiple languages and contexts with structured output.
"""
from typing import Tuple, Optional
from config import LANGUAGE_NAMES


class PromptBuilder:
    """
    Builder for creating optimized AI prompts.
    Provides well-crafted prompt templates for various use cases.
    """
    
    def __init__(self):
        """Initialize PromptBuilder."""
        pass
    
    def _get_language_name(
        self,
        language: str,
        custom_language: Optional[str] = None
    ) -> str:
        """
        Get display name for language.
        
        Args:
            language: Language code (e.g., 'vi', 'en', 'zh')
            custom_language: Custom language name if language is "other"
            
        Returns:
            Language display name (e.g., 'Vietnamese', 'English')
        """
        if language == 'other' and custom_language:
            return custom_language
        return LANGUAGE_NAMES.get(language, 'the language used')
    
    def build_summary_prompt(
        self,
        transcript: str,
        topic: Optional[str] = None,
        language: str = 'en',
        custom_language: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Build optimized prompt for meeting summarization.
        
        This method creates well-structured prompts that:
        - Preserve technical terminology and proper nouns
        - Focus on key decisions and action items
        - Maintain context and clarity
        - Support multiple languages
        
        Args:
            transcript: The transcribed text to summarize
            topic: Optional topic/context for better summarization
            language: Language code for output (default: 'en')
            custom_language: Custom language name if language is "other"
            
        Returns:
            Tuple of (system_message, user_prompt) ready for OpenAI API
        """
        language_name = self._get_language_name(language, custom_language)
        
        # Build comprehensive system message with clear instructions
        # This sets the AI's role and behavior for the conversation
        system_message = (
            f"You are a professional meeting assistant specialized in creating "
            f"concise, accurate, and well-structured summaries.\n\n"
            f"Your summaries must:\n"
            f"- Always be written in {language_name}\n"
            f"- Preserve ALL technical terms, proper nouns, company names, "
            f"product names, and domain-specific terminology exactly as they appear\n"
            f"- NEVER translate technical terms, proper nouns, or brand names\n"
            f"- Focus on key decisions, action items, important discussions, and outcomes\n"
            f"- Maintain clarity and structure while being concise\n"
            f"- Use proper formatting with clear sections and bullet points when appropriate\n"
            f"- Include deadlines, responsibilities, and next steps when mentioned"
        )
        
        # Build user prompt with context-aware instructions
        # Include topic if provided for better context understanding
        if topic:
            user_prompt = f"""Please provide a comprehensive summary of the following meeting transcript.

MEETING TOPIC/CONTEXT: {topic}

CRITICAL INSTRUCTIONS:
- Write the summary in {language_name}
- Preserve ALL technical terms, jargon, and domain-specific vocabulary exactly as they appear
- Do NOT translate technical terms, proper nouns, company names, or product names
- Maintain the original terminology even if it's in a different language
- Focus on key decisions, action items, important discussions, and outcomes
- Structure the summary clearly with main points and sub-points
- Include any deadlines, responsibilities, or next steps mentioned
- Use the meeting topic/context to provide better understanding and relevance

Meeting Transcript:
---
{transcript}
---

Please provide the summary now:"""
        else:
            user_prompt = f"""Please provide a comprehensive summary of the following meeting transcript.

CRITICAL INSTRUCTIONS:
- Write the summary in {language_name}
- Preserve ALL technical terms, proper nouns, company names, and product names exactly as they appear
- Do NOT translate technical terms or proper nouns
- Focus on key decisions, action items, important discussions, and outcomes
- Structure the summary clearly with main points and sub-points
- Include any deadlines, responsibilities, or next steps mentioned

Meeting Transcript:
---
{transcript}
---

Please provide the summary now:"""
        
        return system_message, user_prompt
    
    def build_structured_summary_prompt(
        self,
        transcript: str,
        topic: Optional[str] = None,
        language: str = 'en',
        custom_language: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Build prompt for structured summary output.
        
        This creates prompts that request structured output with specific sections:
        - Key Points
        - Decisions
        - Action Items
        - Next Steps
        
        Args:
            transcript: The transcribed text to summarize
            topic: Optional topic/context
            language: Language code for output
            custom_language: Custom language name if language is "other"
            
        Returns:
            Tuple of (system_message, user_prompt) for structured output
        """
        language_name = self._get_language_name(language, custom_language)
        
        system_message = (
            f"You are a professional meeting assistant that creates structured summaries.\n\n"
            f"Your summaries must be written in {language_name} and include:\n"
            f"1. Key Points: Main discussion topics and important information\n"
            f"2. Decisions: Decisions made during the meeting\n"
            f"3. Action Items: Tasks assigned with assignees and deadlines\n"
            f"4. Next Steps: Follow-up actions and future plans\n\n"
            f"Preserve all technical terms and proper nouns exactly as they appear."
        )
        
        topic_context = f"\nMEETING TOPIC: {topic}\n" if topic else ""
        
        user_prompt = f"""Please provide a structured summary of the following meeting transcript.{topic_context}

Meeting Transcript:
---
{transcript}
---

Please provide the summary in the following structure:
1. Key Points
2. Decisions
3. Action Items
4. Next Steps"""
        
        return system_message, user_prompt

