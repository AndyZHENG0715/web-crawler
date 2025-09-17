"""
Simple token counting utilities.
Provides estimates for OpenAI token usage without requiring tiktoken.
"""

import re
from typing import List


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    
    This is a rough approximation based on the rule of thumb that
    1 token ≈ 4 characters in English text for OpenAI models.
    For more precise counting, use tiktoken library with specific model.
    
    Args:
        text: Input text to count tokens for
        
    Returns:
        Estimated number of tokens
    """
    if not text:
        return 0
        
    # Basic character count estimation
    # OpenAI models typically use ~4 characters per token for English
    char_count = len(text)
    basic_estimate = char_count / 4
    
    # Adjust for word boundaries and punctuation
    # More spaces and punctuation typically mean more tokens
    word_count = len(text.split())
    if word_count > 0:
        avg_word_length = char_count / word_count
        if avg_word_length < 4:  # Short words = more tokens
            basic_estimate *= 1.2
        elif avg_word_length > 8:  # Long words = fewer tokens
            basic_estimate *= 0.9
            
    return int(basic_estimate)


def estimate_tokens_precise(text: str, model: str = "gpt-3.5-turbo") -> int:
    """
    More precise token counting using tiktoken if available.
    Falls back to estimate_tokens if tiktoken is not installed.
    
    Args:
        text: Input text to count tokens for
        model: Model name for tokenizer selection
        
    Returns:
        Number of tokens
    """
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except ImportError:
        # tiktoken not available, use estimation
        return estimate_tokens(text)
    except Exception:
        # Fallback for any tiktoken errors
        return estimate_tokens(text)


def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences using simple heuristics.
    
    Args:
        text: Input text to split
        
    Returns:
        List of sentences
    """
    if not text:
        return []
        
    # Simple sentence splitting - can be improved with NLTK or spaCy
    # This handles basic cases for English text
    sentences = re.split(r'[.!?]+\s+', text)
    
    # Clean up sentences
    cleaned_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if sentence and len(sentence) > 5:  # Skip very short fragments
            # Ensure sentence ends with punctuation
            if not sentence[-1] in '.!?':
                sentence += '.'
            cleaned_sentences.append(sentence)
            
    return cleaned_sentences


def split_into_paragraphs(text: str) -> List[str]:
    """
    Split text into paragraphs.
    
    Args:
        text: Input text to split
        
    Returns:
        List of paragraphs
    """
    if not text:
        return []
        
    # Split on double newlines
    paragraphs = re.split(r'\n\s*\n', text)
    
    # Clean up paragraphs
    cleaned_paragraphs = []
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if paragraph and len(paragraph) > 10:  # Skip very short fragments
            cleaned_paragraphs.append(paragraph)
            
    return cleaned_paragraphs


def truncate_to_tokens(text: str, max_tokens: int, model: str = "gpt-3.5-turbo") -> str:
    """
    Truncate text to approximately max_tokens.
    
    Args:
        text: Input text to truncate
        max_tokens: Maximum number of tokens
        model: Model for precise token counting
        
    Returns:
        Truncated text
    """
    if not text:
        return text
        
    current_tokens = estimate_tokens_precise(text, model)
    
    if current_tokens <= max_tokens:
        return text
        
    # Estimate how much to cut
    ratio = max_tokens / current_tokens
    target_chars = int(len(text) * ratio * 0.9)  # Be conservative
    
    # Truncate at word boundary
    truncated = text[:target_chars]
    last_space = truncated.rfind(' ')
    if last_space > target_chars * 0.8:  # Don't cut too much
        truncated = truncated[:last_space]
        
    # Verify we're under the limit
    if estimate_tokens_precise(truncated, model) > max_tokens:
        # Try sentence boundary
        sentences = split_into_sentences(truncated)
        while sentences and estimate_tokens_precise(' '.join(sentences), model) > max_tokens:
            sentences.pop()
        truncated = ' '.join(sentences)
        
    return truncated


def clean_whitespace(text: str) -> str:
    """
    Clean up whitespace in text.
    
    Args:
        text: Input text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return text
        
    # Normalize newlines
    text = re.sub(r'\r\n|\r', '\n', text)
    
    # Replace multiple spaces with single space
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Replace multiple newlines with double newline (paragraph break)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    
    # Trim lines
    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    return text.strip()


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """
    Extract simple keywords from text.
    This is a basic implementation - for production use, consider
    more sophisticated NLP libraries like NLTK, spaCy, or transformers.
    
    Args:
        text: Input text to extract keywords from
        max_keywords: Maximum number of keywords to return
        
    Returns:
        List of keywords
    """
    if not text:
        return []
        
    # Simple keyword extraction
    # Convert to lowercase and split into words
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    
    # Common English stop words to filter out
    stop_words = {
        'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before',
        'after', 'above', 'below', 'between', 'among', 'this', 'that', 'these',
        'those', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have',
        'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
        'may', 'might', 'must', 'can', 'shall', 'a', 'an', 'the', 'it', 'its',
        'they', 'them', 'their', 'we', 'us', 'our', 'you', 'your', 'he', 'him',
        'his', 'she', 'her', 'hers', 'what', 'which', 'who', 'when', 'where',
        'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most',
        'other', 'some', 'such', 'only', 'own', 'same', 'so', 'than', 'too',
        'very', 'just', 'now', 'here', 'there', 'then', 'also', 'well', 'even'
    }
    
    # Filter stop words and count frequency
    word_freq = {}
    for word in words:
        if word not in stop_words and len(word) > 3:
            word_freq[word] = word_freq.get(word, 0) + 1
            
    # Sort by frequency and return top keywords
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    keywords = [word for word, freq in sorted_words[:max_keywords]]
    
    return keywords
