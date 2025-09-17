"""
Traversal logic for Hong Kong Policy Address site.
Handles the specific patterns and navigation of the Policy Address website.
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .config import CrawlerConfig
from .fetcher import HttpFetcher, FetchResult
from .frontier import UrlFrontier
from .parsers import DocumentParser, ParsedDocument

logger = logging.getLogger(__name__)


class PolicyAddressCrawler:
    """
    Specialized crawler for Hong Kong Policy Address website.
    
    Handles the specific URL patterns and navigation:
    - Main pages: .../policy.html (no Next button)
    - Sub pages: .../p1.html, .../p5.html, .../p9.html etc.
    - Uses "Next Page" button detection for navigation
    """
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.frontier = UrlFrontier(config)
        self.parser = DocumentParser(config)
        self.crawled_urls: Set[str] = set()
        self.documents: List[ParsedDocument] = []
        self.failed_urls: Set[str] = set()
        
    async def crawl(self) -> List[ParsedDocument]:
        """
        Main crawling method.
        
        Returns:
            List of parsed documents
        """
        logger.info("Starting Policy Address crawl")
        
        # Add seed URLs to frontier
        await self.frontier.add_seed_urls(self.config.seeds)
        
        # Start fetching
        async with HttpFetcher(self.config) as fetcher:
            await self._crawl_loop(fetcher)
            
        logger.info(f"Crawl completed: {len(self.documents)} documents, {len(self.failed_urls)} failures")
        return self.documents
        
    async def _crawl_loop(self, fetcher: HttpFetcher):
        """Main crawling loop."""
        pages_crawled = 0
        consecutive_empty = 0
        
        while (pages_crawled < self.config.max_pages and 
               consecutive_empty < 10 and  # Stop if no URLs available for a while
               self.frontier.has_pending_urls()):
               
            # Get next URL
            queued_url = await self.frontier.get_next_url()
            
            if not queued_url:
                # No URL available right now, wait a bit
                next_time = await self.frontier.get_next_available_time()
                wait_time = max(0.1, next_time - asyncio.get_event_loop().time())
                await asyncio.sleep(min(wait_time, 5.0))  # Cap wait time
                consecutive_empty += 1
                continue
                
            consecutive_empty = 0
            
            try:
                # Fetch the URL
                logger.info(f"Crawling [{pages_crawled + 1}/{self.config.max_pages}]: {queued_url.url}")
                fetch_result = await fetcher.fetch(queued_url.url)
                
                # Process the result
                await self._process_fetch_result(fetch_result, queued_url.depth)
                
                pages_crawled += 1
                
            except Exception as e:
                logger.error(f"Error processing {queued_url.url}: {e}")
                self.failed_urls.add(queued_url.url)
                
            finally:
                # Mark as completed in frontier
                await self.frontier.mark_completed(queued_url.url, 
                                                 queued_url.url not in self.failed_urls)
                
            # Log progress periodically
            if pages_crawled % 10 == 0:
                stats = self.frontier.get_stats()
                logger.info(f"Progress: {pages_crawled} pages, {stats['total_queued']} queued, "
                           f"{len(self.documents)} documents")
                           
    async def _process_fetch_result(self, fetch_result: FetchResult, depth: int):
        """Process a single fetch result."""
        if not fetch_result.is_success:
            logger.warning(f"Failed to fetch {fetch_result.url}: {fetch_result.error}")
            self.failed_urls.add(fetch_result.url)
            return
            
        self.crawled_urls.add(fetch_result.url)
        
        # Save raw content if configured
        if ((self.config.storage.save_html and fetch_result.is_html) or
            (self.config.storage.save_pdf and fetch_result.is_pdf)):
            save_dir = Path("data/raw")
            self.parser.save_raw_content(fetch_result, save_dir)
            
        # Parse the content
        document = self.parser.parse(fetch_result)
        if not document:
            logger.warning(f"Failed to parse content from {fetch_result.url}")
            return
            
        # Check for duplicates
        is_duplicate, original_url = self.parser.check_duplicate(document)
        if is_duplicate:
            logger.info(f"Skipping duplicate content: {fetch_result.url} (original: {original_url})")
            return
            
        # Add to documents
        self.documents.append(document)
        logger.debug(f"Added document: {document.title} ({len(document.content)} chars)")
        
        # Extract and queue new URLs
        if fetch_result.is_html:
            await self._extract_and_queue_links(fetch_result, document, depth)
            
    async def _extract_and_queue_links(self, fetch_result: FetchResult, document: ParsedDocument, depth: int):
        """Extract links and add them to the frontier."""
        if depth >= self.config.depth_limit:
            return
            
        soup = BeautifulSoup(fetch_result.content, 'lxml')
        
        # Extract Policy Address specific links first (content pages from table of contents)
        policy_links = self._extract_policy_address_links(soup, fetch_result.final_url)
        for link_url in policy_links:
            # Content pages get high priority (0 = highest)
            priority = 0 if 'policy.html' in fetch_result.final_url else 1
            await self.frontier.add_url(link_url, depth + 1, fetch_result.url, priority=priority)
        
        # Find Next Page button - this is the primary navigation method for content pages
        next_page_url = self._find_next_page_button(soup, fetch_result.final_url)
        if next_page_url:
            added = await self.frontier.add_url(next_page_url, depth + 1, fetch_result.url, priority=0)
            if added:
                logger.debug(f"Found Next Page: {next_page_url}")
                
        # Also extract PDF links (Policy Address documents often have PDF versions)
        pdf_links = self._extract_pdf_links(soup, fetch_result.final_url)
        for pdf_url in pdf_links:
            await self.frontier.add_url(pdf_url, depth + 1, fetch_result.url, priority=2)
            
    def _find_next_page_button(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """
        Find the Next Page button link.
        
        The Policy Address site uses "Next Page" buttons to navigate between sections.
        """
        # Look for common "Next Page" patterns
        next_patterns = [
            'next page',
            'next',
            '下一頁',  # Chinese for "Next Page"
            '下頁',
            '繼續',    # Continue
        ]
        
        # Search for links with next page text
        for link in soup.find_all('a', href=True):
            link_text = link.get_text().strip().lower()
            
            # Check text content
            for pattern in next_patterns:
                if pattern in link_text:
                    href = link['href'].strip()
                    if href and not href.startswith('#'):
                        absolute_url = urljoin(base_url, href)
                        logger.debug(f"Found Next Page button: '{link_text}' -> {absolute_url}")
                        return absolute_url
                        
            # Check title attribute
            title = link.get('title', '').strip().lower()
            for pattern in next_patterns:
                if pattern in title:
                    href = link['href'].strip()
                    if href and not href.startswith('#'):
                        absolute_url = urljoin(base_url, href)
                        logger.debug(f"Found Next Page in title: '{title}' -> {absolute_url}")
                        return absolute_url
                        
        # Look for navigation patterns specific to Policy Address
        # Sometimes the next page link is in a navigation area
        nav_areas = soup.find_all(['nav', 'div'], class_=re.compile(r'nav|pagination|next', re.I))
        for nav in nav_areas:
            for link in nav.find_all('a', href=True):
                href = link['href'].strip()
                if href and not href.startswith('#'):
                    # Check if this looks like a policy address next page pattern
                    if self._is_policy_address_next_page(href, base_url):
                        absolute_url = urljoin(base_url, href)
                        logger.debug(f"Found Policy Address next page pattern: {absolute_url}")
                        return absolute_url
                        
        return None
        
    def _is_policy_address_next_page(self, href: str, base_url: str) -> bool:
        """
        Check if a link looks like a Policy Address next page.
        
        Based on the pattern you described:
        - policy.html -> p1.html
        - p1.html -> p5.html  
        - p5.html -> p9.html
        """
        try:
            base_parsed = urlparse(base_url)
            base_path = base_parsed.path
            
            # Check if href matches the pN.html pattern
            if re.match(r'p\d+\.html$', href):
                return True
                
            # Check if it's a relative path that creates the pattern
            if href.startswith('./') or href.startswith('../'):
                return 'p' in href and '.html' in href
                
            # Check if current page is policy.html and next is p1.html
            if 'policy.html' in base_path and 'p1.html' in href:
                return True
                
            # Check if current page is pN.html and next is pM.html where M > N
            current_match = re.search(r'p(\d+)\.html', base_path)
            next_match = re.search(r'p(\d+)\.html', href)
            
            if current_match and next_match:
                current_num = int(current_match.group(1))
                next_num = int(next_match.group(1))
                return next_num > current_num
                
        except Exception as e:
            logger.debug(f"Error checking Policy Address pattern: {e}")
            
        return False
        
    def _extract_pdf_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract PDF download links."""
        pdf_links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            
            # Direct PDF links
            if href.lower().endswith('.pdf'):
                absolute_url = urljoin(base_url, href)
                pdf_links.append(absolute_url)
                continue
                
            # Links that might lead to PDFs (download buttons, etc.)
            link_text = link.get_text().strip().lower()
            if any(keyword in link_text for keyword in ['pdf', 'download', '下載', 'full text']):
                absolute_url = urljoin(base_url, href)
                # Only add if it looks like it could be a PDF
                if 'pdf' in absolute_url.lower() or 'download' in absolute_url.lower():
                    pdf_links.append(absolute_url)
                    
        return pdf_links
        
    def _extract_policy_address_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        Extract links that are relevant to Policy Address content.
        Prioritizes content page links (p1.html, p5.html, etc.) over navigation links.
        """
        links = []
        base_parsed = urlparse(base_url)
        
        # Special handling for policy.html (table of contents page)
        if 'policy.html' in base_url:
            logger.debug("Processing table of contents page, looking for content links")
            
            # Look for content page links (p1.html, p5.html, etc.)
            content_links = []
            for link in soup.find_all('a', href=True):
                href = link['href'].strip()
                if re.match(r'p\d+\.html$', href):  # Matches p1.html, p5.html, etc.
                    absolute_url = urljoin(base_url, href)
                    content_links.append(absolute_url)
                    logger.debug(f"Found content page link: {absolute_url}")
            
            # Return content links with high priority
            return content_links
        
        # For content pages (p1.html, etc.), extract normal links
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            
            if not href or href.startswith('#'):
                continue
                
            absolute_url = urljoin(base_url, href)
            parsed_url = urlparse(absolute_url)
            
            # Only consider links on the same host
            if parsed_url.netloc != base_parsed.netloc:
                continue
                
            # Look for Policy Address specific patterns
            path = parsed_url.path.lower()
            
            # Skip if not policy address related
            if not any(keyword in path for keyword in ['policy', 'address', 'chief', 'executive']):
                continue
                
            # Include if it matches patterns we care about
            if (path.endswith('.html') or
                path.endswith('.pdf') or
                'policy' in path or
                re.search(r'p\d+', path)):  # pN pattern
                links.append(absolute_url)
                
        return links
        
    def get_stats(self) -> Dict[str, any]:
        """Get crawling statistics."""
        frontier_stats = self.frontier.get_stats()
        
        return {
            'documents_found': len(self.documents),
            'urls_crawled': len(self.crawled_urls),
            'urls_failed': len(self.failed_urls),
            'frontier_stats': frontier_stats,
            'success_rate': len(self.crawled_urls) / max(1, len(self.crawled_urls) + len(self.failed_urls))
        }


async def crawl_policy_address(config: CrawlerConfig) -> List[ParsedDocument]:
    """
    Main entry point for Policy Address crawling.
    
    Args:
        config: Crawler configuration
        
    Returns:
        List of parsed documents
    """
    crawler = PolicyAddressCrawler(config)
    documents = await crawler.crawl()
    
    # Log final statistics
    stats = crawler.get_stats()
    logger.info(f"Crawl complete - Documents: {stats['documents_found']}, "
               f"Success rate: {stats['success_rate']:.1%}")
    
    return documents
