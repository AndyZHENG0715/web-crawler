# N8N Policy Address Crawler Setup Guide

This guide helps you migrate from the Python crawler to n8n workflow automation.

## 🚀 Quick Start

### 1. Prerequisites
- Node.js 16+ installed
- Access to n8n instance (cloud or self-hosted)
- n8n API key

### 2. Setup N8N Credentials

```bash
# Copy the environment template
cp .env.n8n.example .env

# Edit .env with your n8n details
# N8N_INSTANCE_URL=https://your-instance.app.n8n.cloud
# N8N_API_KEY=your-api-key-here
```

### 3. Install Dependencies

```bash
npm install
```

### 4. Deploy the Workflow

```bash
# Deploy workflow to n8n instance
npm run deploy

# Deploy and immediately execute
npm run deploy-and-run
```

## 🏗️ Architecture Comparison

### Python Implementation vs N8N Implementation

| Component | Python | N8N |
|-----------|--------|-----|
| **HTTP Fetcher** | `fetcher.py` with httpx | HTTP Request node with retry logic |
| **URL Queue** | `frontier.py` with async queue | Split in Batches + Code node |
| **HTML Parser** | BeautifulSoup + lxml | Cheerio in Code node |
| **Content Extraction** | Custom Python functions | JavaScript parsing logic |
| **Rate Limiting** | Async semaphores | Wait node with dynamic delay |
| **Data Storage** | JSONL file output | Write File node |
| **Configuration** | YAML + Pydantic | Environment variables + Set nodes |

## 🔧 Workflow Structure

The n8n workflow replicates the Python crawler with these nodes:

1. **Configuration** - Load settings (URLs, rate limits, etc.)
2. **Initialize Crawl State** - Set up crawling variables
3. **Load Seed URLs** - Start with Policy Address table of contents
4. **Process URLs** - Batch processing with rate limiting
5. **Fetch Page Content** - HTTP requests with retry logic
6. **Parse HTML Content** - Extract text, links, and metadata
7. **Discover New URLs** - Find content pages and next buttons
8. **Filter Valid Content** - Quality control for extracted content
9. **Save Document** - Store results in JSONL format
10. **Generate Statistics** - Final crawl metrics

## 📊 Expected Results

The n8n workflow should achieve similar results to the Python version:

- ✅ **108+ documents** from Policy Address (2023-2025)
- ✅ **HTML content pages** (p1.html, p5.html, etc.)
- ✅ **PDF documents** (full policies + annexes)
- ✅ **Sequential navigation** via "Next Page" buttons
- ✅ **Rate limiting** (1 RPS default)
- ✅ **Error handling** with retries
- ✅ **JSONL output** compatible with Python version

## 🛠️ Customization

### Modify Crawling Parameters

Edit the environment variables in `.env`:

```env
# Increase crawling speed (be careful with rate limits)
RATE_LIMIT_RPS=2

# Limit total pages
MAX_PAGES=50

# Add additional URLs
POLICY_ADDRESS_URLS=https://www.policyaddress.gov.hk/2023/en/policy.html,https://custom-url.html
```

### Extend the Workflow

1. **Add PDF Processing**: Create additional nodes to extract PDF content
2. **Add Embeddings**: Integrate with OpenAI API for vector embeddings
3. **Add Database Storage**: Connect to PostgreSQL or MongoDB
4. **Add Notifications**: Send completion alerts via Slack/Email

## 🔍 Monitoring and Debugging

### Check Workflow Execution

1. **N8N Interface**: View real-time execution in n8n dashboard
2. **Logs**: Check node outputs for debugging
3. **Error Handling**: Failed nodes are highlighted with error details

### Common Issues

**Authentication Errors**
- Verify `N8N_API_KEY` is correct
- Check `N8N_INSTANCE_URL` format

**Rate Limiting**
- Increase `RATE_LIMIT_RPS` if too slow
- Decrease if getting blocked by website

**Content Parsing Issues**
- Check HTML structure changes on Policy Address site
- Modify cheerio selectors in "Parse HTML Content" node

## 🔄 Migration Benefits

### Python → N8N Advantages

1. **Visual Workflow**: Easy to understand and modify
2. **No Server Management**: Cloud-hosted execution
3. **Built-in Monitoring**: Real-time execution tracking
4. **Easy Scaling**: Adjust execution frequency
5. **Integration Ready**: Connect to 300+ services
6. **No Code Maintenance**: GUI-based modifications
7. **Collaboration**: Team can view/edit workflows

### When to Use Each

**Use Python when**:
- Complex data processing logic
- Custom algorithms needed
- Local development/testing
- Full control over execution environment

**Use N8N when**:
- Visual workflow preferred
- Integration with other services
- Team collaboration important
- Cloud execution desired
- Scheduled automation needed

## 📈 Performance Comparison

Based on the Python implementation results:

| Metric | Python | N8N (Expected) |
|--------|---------|----------------|
| **Documents Crawled** | 108 | 108+ |
| **Success Rate** | 100% | 95-100% |
| **Execution Time** | ~6 minutes | ~6-8 minutes |
| **Memory Usage** | ~50MB | Cloud-managed |
| **Setup Complexity** | Medium | Low |
| **Maintenance** | Code updates | GUI updates |

The n8n implementation should achieve similar performance with easier maintenance and better integration capabilities.