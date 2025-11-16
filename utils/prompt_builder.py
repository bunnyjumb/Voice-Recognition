"""
Prompt Builder Module
Builds optimized prompts for AI summarization.
"""
from typing import Tuple, Optional
from config import LANGUAGE_NAMES


class PromptBuilder:
    """Builder for creating optimized AI prompts."""
    
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
            language: Language code
            custom_language: Custom language name if language is "other"
            
        Returns:
            Language display name
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
        Build optimized prompt for summarization.
        
        Args:
            transcript: The transcribed text to summarize
            topic: Optional topic/context for better summarization
            language: Language code for output
            custom_language: Custom language name if language is "other"
            
        Returns:
            Tuple of (system_message, user_prompt)
        """
        language_name = self._get_language_name(language, custom_language)
        
        # Build system message
        system_message = (
            f"You are a professional meeting assistant specialized in creating "
            f"concise and accurate summaries. Your summaries must:\n"
            f"- Always be written in {language_name}\n"
            f"- Preserve all technical terms, proper nouns, company names, "
            f"product names, and domain-specific terminology exactly as they appear\n"
            f"- Never translate technical terms or proper nouns\n"
            f"- Focus on key decisions, action items, and important points\n"
            f"- Maintain clarity and structure while being concise"
        )
        
        # Build user prompt with topic if provided
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

