# Hong Kong Policy Address Web Crawler (n8n)

A configurable web crawler built with n8n workflows, focused on extracting content from the Hong Kong Chief Executive's Policy Address (2023–2025), with extensibility for other domains and RAG (Retrieval Augmented Generation) capabilities.

## 🎯 Project Overview

This n8n-based crawler is designed to:
- **Target**: Hong Kong Policy Address documents from recent years
- **Extract**: Both HTML pages and PDF documents with intelligent deduplication
- **Process**: Content into chunks suitable for RAG applications
- **Store**: Documents in structured format with optional vector embeddings
- **Scale**: Extensible n8n workflow architecture for other government documents and domains

## 🏗️ Architecture

```
├── n8n-workflows/
│   ├── policy-address-crawler.json    # Main n8n workflow definition
│   └── policy-address-crawler.json.backup  # Backup of complex workflow
├── deploy-n8n-crawler.js             # Deployment script for n8n workflows
├── test_webhook.js                    # Webhook testing utility
├── configs/
│   ├── config.example.yaml           # Configuration templates
│   └── config.yaml                    # Your custom config
├── data/
│   ├── raw/                          # Saved HTML and PDF files
│   └── processed/                    # Processed output files
└── logs/                             # Execution logs
```

## 🚀 Quick Start

### 1. n8n Setup

This project uses n8n cloud instance for workflow execution. The workflows are pre-configured and deployed.

**Webhook URL**: `https://aitutorhk.app.n8n.cloud/webhook/policy-address-crawler`

### 2. Deploy Workflow

```bash
# Install Node.js dependencies
npm install

# Deploy the n8n workflow
npm run deploy
```

### 3. Test the Crawler

```bash
# Test the webhook endpoint
node test_webhook.js

# Or trigger via HTTP POST:
curl -X POST https://aitutorhk.app.n8n.cloud/webhook/policy-address-crawler
```

### 4. Monitor Execution

- **n8n Dashboard**: View executions at https://aitutorhk.app.n8n.cloud
- **Workflow Editor**: Modify the workflow in the n8n interface
- **Logs**: Check execution history for detailed information

## 📋 Key Features

### n8n Workflow Benefits
- **Visual workflows**: Easy to understand and modify crawling logic
- **Cloud execution**: No local Python environment required
- **API-driven**: Trigger crawls via webhook calls
- **Monitoring**: Built-in execution history and error tracking
- **Scalable**: Cloud infrastructure handles resource management

### Intelligent Deduplication
- **Content-based**: Uses hashes to detect identical content across different URLs
- **Configurable preference**: Choose HTML vs PDF when both contain same content
- **Resume capability**: Skip already-processed files on restart

### Polite Crawling
- **Rate limiting**: Configurable requests per second per host
- **Concurrency control**: Limit simultaneous connections
- **Timeouts & retries**: Robust error handling
- **Webhook responses**: Real-time status updates

### RAG-Ready Output
- **Chunking**: Intelligent text splitting with configurable overlap
- **Metadata**: Preserves document structure, page numbers, sections
- **API integration**: Ready for OpenAI and Pinecone integration

## ⚙️ Configuration Guide

### n8n Workflow Configuration

The crawler behavior is controlled through the n8n workflow nodes:

```javascript
// Configuration Node (in workflow)
{
  "seedUrls": "https://www.policyaddress.gov.hk/2024/,https://www.policyaddress.gov.hk/2023/",
  "maxPages": "50",
  "rateLimitRps": "1",
  "allowedHosts": "www.policyaddress.gov.hk"
}
```

### Modifying the Workflow

1. **Access n8n Editor**: Visit https://aitutorhk.app.n8n.cloud
2. **Open Workflow**: Find "Hong Kong Policy Address Crawler"
3. **Edit Nodes**: Modify configuration values
4. **Save & Activate**: Deploy changes

### Advanced Configuration

Edit `configs/config.yaml` for additional settings:

```yaml
# Control crawling behavior
crawling:
  max_pages: 200            # Safety limit for total pages
  depth_limit: 5            # How deep to follow links
  rate_limit_rps: 1         # Requests per second

# Output format
output:
  save_html: true           # Save raw HTML files
  save_pdf: true            # Save PDF documents
  chunk_content: true       # Enable text chunking
```

## 📊 Output Format

### Webhook Response
The crawler returns real-time status via webhook:

```
✅ Policy Address Crawler Webhook Working!

Timestamp: 2025-09-22T09:53:27Z
Seed URLs: https://www.policyaddress.gov.hk/2024/, https://www.policyaddress.gov.hk/2023/
Max Pages: 50
Status: Ready to crawl Hong Kong Policy Address documents
```

### Processed Documents
Documents are saved in structured format in `data/processed/`:

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
  "crawled_at": "2025-09-22T09:53:27Z"
}
```

## 🔧 Development

### n8n Workflow Structure

The main workflow consists of these key nodes:

- **Webhook Trigger**: Receives HTTP POST requests to start crawling
- **Configuration**: Sets crawling parameters (URLs, limits, rate limiting)
- **URL Processing**: Manages the queue of URLs to crawl
- **Content Fetching**: Downloads HTML and PDF content
- **Content Parsing**: Extracts text and discovers new URLs
- **Content Filtering**: Applies quality checks and deduplication
- **Text Chunking**: Processes content for RAG applications
- **Storage**: Saves processed documents and metadata
- **Webhook Response**: Returns status and statistics

### Extending to Other Sites

1. **Duplicate Workflow**: Copy the existing workflow in n8n
2. **Modify Configuration**: Update seed URLs and allowed hosts
3. **Customize Parsing**: Adjust content extraction logic for the new site
4. **Test with Limits**: Use small `maxPages` for initial testing

### Local Development

```bash
# Install dependencies
npm install

# Test webhook locally
node test_webhook.js

# Deploy workflow changes
npm run deploy
```

### Contributing

1. **Use n8n Editor**: Make changes in the visual workflow editor
2. **Export Workflow**: Download JSON and commit to repository
3. **Test Thoroughly**: Verify webhook responses and data quality
4. **Update Documentation**: Keep README current with workflow changes

## 🐛 Troubleshooting

### Common Issues

**Webhook Not Responding**
```bash
# Test the webhook endpoint
node test_webhook.js

# Check n8n workflow is active
# Visit: https://aitutorhk.app.n8n.cloud

# Verify workflow execution logs in n8n dashboard
```

**n8n Workflow Errors**
- Check execution logs in n8n interface
- Verify all required nodes are connected
- Ensure webhook trigger uses `responseMode: "responseNode"`
- Confirm `respondToWebhook` node is properly configured

**Configuration Issues**
- Edit workflow nodes in n8n editor
- Update seed URLs and rate limits
- Check allowed hosts configuration

**Large Memory Usage**
- Reduce `maxPages` in workflow configuration
- Lower rate limits in configuration nodes
- Monitor execution in n8n dashboard

### Logs and Debugging

- **n8n Dashboard**: View execution history and errors
- **Webhook Testing**: Use `test_webhook.js` for quick tests
- **Local Logs**: Check `logs/` directory for local execution logs
- **Browser DevTools**: Monitor network requests when testing webhooks

### Performance Optimization

- **Rate Limiting**: Adjust `rateLimitRps` to balance speed vs politeness
- **Concurrent Processing**: Configure workflow for optimal throughput
- **Memory Management**: Monitor n8n cloud resource usage

## 📝 License

This project is open source. Please respect the websites you crawl and follow their robots.txt and terms of service.

## 🤝 Support

For questions about:
- **n8n Workflows**: Check execution logs in the n8n dashboard
- **Configuration**: Review workflow nodes and settings
- **API Integration**: Test webhook endpoints with provided utilities
- **Site-specific Issues**: Examine content parsing logic in workflow nodes

**Useful Resources:**
- **n8n Documentation**: https://docs.n8n.io/
- **Webhook Testing**: Use `test_webhook.js` for debugging
- **Workflow URL**: https://aitutorhk.app.n8n.cloud/workflow/Sb4LopO6LddL8lgI

Happy crawling with n8n! 🕷️🤖