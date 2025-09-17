"""
HTTP client using httpx with retries and timeouts.
Handles connection pooling, user agents, and robust error handling.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urljoin
import httpx
from yarl import URL

from .config import CrawlerConfig

logger = logging.getLogger(__name__)


class FetchResult:
    """Result of a fetch operation."""
    
    def __init__(self, url: str, status_code: int, content: bytes, 
                 headers: Dict[str, str], content_type: str, 
                 final_url: str, error: Optional[str] = None):
        self.url = url
        self.status_code = status_code
        self.content = content
        self.headers = headers
        self.content_type = content_type
        self.final_url = final_url  # After redirects
        self.error = error
        
    @property
    def is_success(self) -> bool:
        """Check if fetch was successful."""
        return self.status_code == 200 and self.error is None
        
    @property
    def is_html(self) -> bool:
        """Check if content is HTML."""
        return 'text/html' in self.content_type.lower()
        
    @property
    def is_pdf(self) -> bool:
        """Check if content is PDF."""
        return 'application/pdf' in self.content_type.lower()
        
    @property
    def text(self) -> str:
        """Get text content with encoding detection."""
        if not self.content:
            return ""
        
        # Try to detect encoding from headers
        encoding = 'utf-8'  # Default
        if 'charset=' in self.content_type:
            try:
                encoding = self.content_type.split('charset=')[1].split(';')[0].strip()
            except (IndexError, ValueError):
                pass
                
        try:
            return self.content.decode(encoding)
        except UnicodeDecodeError:
            # Fallback to utf-8 with error replacement
            return self.content.decode('utf-8', errors='replace')


class HttpFetcher:
    """
    HTTP client with configurable retries, timeouts, and rate limiting.
    Uses httpx for modern async HTTP support.
    """
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.session: Optional[httpx.AsyncClient] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        
    async def start(self):
        """Initialize the HTTP client session."""
        if self.session is not None:
            return
            
        # Configure httpx client
        timeout = httpx.Timeout(
            connect=self.config.timeouts.get('connect', 10),
            read=self.config.timeouts.get('read', 30),
            write=self.config.timeouts.get('write', 5),
            pool=self.config.timeouts.get('pool', 5)
        )
        
        headers = {
            'User-Agent': self.config.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        self.session = httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
            follow_redirects=True,
            max_redirects=10,
            limits=httpx.Limits(
                max_connections=self.config.rate_limits.global_concurrency * 2,
                max_keepalive_connections=self.config.rate_limits.global_concurrency
            )
        )
        
        logger.info(f"HTTP client initialized with {self.config.rate_limits.global_concurrency} max connections")
        
    async def close(self):
        """Close the HTTP client session."""
        if self.session:
            await self.session.aclose()
            self.session = None
            logger.info("HTTP client closed")
            
    async def fetch(self, url: str) -> FetchResult:
        """
        Fetch a single URL with retries and error handling.
        
        Args:
            url: The URL to fetch
            
        Returns:
            FetchResult: Result of the fetch operation
        """
        if not self.session:
            await self.start()
            
        url_obj = URL(url)
        logger.debug(f"Fetching: {url}")
        
        last_error = None
        
        for attempt in range(self.config.retries + 1):
            try:
                response = await self.session.get(url)
                
                # Get final URL after redirects
                final_url = str(response.url)
                
                # Extract content type
                content_type = response.headers.get('content-type', 'text/html')
                
                # Convert headers to dict
                headers = dict(response.headers)
                
                logger.debug(f"Fetched {url} -> {response.status_code} ({len(response.content)} bytes)")
                
                return FetchResult(
                    url=url,
                    status_code=response.status_code,
                    content=response.content,
                    headers=headers,
                    content_type=content_type,
                    final_url=final_url
                )
                
            except httpx.TimeoutException as e:
                last_error = f"Timeout: {e}"
                logger.warning(f"Timeout fetching {url} (attempt {attempt + 1}/{self.config.retries + 1}): {e}")
                
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}: {e}"
                logger.warning(f"HTTP error fetching {url}: {e}")
                # Don't retry for client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    break
                    
            except httpx.ConnectError as e:
                last_error = f"Connection error: {e}"
                logger.warning(f"Connection error fetching {url} (attempt {attempt + 1}/{self.config.retries + 1}): {e}")
                
            except Exception as e:
                last_error = f"Unexpected error: {e}"
                logger.error(f"Unexpected error fetching {url}: {e}")
                
            # Wait before retry (exponential backoff)
            if attempt < self.config.retries:
                wait_time = 2 ** attempt
                logger.debug(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
                
        # All retries failed
        logger.error(f"Failed to fetch {url} after {self.config.retries + 1} attempts: {last_error}")
        
        return FetchResult(
            url=url,
            status_code=0,
            content=b'',
            headers={},
            content_type='',
            final_url=url,
            error=last_error
        )
        
    async def fetch_multiple(self, urls: list[str]) -> list[FetchResult]:
        """
        Fetch multiple URLs concurrently with rate limiting.
        
        Args:
            urls: List of URLs to fetch
            
        Returns:
            List of FetchResult objects
        """
        if not urls:
            return []
            
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.config.rate_limits.global_concurrency)
        
        async def fetch_with_semaphore(url: str) -> FetchResult:
            async with semaphore:
                return await self.fetch(url)
                
        logger.info(f"Fetching {len(urls)} URLs with max {self.config.rate_limits.global_concurrency} concurrent connections")
        
        # Execute all fetches concurrently
        tasks = [fetch_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        fetch_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task failed for {urls[i]}: {result}")
                fetch_results.append(FetchResult(
                    url=urls[i],
                    status_code=0,
                    content=b'',
                    headers={},
                    content_type='',
                    final_url=urls[i],
                    error=str(result)
                ))
            else:
                fetch_results.append(result)
                
        success_count = sum(1 for r in fetch_results if r.is_success)
        logger.info(f"Fetch complete: {success_count}/{len(urls)} successful")
        
        return fetch_results
