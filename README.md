# Hong Kong Policy Address Web Crawler

A configurable web crawler focused on extracting content from the Hong Kong Chief Executive's Policy Address (2023–2025), with extensibility for other domains and RAG (Retrieval Augmented Generation) capabilities using Pinecone and OpenAI embeddings.

## 🎯 Project Overview

This crawler is designed to:
- **Target**: Hong Kong Policy Address documents from recent years
- **Extract**: Both HTML pages and PDF documents with intelligent deduplication
- **Process**: Content into chunks suitable for RAG applications
- **Store**: Documents in JSONL format with optional vector embeddings
- **Scale**: Extensible architecture for other government documents and domains

## 🏗️ Architecture

```
├── main.py                 # Entry point - orchestrates crawling and indexing
├── configs/
│   ├── config.example.yaml # Full configuration with detailed comments
│   └── config.yaml         # Your custom config (copy from example)
├── crawler/
│   ├── config.py          # Pydantic models for configuration
│   ├── frontier.py        # URL queue with per-host rate limiting
│   ├── fetcher.py         # HTTP client with retries and timeouts
│   ├── policy_address.py  # Site-specific traversal logic
│   ├── parsers.py         # HTML/PDF content extraction
│   ├── chunker.py         # Text chunking for RAG
│   ├── indexer.py         # Document processing and vector storage
│   └── utils/text.py      # Token counting utilities
├── data/
│   ├── raw/              # Saved HTML and PDF files
│   └── processed/        # JSONL output files
└── logs/                 # Crawler logs
```

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Clone or navigate to project directory
cd crawler-project

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows Command Prompt:
.venv\Scripts\activate.bat
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**⚠️ Important**: Always activate the virtual environment before running the crawler! If you get import errors like "No module named 'rich'" or "No module named 'yaml'", you're likely not using the virtual environment.

### Quick Test
```bash
# Test that everything is working (with virtual environment activated)
python verify_setup.py  # Check all dependencies
python main.py --dry-run  # Validate configuration
```

### 2. Configuration

```bash
# Copy example configuration
copy configs\config.example.yaml configs\config.yaml

# Copy environment template
copy .env.example .env
```

Edit `configs/config.yaml` to customize:
- **Years**: Which policy address years to crawl
- **Rate limits**: How fast/polite to crawl (start with defaults)
- **Storage**: What to save (HTML, PDF, both)
- **RAG settings**: Chunk sizes and embedding preferences

### 3. API Keys (Optional)

If you want to use OpenAI embeddings or Pinecone vector storage, edit `.env`:

```env
OPENAI_API_KEY=sk-your-openai-api-key-here
PINECONE_API_KEY=your-pinecone-api-key-here
```

Then enable in `configs/config.yaml`:
```yaml
openai:
  enabled: true

pinecone:
  enabled: true
  index_name: "policy-address-index"  # Create this in Pinecone dashboard
```

### 4. Run the Crawler

**Make sure your virtual environment is activated first!**

```bash
# Windows PowerShell (recommended):
.venv\Scripts\Activate.ps1
python main.py --config configs/config.yaml

# Windows Command Prompt:
.venv\Scripts\activate.bat
python main.py --config configs/config.yaml

# Or use the convenience script:
run_crawler.bat --dry-run
```

## 📋 Key Features

### Intelligent Deduplication
- **Content-based**: Uses hashes to detect identical content across different URLs
- **Configurable preference**: Choose HTML vs PDF when both contain same content
- **Resume capability**: Skip already-processed files on restart

### Polite Crawling
- **Rate limiting**: Configurable requests per second per host
- **Concurrency control**: Limit simultaneous connections
- **Robots.txt respect**: Optional compliance with site policies
- **Timeouts & retries**: Robust error handling

### RAG-Ready Output
- **Chunking**: Intelligent text splitting with configurable overlap
- **Metadata**: Preserves document structure, page numbers, sections
- **Embeddings**: Optional OpenAI integration for vector generation
- **Vector storage**: Optional Pinecone integration for similarity search

## ⚙️ Configuration Guide

### Basic Settings

```yaml
# Target specific years
years: [2023, 2024, 2025]

# Control crawling speed (be polite!)
rate_limits:
  per_host_rps: 1          # 1 request per second (conservative)
  per_host_concurrency: 2  # Max 2 simultaneous connections
  global_concurrency: 4    # Max 4 total connections

# Set boundaries
depth_limit: 5             # How deep to follow links
max_pages: 200            # Safety limit for total pages
```

### RAG Configuration

```yaml
rag:
  chunk_size_tokens: 1000    # ~750 words per chunk
  chunk_overlap_tokens: 150  # ~110 words overlap
  embedding_model: "text-embedding-3-large"  # Best quality
  respect_boundaries: true   # Don't split across document sections
  include_metadata: true     # Include page numbers, headings, etc.
```

### Advanced Options

See `configs/config.example.yaml` for full documentation of all available options.

## 📊 Output Format

### JSONL Documents
Each line in `data/processed/documents.jsonl` contains:

```json
{
  "url": "https://www.policyaddress.gov.hk/2024/en/policy.html",
  "title": "Policy Address 2024 - Chapter 1",
  "content": "The full extracted text content...",
  "content_hash": "sha256:abc123...",
  "content_type": "text/html",
  "metadata": {
    "year": 2024,
    "language": "en",
    "page_number": 1,
    "section": "Introduction",
    "file_path": "data/raw/2024_en_policy_p1.html"
  },
  "chunks": [
    {
      "id": "chunk_0",
      "content": "First chunk of content...",
      "token_count": 1000,
      "start_char": 0,
      "end_char": 750,
      "embedding": [0.1, 0.2, ...]  // Optional: if OpenAI enabled
    }
  ],
  "crawled_at": "2025-09-17T10:30:00Z"
}
```

## 🔧 Development

### Project Structure Explained

- **`main.py`**: Orchestrates the entire process - configuration loading, crawling, and indexing
- **`crawler/config.py`**: Type-safe configuration with Pydantic validation
- **`crawler/frontier.py`**: URL queue management with per-host politeness
- **`crawler/fetcher.py`**: HTTP client wrapper with retry logic and timeout handling
- **`crawler/policy_address.py`**: Site-specific logic for navigating Policy Address pages
- **`crawler/parsers.py`**: Content extraction from HTML and PDF files
- **`crawler/chunker.py`**: Text processing for RAG applications
- **`crawler/indexer.py`**: Document processing and optional vector storage

### Extending to Other Sites

1. **Create site-specific module**: Copy `policy_address.py` as template
2. **Add traversal logic**: Implement site navigation rules
3. **Configure seeds**: Add starting URLs to config
4. **Test with limits**: Use small `max_pages` for initial testing

### Contributing

1. **Follow the existing patterns**: Each module has clear responsibilities
2. **Add comprehensive logging**: Use the configured logger for debugging
3. **Test with small datasets**: Always test with `max_pages: 10` first
4. **Update documentation**: Keep README and config comments current

## 🐛 Troubleshooting

### Common Issues

**Import Errors**
```bash
# Ensure virtual environment is activated
.venv\Scripts\activate  # Windows
# Install dependencies
pip install -r requirements.txt
```

### Common Issues

**Import Errors (`No module named 'rich'`, `No module named 'yaml'`, etc.)**
```bash
# Make sure you're using the virtual environment:
.venv\Scripts\Activate.ps1  # PowerShell
# OR
.venv\Scripts\activate.bat  # Command Prompt

# Verify you're in the right environment:
python -c "import sys; print(sys.executable)"
# Should show: D:\Dev\Crawler\.venv\Scripts\python.exe

# If packages are missing, reinstall:
pip install -r requirements.txt
```

**lxml Compilation Errors**
```bash
# Use pre-compiled wheel
pip install lxml --only-binary=:all:
```

**Rate Limiting / Blocked**
- Increase delays in `rate_limits.per_host_rps` (lower = slower)
- Check `user_agent` string isn't blocked
- Verify `respect_robots_txt: true` if site requires it

**Large Memory Usage**
- Reduce `rag.chunk_size_tokens`
- Lower `rate_limits.global_concurrency`
- Enable `deduplication.skip_existing_files: true`

**Pinecone Connection Issues**
- Verify API key in `.env`
- Check index exists in Pinecone dashboard
- Ensure `dimension: 3072` matches embedding model

### Logs and Debugging

- **Logs**: Check `logs/crawler.log` for detailed execution info
- **Progress**: Enable `logging.show_progress: true` for visual feedback
- **Verbose mode**: Set `logging.level: "DEBUG"` for maximum detail

## 📝 License

This project is open source. Please respect the websites you crawl and follow their robots.txt and terms of service.

## 🤝 Support

For questions about:
- **Configuration**: Check the detailed comments in `configs/config.example.yaml`
- **API integration**: Refer to OpenAI and Pinecone documentation
- **Site-specific issues**: Review the `crawler/policy_address.py` implementation

Happy crawling! 🕷️