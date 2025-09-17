"""
Chunk utilities for RAG.
Handles text splitting with configurable overlap and boundary respect.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .config import CrawlerConfig
from .utils.text import estimate_tokens, split_into_sentences, split_into_paragraphs

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """A chunk of text with metadata."""
    id: str
    content: str
    token_count: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'content': self.content,
            'token_count': self.token_count,
            'start_char': self.start_char,
            'end_char': self.end_char,
            'metadata': self.metadata
        }


class TextChunker:
    """
    Chunks text for RAG applications with configurable strategies.
    """
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.chunk_size = config.rag.chunk_size_tokens
        self.overlap_size = config.rag.chunk_overlap_tokens
        self.respect_boundaries = config.rag.respect_boundaries
        self.include_metadata = config.rag.include_metadata
        
    def chunk_document(self, content: str, document_metadata: Dict[str, Any] = None) -> List[TextChunk]:
        """
        Chunk a document into smaller pieces for RAG.
        
        Args:
            content: The text content to chunk
            document_metadata: Metadata about the source document
            
        Returns:
            List of TextChunk objects
        """
        if not content or not content.strip():
            return []
            
        document_metadata = document_metadata or {}
        
        if self.respect_boundaries:
            return self._chunk_with_boundaries(content, document_metadata)
        else:
            return self._chunk_fixed_size(content, document_metadata)
            
    def _chunk_with_boundaries(self, content: str, document_metadata: Dict[str, Any]) -> List[TextChunk]:
        """
        Chunk text respecting paragraph and sentence boundaries.
        """
        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_id = 0
        
        # First try to split by paragraphs
        paragraphs = split_into_paragraphs(content)
        
        if not paragraphs:
            # If no paragraphs found, treat as single paragraph
            paragraphs = [content]
            
        for paragraph in paragraphs:
            paragraph_tokens = estimate_tokens(paragraph)
            
            # If single paragraph is too big, need to split it
            if paragraph_tokens > self.chunk_size:
                # Try to finish current chunk first
                if current_chunk:
                    chunk = self._create_chunk(
                        chunk_id, current_chunk, current_start, 
                        current_start + len(current_chunk), document_metadata
                    )
                    chunks.append(chunk)
                    chunk_id += 1
                    current_chunk = ""
                    
                # Split the large paragraph
                para_chunks = self._split_large_paragraph(paragraph, current_start + len(current_chunk), document_metadata, chunk_id)
                chunks.extend(para_chunks)
                chunk_id += len(para_chunks)
                current_start = chunks[-1].end_char if chunks else 0
                
            else:
                # Check if adding this paragraph would exceed chunk size
                test_chunk = current_chunk + "\n\n" + paragraph if current_chunk else paragraph
                test_tokens = estimate_tokens(test_chunk)
                
                if test_tokens <= self.chunk_size:
                    # Add to current chunk
                    if current_chunk:
                        current_chunk += "\n\n" + paragraph
                    else:
                        current_chunk = paragraph
                        current_start = self._find_content_start(content, paragraph)
                else:
                    # Finish current chunk and start new one
                    if current_chunk:
                        chunk = self._create_chunk(
                            chunk_id, current_chunk, current_start,
                            current_start + len(current_chunk), document_metadata
                        )
                        chunks.append(chunk)
                        chunk_id += 1
                        
                    # Start new chunk with this paragraph
                    current_chunk = paragraph
                    current_start = self._find_content_start(content, paragraph)
                    
        # Don't forget the last chunk
        if current_chunk:
            chunk = self._create_chunk(
                chunk_id, current_chunk, current_start,
                current_start + len(current_chunk), document_metadata
            )
            chunks.append(chunk)
            
        return self._add_overlap(chunks, content)
        
    def _chunk_fixed_size(self, content: str, document_metadata: Dict[str, Any]) -> List[TextChunk]:
        """
        Chunk text using fixed token sizes without respecting boundaries.
        """
        chunks = []
        chunk_id = 0
        
        # Estimate characters per token for this content
        total_tokens = estimate_tokens(content)
        chars_per_token = len(content) / max(total_tokens, 1)
        
        # Calculate character-based chunk size
        chunk_chars = int(self.chunk_size * chars_per_token)
        overlap_chars = int(self.overlap_size * chars_per_token)
        
        start = 0
        while start < len(content):
            end = min(start + chunk_chars, len(content))
            
            # Try to break at word boundary
            if end < len(content):
                # Look back for space
                space_pos = content.rfind(' ', start, end)
                if space_pos > start + chunk_chars * 0.8:  # Don't go too far back
                    end = space_pos
                    
            chunk_content = content[start:end].strip()
            
            if chunk_content:
                chunk = self._create_chunk(chunk_id, chunk_content, start, end, document_metadata)
                chunks.append(chunk)
                chunk_id += 1
                
            # Move start forward with overlap
            start = max(start + 1, end - overlap_chars)
            
        return chunks
        
    def _split_large_paragraph(self, paragraph: str, start_offset: int, 
                             document_metadata: Dict[str, Any], start_chunk_id: int) -> List[TextChunk]:
        """
        Split a paragraph that's too large into smaller chunks.
        """
        chunks = []
        chunk_id = start_chunk_id
        
        # Try to split by sentences first
        sentences = split_into_sentences(paragraph)
        
        if len(sentences) <= 1:
            # Single sentence or no sentence boundaries, use fixed chunking
            return self._chunk_fixed_size(paragraph, document_metadata)
            
        current_chunk = ""
        current_start = start_offset
        
        for sentence in sentences:
            test_chunk = current_chunk + " " + sentence if current_chunk else sentence
            test_tokens = estimate_tokens(test_chunk)
            
            if test_tokens <= self.chunk_size:
                current_chunk = test_chunk
            else:
                # Finish current chunk
                if current_chunk:
                    chunk = self._create_chunk(
                        chunk_id, current_chunk, current_start,
                        current_start + len(current_chunk), document_metadata
                    )
                    chunks.append(chunk)
                    chunk_id += 1
                    current_start += len(current_chunk) + 1
                    
                # Start new chunk with current sentence
                current_chunk = sentence
                
        # Don't forget the last chunk
        if current_chunk:
            chunk = self._create_chunk(
                chunk_id, current_chunk, current_start,
                current_start + len(current_chunk), document_metadata
            )
            chunks.append(chunk)
            
        return chunks
        
    def _create_chunk(self, chunk_id: int, content: str, start: int, end: int, 
                     document_metadata: Dict[str, Any]) -> TextChunk:
        """Create a TextChunk object with metadata."""
        chunk_metadata = {}
        
        if self.include_metadata and document_metadata:
            # Include relevant document metadata
            chunk_metadata.update({
                'source_url': document_metadata.get('url'),
                'source_title': document_metadata.get('title'),
                'content_type': document_metadata.get('content_type'),
                'language': document_metadata.get('language')
            })
            
        # Add chunk-specific metadata
        chunk_metadata.update({
            'chunk_index': chunk_id,
            'char_start': start,
            'char_end': end,
            'char_length': len(content)
        })
        
        # Try to identify section/heading context
        heading_context = self._extract_heading_context(content)
        if heading_context:
            chunk_metadata['section'] = heading_context
            
        return TextChunk(
            id=f"chunk_{chunk_id}",
            content=content.strip(),
            token_count=estimate_tokens(content),
            start_char=start,
            end_char=end,
            metadata=chunk_metadata
        )
        
    def _add_overlap(self, chunks: List[TextChunk], full_content: str) -> List[TextChunk]:
        """
        Add overlap between chunks by extending their content.
        """
        if len(chunks) <= 1 or self.overlap_size <= 0:
            return chunks
            
        overlapped_chunks = []
        
        for i, chunk in enumerate(chunks):
            content = chunk.content
            start_char = chunk.start_char
            end_char = chunk.end_char
            
            # Add overlap from previous chunk
            if i > 0:
                prev_chunk = chunks[i - 1]
                overlap_chars = int(self.overlap_size * (len(prev_chunk.content) / max(prev_chunk.token_count, 1)))
                
                # Get overlap content from end of previous chunk
                overlap_start = max(0, len(prev_chunk.content) - overlap_chars)
                overlap_content = prev_chunk.content[overlap_start:].strip()
                
                if overlap_content:
                    content = overlap_content + "\n\n" + content
                    
            # Add overlap from next chunk
            if i < len(chunks) - 1:
                next_chunk = chunks[i + 1]
                overlap_chars = int(self.overlap_size * (len(next_chunk.content) / max(next_chunk.token_count, 1)))
                
                # Get overlap content from start of next chunk
                overlap_content = next_chunk.content[:overlap_chars].strip()
                
                if overlap_content:
                    content = content + "\n\n" + overlap_content
                    
            # Create new chunk with overlap
            new_chunk = TextChunk(
                id=chunk.id,
                content=content,
                token_count=estimate_tokens(content),
                start_char=start_char,
                end_char=end_char,
                metadata=chunk.metadata.copy()
            )
            
            # Update metadata to reflect overlap
            new_chunk.metadata['has_overlap'] = i > 0 or i < len(chunks) - 1
            new_chunk.metadata['original_token_count'] = chunk.token_count
            
            overlapped_chunks.append(new_chunk)
            
        return overlapped_chunks
        
    def _find_content_start(self, full_content: str, search_content: str) -> int:
        """Find the starting position of content in the full text."""
        try:
            return full_content.index(search_content)
        except ValueError:
            # Content not found exactly, try first few words
            words = search_content.split()[:5]
            if words:
                search_phrase = ' '.join(words)
                try:
                    return full_content.index(search_phrase)
                except ValueError:
                    pass
        return 0
        
    def _extract_heading_context(self, content: str) -> Optional[str]:
        """
        Try to extract heading/section context from content.
        """
        lines = content.split('\n')
        
        for line in lines[:3]:  # Check first few lines
            line = line.strip()
            
            # Look for heading patterns
            if (len(line) < 100 and  # Not too long
                (line.isupper() or  # ALL CAPS
                 re.match(r'^[A-Z][^.]*$', line) or  # Starts with capital, no periods
                 re.match(r'^\d+\.?\s+[A-Z]', line))):  # Numbered heading
                return line
                
        return None
        
    def get_chunk_summary(self, chunks: List[TextChunk]) -> Dict[str, Any]:
        """
        Get summary statistics for a list of chunks.
        """
        if not chunks:
            return {
                'total_chunks': 0,
                'total_tokens': 0,
                'avg_tokens_per_chunk': 0,
                'min_tokens': 0,
                'max_tokens': 0
            }
            
        token_counts = [chunk.token_count for chunk in chunks]
        
        return {
            'total_chunks': len(chunks),
            'total_tokens': sum(token_counts),
            'avg_tokens_per_chunk': sum(token_counts) / len(token_counts),
            'min_tokens': min(token_counts),
            'max_tokens': max(token_counts),
            'target_chunk_size': self.chunk_size,
            'overlap_size': self.overlap_size
        }
