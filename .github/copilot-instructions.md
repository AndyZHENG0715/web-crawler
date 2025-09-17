# Copilot Instructions for Web Crawler Project

This file tracks the systematic setup and development of the Hong Kong Policy Address web crawler project. Each checklist item below will be updated as completed.

## Checklist

- [x] Scaffold Python web crawler project
- [x] Customize config and example files
- [x] Verify requirements and install dependencies
- [x] Add README and documentation

## Project Overview

- Python web crawler focused on Hong Kong Chief Executive’s Policy Address (2023–2025)
- Extensible to other domains and RAG (Pinecone + embeddings)
- Architecture: modular, configurable, YAML settings, .env for API keys
- Key dependencies: httpx, BeautifulSoup, lxml, pypdf, pdfminer.six, PyYAML, pydantic, python-dotenv, yarl, rich/tqdm, OpenAI SDK, pinecone-client
- Project structure: main.py, configs/, crawler/, data/raw/, data/processed/

## Execution Guidelines
- Use '.' as the working directory
- Only install extensions if specified
- Avoid verbose explanations
- Mark each checklist item as completed when done

## Implementation Notes

### Configuration Strategy
- Industry-standard defaults with comprehensive comments
- Separate YAML for settings, .env for secrets
- Pydantic validation for type safety
- Modular config sections (rate limits, storage, RAG, APIs)

### Key Design Decisions
1. **Deduplication**: Index-time strategy (crawl everything, dedupe during processing)
2. **Rate Limiting**: Conservative defaults (1 RPS per host, 2 concurrent per host)
3. **Chunking**: 1000 tokens with 150 overlap, respect document boundaries
4. **Error Handling**: Retry logic, resume capability, robust timeout handling
5. **Vector Storage**: Optional Pinecone integration with modern API patterns

### Dependencies Resolved
- lxml: Used pre-compiled wheel (>=6.0.0) to avoid Windows compilation issues
- httpx: Fixed timeout configuration to include all four parameters (connect, read, write, pool)
- All other packages: Installed successfully with specified versions
- Virtual environment: Python 3.13.2 configured

## Next Steps for Development
1. Implement crawler modules with placeholder logic
2. Add comprehensive error handling and logging
3. Create example configurations for different use cases
4. Add unit tests for core functionality
5. Document API integration patterns
