"""
Text Normalizer Module
Normalizes transcription text to fix capitalization and formatting issues.
Applies to all languages, not just Vietnamese.
Intelligently preserves proper nouns, acronyms, and technical terms.
"""
import re
import logging

logger = logging.getLogger(__name__)


class TextNormalizer:
    """
    Normalizes transcription text to improve quality.
    Fixes common issues like:
    - All caps text (while preserving proper nouns and acronyms)
    - Inconsistent capitalization
    - Sentence capitalization
    - Whitespace issues
    
    Intelligently preserves:
    - Proper nouns (names, places, companies)
    - Acronyms (API, URL, HTTP, etc.)
    - Technical terms
    - Brand names
    """
    
    def __init__(self):
        """Initialize TextNormalizer."""
        # Common acronyms that should stay all caps
        # These are technical terms, abbreviations that are always uppercase
        self.common_acronyms = {
            'API', 'URL', 'HTTP', 'HTTPS', 'HTML', 'CSS', 'JS', 'JSON', 'XML',
            'PDF', 'CSV', 'SQL', 'AWS', 'GCP', 'AI', 'ML', 'DL', 'NLP',
            'CPU', 'GPU', 'RAM', 'SSD', 'HDD', 'USB', 'WiFi', 'VPN',
            'CEO', 'CTO', 'CFO', 'VP', 'PM', 'QA', 'UI', 'UX', 'ID',
            'IP', 'DNS', 'TCP', 'UDP', 'FTP', 'SSH', 'SSL', 'TLS',
            'IDE', 'SDK', 'CLI', 'GUI', 'REST', 'SOAP', 'RPC',
            'iOS', 'Android', 'Windows', 'Linux', 'macOS',
            'NASA', 'FBI', 'CIA', 'UN', 'WHO', 'EU', 'UK', 'USA',
            'GDP', 'KPI', 'ROI', 'SLA', 'SLO', 'MTTR', 'MTBF'
        }
        
        # Common proper nouns patterns (company suffixes, titles)
        self.proper_noun_indicators = [
            r'\b(Mr|Mrs|Ms|Dr|Prof|Sir|Madam)\.\s+[A-Z]',  # Titles before names
            r'\b(Inc|Ltd|Corp|LLC|Co)\.',  # Company suffixes
            r'\b[A-Z][a-z]+\s+(Inc|Ltd|Corp|LLC|Co)\.',  # Company names
        ]
        
        # Compile patterns for performance
        self.proper_noun_patterns = [re.compile(pattern) for pattern in self.proper_noun_indicators]
        
    def _is_likely_proper_noun(self, word: str, context: str = '') -> bool:
        """
        Check if a word is likely a proper noun that should be preserved.
        
        Args:
            word: Word to check
            context: Surrounding context (previous/next words)
            
        Returns:
            True if word should be preserved as-is
        """
        word_clean = re.sub(r'[^\w]', '', word).upper()
        
        # Check if it's a known acronym
        if word_clean in self.common_acronyms:
            return True
        
        # Short words (2-3 chars) that are all caps are likely acronyms
        if len(word_clean) <= 3 and word_clean.isupper() and word_clean.isalpha():
            return True
        
        # Check context for proper noun indicators
        if context:
            for pattern in self.proper_noun_patterns:
                if pattern.search(context):
                    return True
        
        # Words that start with capital and have mixed case are likely proper nouns
        # (already correctly formatted)
        if word and word[0].isupper() and not word.isupper() and not word.islower():
            return True
        
        return False
    
    def _is_likely_transcription_error(self, word: str) -> bool:
        """
        Check if an all-caps word is likely a transcription error.
        
        Args:
            word: Word to check
            
        Returns:
            True if likely an error (should be normalized)
        """
        word_clean = re.sub(r'[^\w]', '', word)
        
        # Very short words (1-2 chars) - likely not errors
        if len(word_clean) <= 2:
            return False
        
        # Known acronyms - not errors
        if word_clean.upper() in self.common_acronyms:
            return False
        
        # Long all-caps words (>5 chars) are more likely to be errors
        # Short ones (3-4 chars) might be acronyms
        if len(word_clean) > 5 and word_clean.isupper() and word_clean.isalpha():
            return True
        
        # Words that are all caps and longer than 3 chars might be errors
        # But we'll be conservative and only fix very long ones
        if len(word_clean) > 6 and word_clean.isupper() and word_clean.isalpha():
            return True
        
        return False
        
    def normalize(self, text: str, language: str = None) -> str:
        """
        Normalize transcription text.
        
        Args:
            text: Raw transcription text
            language: Language code (optional, for language-specific rules)
            
        Returns:
            Normalized text
        """
        if not text or not text.strip():
            return text
        
        # Step 1: Normalize whitespace
        text = ' '.join(text.split())
        
        # Step 2: Fix all caps words (common transcription error)
        # But preserve proper nouns, acronyms, and technical terms
        words = text.split()
        normalized_words = []
        
        for i, word in enumerate(words):
            # Get context (previous and next words)
            prev_word = words[i-1] if i > 0 else ''
            next_word = words[i+1] if i < len(words) - 1 else ''
            context = f"{prev_word} {word} {next_word}"
            
            # Remove punctuation temporarily to check
            word_clean = re.sub(r'[^\w]', '', word)
            
            # Check if it's likely a proper noun or acronym (preserve it)
            if self._is_likely_proper_noun(word, context):
                # Keep as-is (it's a proper noun or acronym)
                normalized_words.append(word)
            elif self._is_likely_transcription_error(word):
                # It's likely a transcription error, convert to proper case
                # Preserve punctuation
                punct_before = re.match(r'^[^\w]*', word).group()
                punct_after = re.search(r'[^\w]*$', word).group()
                word_clean_normalized = word_clean.capitalize()
                normalized_word = punct_before + word_clean_normalized + punct_after
                normalized_words.append(normalized_word)
            else:
                # Keep as-is (already correct or ambiguous)
                normalized_words.append(word)
        
        text = ' '.join(normalized_words)
        
        # Step 3: Fix sentence capitalization
        # Split by sentence endings
        sentences = re.split(r'([.!?]\s+)', text)
        processed_sentences = []
        
        for i, sentence in enumerate(sentences):
            if sentence.strip() and not re.match(r'^[.!?]\s+$', sentence):
                # Check if this is the start of a sentence
                is_sentence_start = (
                    i == 0 or 
                    (i > 0 and re.match(r'^[.!?]\s+$', sentences[i-1]))
                )
                
                if is_sentence_start:
                    # Capitalize first letter of sentence
                    sentence = sentence.strip()
                    if len(sentence) > 0:
                        # Find first letter (skip leading punctuation)
                        first_letter_idx = 0
                        for idx, char in enumerate(sentence):
                            if char.isalpha():
                                first_letter_idx = idx
                                break
                        
                        if first_letter_idx < len(sentence):
                            # Get first word
                            first_word_end = sentence.find(' ', first_letter_idx)
                            if first_word_end == -1:
                                first_word_end = len(sentence)
                            
                            first_word = sentence[first_letter_idx:first_word_end]
                            first_word_clean = re.sub(r'[^\w]', '', first_word)
                            
                            # Only capitalize if it's not already a proper noun or acronym
                            if not self._is_likely_proper_noun(first_word):
                                # Check if it's all lowercase or all uppercase (likely needs fixing)
                                if first_word_clean.islower() or (
                                    first_word_clean.isupper() and 
                                    len(first_word_clean) > 3 and
                                    first_word_clean.upper() not in self.common_acronyms
                                ):
                                    # Capitalize first letter, preserve rest
                                    if len(first_word) > 0:
                                        first_char = first_word[0]
                                        if first_char.isalpha():
                                            first_word = first_char.upper() + first_word[1:]
                            
                            sentence = (
                                sentence[:first_letter_idx] + 
                                first_word + 
                                sentence[first_word_end:]
                            )
                
                processed_sentences.append(sentence)
            else:
                processed_sentences.append(sentence)
        
        text = ''.join(processed_sentences)
        
        # Step 4: Fix common formatting issues
        # Remove space before punctuation
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        # Add space after punctuation if missing
        text = re.sub(r'([.,!?;:])([A-Za-zÀ-ỹ])', r'\1 \2', text)
        
        # Step 5: Normalize multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Step 6: Final trim
        text = text.strip()
        
        return text
    
    def fix_all_caps(self, text: str) -> str:
        """
        Fix all caps words in text (common transcription error).
        Preserves proper nouns and acronyms.
        
        Args:
            text: Text with potential all-caps words
            
        Returns:
            Text with all-caps words converted to proper case (except proper nouns/acronyms)
        """
        if not text:
            return text
        
        words = text.split()
        fixed_words = []
        
        for i, word in enumerate(words):
            # Get context
            prev_word = words[i-1] if i > 0 else ''
            next_word = words[i+1] if i < len(words) - 1 else ''
            context = f"{prev_word} {word} {next_word}"
            
            # Extract word without punctuation
            word_match = re.match(r'^([^\w]*)(\w+)([^\w]*)$', word)
            if word_match:
                punct_before, word_clean, punct_after = word_match.groups()
                
                # Check if it's a proper noun or acronym (preserve it)
                if self._is_likely_proper_noun(word, context):
                    # Keep as-is
                    fixed_words.append(word)
                elif self._is_likely_transcription_error(word):
                    # Convert to proper case
                    word_clean = word_clean.capitalize()
                    fixed_words.append(punct_before + word_clean + punct_after)
                else:
                    # Keep as-is
                    fixed_words.append(word)
            else:
                fixed_words.append(word)
        
        return ' '.join(fixed_words)
    
    def add_acronym(self, acronym: str):
        """
        Add a custom acronym to the preserve list.
        
        Args:
            acronym: Acronym to preserve (will be converted to uppercase)
        """
        self.common_acronyms.add(acronym.upper())
        logger.debug(f"Added acronym to preserve list: {acronym.upper()}")
    
    def add_acronyms(self, acronyms: list):
        """
        Add multiple acronyms to the preserve list.
        
        Args:
            acronyms: List of acronyms to preserve
        """
        for acronym in acronyms:
            self.common_acronyms.add(acronym.upper())
        logger.debug(f"Added {len(acronyms)} acronyms to preserve list")

