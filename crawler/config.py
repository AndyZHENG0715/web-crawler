"""
Configuration models and YAML loader for Policy Address Crawler.
Uses Pydantic for validation and type safety.
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import yaml
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class RateLimits(BaseModel):
    """Rate limiting configuration for polite crawling."""
    per_host_rps: int = 1  # Requests per second per host
    per_host_concurrency: int = 2  # Max concurrent connections per host
    global_concurrency: int = 4  # Max total concurrent connections

class StorageConfig(BaseModel):
    """File storage and output configuration."""
    save_html: bool = True
    save_pdf: bool = True
    output_jsonl: str = "data/processed/documents.jsonl"

class DeduplicationConfig(BaseModel):
    """Deduplication and resume settings."""
    strategy: str = "index"  # "crawl" or "index"
    skip_existing_files: bool = True
    enable_resume: bool = True

class RAGConfig(BaseModel):
    """Retrieval Augmented Generation settings."""
    chunk_size_tokens: int = 1000
    chunk_overlap_tokens: int = 150
    embedding_model: str = "text-embedding-3-large"
    respect_boundaries: bool = True
    include_metadata: bool = True

class OpenAIConfig(BaseModel):
    """OpenAI API configuration."""
    enabled: bool = False
    api_key: Optional[str] = None
    batch_size: int = 100
    max_retries: int = 3
    
    def __init__(self, **data):
        super().__init__(**data)
        # Override with environment variable if available
        if not self.api_key:
            self.api_key = os.getenv("OPENAI_API_KEY")

class PineconeConfig(BaseModel):
    """Pinecone vector database configuration."""
    enabled: bool = False
    api_key: Optional[str] = None
    index_name: str = "policy-address-index"
    dimension: int = 3072  # text-embedding-3-large dimension
    metric: str = "cosine"
    batch_size: int = 100
    
    def __init__(self, **data):
        super().__init__(**data)
        # Override with environment variable if available
        if not self.api_key:
            self.api_key = os.getenv("PINECONE_API_KEY")

class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    file: str = "logs/crawler.log"
    show_progress: bool = True

class CrawlerConfig(BaseModel):
    """Main configuration model for the Policy Address crawler."""
    seeds: List[str]
    allowed_hosts: List[str]
    years: List[int]
    languages: List[str]
    rate_limits: RateLimits
    depth_limit: int = 5
    max_pages: int = 200
    respect_robots_txt: bool = True
    timeouts: Dict[str, int] = {"connect": 10, "read": 30, "write": 5, "pool": 5}
    retries: int = 3
    user_agent: str = "PolicyCrawler/1.0"
    storage: StorageConfig
    prefer_pdf_over_html: bool = True
    deduplication: DeduplicationConfig = DeduplicationConfig()
    rag: RAGConfig
    openai: OpenAIConfig
    pinecone: PineconeConfig
    logging: LoggingConfig = LoggingConfig()


def load_config(path: str) -> CrawlerConfig:
    """
    Load configuration from YAML file.
    
    Args:
        path: Path to the YAML configuration file
        
    Returns:
        CrawlerConfig: Validated configuration object
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML is malformed
        pydantic.ValidationError: If config values are invalid
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
        
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    return CrawlerConfig(**data)
