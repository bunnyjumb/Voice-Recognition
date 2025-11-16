"""
Vietnamese Post-Processing Module
Handles post-processing of Vietnamese transcriptions to improve accuracy.
Fixes common transcription errors and improves text quality.
"""
import re
from typing import List, Tuple


class VietnamesePostProcessor:
    """
    Post-processor for Vietnamese transcriptions.
    Fixes common errors and improves text quality.
    """
    
    # Common Vietnamese word corrections (transcription errors -> correct form)
    # These are common mistakes made by Whisper when transcribing Vietnamese
    COMMON_CORRECTIONS = {
        # Common mispronunciations/transcription errors
        'được': ['được', 'đươc', 'đươc', 'đươc'],
        'không': ['không', 'khong', 'không'],
        'với': ['với', 'voi', 'vơi'],
        'này': ['này', 'nay', 'nay'],
        'đó': ['đó', 'do', 'do'],
        'của': ['của', 'cua', 'cua'],
        'trong': ['trong', 'trong'],
        'nhưng': ['nhưng', 'nhung', 'nhung'],
        'khi': ['khi', 'khi'],
        'nếu': ['nếu', 'neu', 'neu'],
        'thì': ['thì', 'thi', 'thi'],
        'và': ['và', 'va', 'va'],
        'hoặc': ['hoặc', 'hoac', 'hoac'],
        'để': ['để', 'de', 'de'],
        'mà': ['mà', 'ma', 'ma'],
        'nên': ['nên', 'nen', 'nen'],
        'vì': ['vì', 'vi', 'vi'],
        'đã': ['đã', 'da', 'da'],
        'sẽ': ['sẽ', 'se', 'se'],                           
        'đang': ['đang', 'dang', 'dang'],
        'có': ['có', 'co', 'co'],
        'là': ['là', 'la', 'la'],
        'một': ['một', 'mot', 'mot'],
        'hai': ['hai', 'hai'],
        'ba': ['ba', 'ba'],
        'bốn': ['bốn', 'bon', 'bon'],
        'năm': ['năm', 'nam', 'nam'],
        'sáu': ['sáu', 'sau', 'sau'],
        'bảy': ['bảy', 'bay', 'bay'],
        'tám': ['tám', 'tam', 'tam'],
        'chín': ['chín', 'chin', 'chin'],
        'mười': ['mười', 'muoi', 'muoi'],
    }
    
    # Common phrase patterns to fix
    PHRASE_PATTERNS = [
        # Fix spacing issues
        (r'\s+', ' '),  # Multiple spaces to single space
        (r'\s+([.,!?;:])', r'\1'),  # Remove space before punctuation
        (r'([.,!?;:])\s*([A-Za-zÀ-ỹ])', r'\1 \2'),  # Add space after punctuation
        # Fix common Vietnamese-specific issues
        (r'\bkhông\s+phải\b', 'không phải'),
        (r'\bđược\s+rồi\b', 'được rồi'),
        (r'\bcảm\s+ơn\b', 'cảm ơn'),
        (r'\bxin\s+chào\b', 'xin chào'),
        (r'\btạm\s+biệt\b', 'tạm biệt'),
    ]
    
    def __init__(self):
        """Initialize VietnamesePostProcessor."""
        # Compile regex patterns for better performance
        self.compiled_patterns = [
            (re.compile(pattern), replacement)
            for pattern, replacement in self.PHRASE_PATTERNS
        ]
    
    def post_process(self, text: str) -> str:
        """
        Post-process Vietnamese transcription text.
        
        Args:
            text: Raw transcription text from Whisper
            
        Returns:
            Post-processed text with improved accuracy
        """
        if not text or not text.strip():
            return text
        
        # Step 1: Normalize whitespace
        text = ' '.join(text.split())
        
        # Step 2: Apply phrase pattern corrections
        for pattern, replacement in self.compiled_patterns:
            text = pattern.sub(replacement, text)
        
        # Step 3: Capitalize first letter of sentences
        sentences = re.split(r'([.!?]\s+)', text)
        processed_sentences = []
        for i, sentence in enumerate(sentences):
            if sentence.strip() and not re.match(r'^[.!?]\s+$', sentence):
                # Capitalize first letter if it's the start or after punctuation
                if i == 0 or (i > 0 and re.match(r'^[.!?]\s+$', sentences[i-1])):
                    sentence = sentence[0].upper() + sentence[1:] if len(sentence) > 0 else sentence
            processed_sentences.append(sentence)
        text = ''.join(processed_sentences)
        
        # Step 4: Final cleanup
        text = text.strip()
        
        return text
    
    def fix_common_errors(self, text: str) -> str:
        """
        Fix common transcription errors in Vietnamese text.
        
        Args:
            text: Text with potential errors
            
        Returns:
            Text with common errors fixed
        """
        # This is a simplified version - in production, you might want to use
        # a more sophisticated approach with a Vietnamese dictionary or NLP library
        words = text.split()
        corrected_words = []
        
        for word in words:
            # Check if word needs correction
            word_lower = word.lower()
            if word_lower in self.COMMON_CORRECTIONS:
                # Use the first (correct) form
                corrected_word = self.COMMON_CORRECTIONS[word_lower][0]
                # Preserve original capitalization
                if word[0].isupper():
                    corrected_word = corrected_word.capitalize()
                corrected_words.append(corrected_word)
            else:
                corrected_words.append(word)
        
        return ' '.join(corrected_words)

