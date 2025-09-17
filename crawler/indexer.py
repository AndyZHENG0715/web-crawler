"""
Local JSONL indexer, OpenAI embeddings, Pinecone upsert hooks.
Processes documents into chunks and optionally generates embeddings and stores in vector DB.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import uuid

from .config import CrawlerConfig
from .parsers import ParsedDocument
from .chunker import TextChunker, TextChunk

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generates embeddings using OpenAI API."""
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.client = None
        
    async def __aenter__(self):
        if self.config.openai.enabled:
            try:
                import openai
                self.client = openai.AsyncOpenAI(
                    api_key=self.config.openai.api_key,
                    max_retries=self.config.openai.max_retries
                )
                logger.info(f"OpenAI client initialized with model {self.config.rag.embedding_model}")
            except ImportError:
                logger.error("OpenAI library not available, embeddings disabled")
                self.client = None
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.client = None
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.close()
            
    async def generate_embeddings(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (or None for failures)
        """
        if not self.client or not texts:
            return [None] * len(texts)
            
        try:
            # Process in batches to respect API limits
            batch_size = self.config.openai.batch_size
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_embeddings = await self._generate_batch(batch)
                all_embeddings.extend(batch_embeddings)
                
                # Rate limiting between batches
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.1)  # Small delay between batches
                    
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            return [None] * len(texts)
            
    async def _generate_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings for a single batch."""
        try:
            response = await self.client.embeddings.create(
                model=self.config.rag.embedding_model,
                input=texts
            )
            
            embeddings = []
            for i, embedding_obj in enumerate(response.data):
                embeddings.append(embedding_obj.embedding)
                
            logger.debug(f"Generated {len(embeddings)} embeddings")
            return embeddings
            
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            return [None] * len(texts)


class PineconeUploader:
    """Uploads vectors to Pinecone vector database."""
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.index = None
        
    async def __aenter__(self):
        if self.config.pinecone.enabled:
            try:
                from pinecone import Pinecone
                
                pc = Pinecone(api_key=self.config.pinecone.api_key)
                self.index = pc.Index(self.config.pinecone.index_name)
                
                # Verify index exists and has correct dimensions
                stats = self.index.describe_index_stats()
                logger.info(f"Connected to Pinecone index: {self.config.pinecone.index_name}")
                logger.debug(f"Index stats: {stats}")
                
            except ImportError:
                logger.error("Pinecone library not available, vector storage disabled")
                self.index = None
            except Exception as e:
                logger.error(f"Failed to connect to Pinecone: {e}")
                self.index = None
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Pinecone client doesn't need explicit closing
        pass
        
    async def upsert_vectors(self, vectors: List[Dict[str, Any]]) -> bool:
        """
        Upsert vectors to Pinecone.
        
        Args:
            vectors: List of vector dictionaries with 'id', 'values', and 'metadata'
            
        Returns:
            True if successful, False otherwise
        """
        if not self.index or not vectors:
            return False
            
        try:
            # Process in batches
            batch_size = self.config.pinecone.batch_size
            
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                
                # Convert to Pinecone format
                pinecone_vectors = []
                for vector in batch:
                    pinecone_vectors.append({
                        'id': vector['id'],
                        'values': vector['values'],
                        'metadata': vector.get('metadata', {})
                    })
                    
                # Upsert batch
                self.index.upsert(vectors=pinecone_vectors)
                logger.debug(f"Upserted batch of {len(batch)} vectors")
                
                # Small delay between batches
                if i + batch_size < len(vectors):
                    await asyncio.sleep(0.1)
                    
            logger.info(f"Successfully upserted {len(vectors)} vectors to Pinecone")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upsert vectors to Pinecone: {e}")
            return False


class DocumentIndexer:
    """
    Main document indexer that processes documents into chunks,
    generates embeddings, and stores in various formats.
    """
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.chunker = TextChunker(config)
        
    async def index_documents(self, documents: List[ParsedDocument]) -> Dict[str, Any]:
        """
        Index a list of documents.
        
        Args:
            documents: List of parsed documents to index
            
        Returns:
            Dictionary with indexing statistics
        """
        if not documents:
            logger.warning("No documents to index")
            return {'total_documents': 0, 'total_chunks': 0}
            
        logger.info(f"Starting indexing of {len(documents)} documents")
        start_time = time.time()
        
        # Process documents into chunks
        all_chunks = []
        for doc in documents:
            chunks = self._process_document(doc)
            all_chunks.extend(chunks)
            
        logger.info(f"Generated {len(all_chunks)} chunks from {len(documents)} documents")
        
        # Generate embeddings if enabled
        embeddings = []
        if self.config.openai.enabled:
            async with EmbeddingGenerator(self.config) as embedding_gen:
                chunk_texts = [chunk.content for chunk in all_chunks]
                embeddings = await embedding_gen.generate_embeddings(chunk_texts)
        else:
            embeddings = [None] * len(all_chunks)
            
        # Create final chunk records
        chunk_records = []
        for chunk, embedding in zip(all_chunks, embeddings):
            record = self._create_chunk_record(chunk, embedding)
            chunk_records.append(record)
            
        # Save to JSONL
        jsonl_path = Path(self.config.storage.output_jsonl)
        self._save_to_jsonl(chunk_records, jsonl_path)
        
        # Upload to Pinecone if enabled
        pinecone_success = False
        if self.config.pinecone.enabled and any(r.get('embedding') for r in chunk_records):
            async with PineconeUploader(self.config) as uploader:
                vectors = self._prepare_vectors_for_pinecone(chunk_records)
                pinecone_success = await uploader.upsert_vectors(vectors)
                
        # Calculate statistics
        elapsed_time = time.time() - start_time
        stats = {
            'total_documents': len(documents),
            'total_chunks': len(all_chunks),
            'chunks_with_embeddings': sum(1 for e in embeddings if e is not None),
            'jsonl_path': str(jsonl_path),
            'pinecone_upload': pinecone_success,
            'processing_time_seconds': elapsed_time
        }
        
        logger.info(f"Indexing complete: {stats}")
        return stats
        
    def _process_document(self, document: ParsedDocument) -> List[TextChunk]:
        """Process a single document into chunks."""
        try:
            # Prepare document metadata for chunks
            doc_metadata = {
                'url': document.url,
                'title': document.title,
                'content_type': document.content_type,
                'content_hash': document.content_hash
            }
            doc_metadata.update(document.metadata)
            
            # Generate chunks
            chunks = self.chunker.chunk_document(document.content, doc_metadata)
            
            logger.debug(f"Document '{document.title}' -> {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to process document {document.url}: {e}")
            return []
            
    def _create_chunk_record(self, chunk: TextChunk, embedding: Optional[List[float]]) -> Dict[str, Any]:
        """Create a complete chunk record for storage."""
        record = chunk.to_dict()
        
        # Add embedding if available
        if embedding:
            record['embedding'] = embedding
            record['embedding_model'] = self.config.rag.embedding_model
            
        # Add indexing metadata
        record['indexed_at'] = time.time()
        record['chunker_config'] = {
            'chunk_size_tokens': self.config.rag.chunk_size_tokens,
            'overlap_tokens': self.config.rag.chunk_overlap_tokens,
            'respect_boundaries': self.config.rag.respect_boundaries
        }
        
        return record
        
    def _save_to_jsonl(self, records: List[Dict[str, Any]], output_path: Path):
        """Save chunk records to JSONL file."""
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                for record in records:
                    json.dump(record, f, ensure_ascii=False)
                    f.write('\n')
                    
            logger.info(f"Saved {len(records)} chunk records to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save JSONL to {output_path}: {e}")
            
    def _prepare_vectors_for_pinecone(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prepare chunk records for Pinecone upload."""
        vectors = []
        
        for record in records:
            if record.get('embedding'):
                # Create vector ID
                vector_id = record.get('id', str(uuid.uuid4()))
                
                # Prepare metadata (Pinecone has size limits)
                metadata = {
                    'chunk_id': record.get('id'),
                    'source_url': record.get('metadata', {}).get('source_url', ''),
                    'source_title': record.get('metadata', {}).get('source_title', ''),
                    'content_type': record.get('metadata', {}).get('content_type', ''),
                    'chunk_index': record.get('metadata', {}).get('chunk_index', 0),
                    'token_count': record.get('token_count', 0),
                    'char_length': record.get('metadata', {}).get('char_length', 0)
                }
                
                # Add section info if available
                section = record.get('metadata', {}).get('section')
                if section:
                    metadata['section'] = section[:100]  # Truncate long sections
                    
                # Truncate content for metadata (Pinecone metadata size limits)
                content = record.get('content', '')
                if len(content) > 500:
                    metadata['content_preview'] = content[:500] + '...'
                else:
                    metadata['content_preview'] = content
                    
                vectors.append({
                    'id': vector_id,
                    'values': record['embedding'],
                    'metadata': metadata
                })
                
        return vectors


async def index_documents(config: CrawlerConfig, documents: Optional[List[ParsedDocument]] = None) -> Dict[str, Any]:
    """
    Main entry point for document indexing.
    
    Args:
        config: Crawler configuration
        documents: Optional list of documents to index. If None, will load from crawl results.
        
    Returns:
        Dictionary with indexing statistics
    """
    indexer = DocumentIndexer(config)
    
    # If no documents provided, try to load from a previous crawl
    if documents is None:
        logger.warning("No documents provided for indexing")
        return {'error': 'No documents to index'}
        
    return await indexer.index_documents(documents)
