"""
Validation Service
Centralized validation logic for form data and requests.
Follows Single Responsibility Principle.
"""
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ValidationService:
    """
    Service for validating user input and requests.
    
    Responsibilities:
    - Validate form data (topic, language, etc.)
    - Provide clear error messages
    - Check required fields
    """
    
    @staticmethod
    def validate_audio_request(form_data: Dict, files: Dict) -> Tuple[bool, Optional[str], Dict]:
        """
        Validate audio processing request.
        
        Args:
            form_data: Form data dictionary
            files: Files dictionary from request
            
        Returns:
            Tuple of (is_valid, error_message, validated_data)
            validated_data contains: topic, language, custom_language
        """
        # Check audio file
        if 'audio_data' not in files:
            return False, "No audio file found in request", {}
        
        file = files['audio_data']
        if not file or file.filename == '':
            return False, "No file selected", {}
        
        # Validate topic
        topic = form_data.get('topic', '').strip()
        if not topic:
            return False, "Meeting Topic is required", {}
        
        # Validate language
        language = form_data.get('language', '').strip()
        if not language:
            return False, "Conversation Language is required", {}
        
        # Validate custom language if "other" is selected
        custom_language = form_data.get('custom_language', '').strip() or None
        if language == 'other' and not custom_language:
            return False, "Custom language is required when 'Other' is selected", {}
        
        validated_data = {
            'topic': topic,
            'language': language,
            'custom_language': custom_language
        }
        
        logger.info(f"Validation passed - Topic: {topic}, Language: {language}")
        if custom_language:
            logger.info(f"  Custom language: {custom_language}")
        
        return True, None, validated_data
    
    @staticmethod
    def validate_language_code(language: str) -> bool:
        """
        Validate language code.
        
        Args:
            language: Language code to validate
            
        Returns:
            True if valid, False otherwise
        """
        from config import LANGUAGE_MAP
        return language in LANGUAGE_MAP or language == 'other'
    
    @staticmethod
    def get_validation_error_message(field: str) -> str:
        """
        Get user-friendly error message for validation failures.
        
        Args:
            field: Field name that failed validation
            
        Returns:
            Error message string
        """
        messages = {
            'topic': 'Meeting Topic is required',
            'language': 'Conversation Language is required',
            'custom_language': 'Please specify the custom language',
            'audio_file': 'No audio file provided'
        }
        
        return messages.get(field, f'{field} validation failed')

