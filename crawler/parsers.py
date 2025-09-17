"""
HTML and PDF extraction, content checksums.
Handles content extraction, deduplication, and link discovery.
"""

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import List, Optional, Set, Dict, Any, Tuple
from urllib.parse import urljoin, urlparse

import pypdf
from bs4 import BeautifulSoup, Comment
from pdfminer.high_level import extract_text as pdf_extract_text
from pdfminer.pdfpage import PDFPage

from .config import CrawlerConfig
from .fetcher import FetchResult

logger = logging.getLogger(__name__)


class ParsedDocument:
    """Represents a parsed document with extracted content."""
    
    def __init__(self, url: str, title: str, content: str, 
                 content_hash: str, content_type: str,
                 links: List[str], metadata: Dict[str, Any]):
        self.url = url
        self.title = title
        self.content = content
        self.content_hash = content_hash
        self.content_type = content_type
        self.links = links
        self.metadata = metadata
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'url': self.url,
            'title': self.title,
            'content': self.content,
            'content_hash': self.content_hash,
            'content_type': self.content_type,
            'links': self.links,
            'metadata': self.metadata
        }


class ContentDeduplicator:
    """Manages content deduplication using hashes."""
    
    def __init__(self):
        self.seen_hashes: Set[str] = set()
        self.hash_to_url: Dict[str, str] = {}
        
    def get_content_hash(self, content: str) -> str:
        """Generate SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
        
    def is_duplicate(self, content: str, url: str) -> Tuple[bool, Optional[str]]:
        """
        Check if content is duplicate.
        
        Returns:
            Tuple of (is_duplicate, original_url)
        """
        content_hash = self.get_content_hash(content)
        
        if content_hash in self.seen_hashes:
            original_url = self.hash_to_url.get(content_hash)
            logger.debug(f"Duplicate content detected: {url} matches {original_url}")
            return True, original_url
            
        self.seen_hashes.add(content_hash)
        self.hash_to_url[content_hash] = url
        return False, None


class HtmlParser:
    """Parses HTML content and extracts text, links, and metadata."""
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        
    def parse(self, fetch_result: FetchResult, base_url: str) -> Optional[ParsedDocument]:
        """
        Parse HTML content from fetch result.
        
        Args:
            fetch_result: The fetch result containing HTML
            base_url: Base URL for resolving relative links
            
        Returns:
            ParsedDocument or None if parsing failed
        """
        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(fetch_result.content, 'lxml')
            
            # Extract title
            title = self._extract_title(soup)
            
            # Extract main content
            content = self._extract_content(soup)
            
            # Extract links
            links = self._extract_links(soup, base_url)
            
            # Extract metadata
            metadata = self._extract_metadata(soup, fetch_result)
            
            # Generate content hash
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
            
            logger.debug(f"Parsed HTML: {len(content)} chars, {len(links)} links")
            
            return ParsedDocument(
                url=fetch_result.url,
                title=title,
                content=content,
                content_hash=content_hash,
                content_type='text/html',
                links=links,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Failed to parse HTML from {fetch_result.url}: {e}")
            return None
            
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        # Try title tag first
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            return title_tag.string.strip()
            
        # Try h1 tag
        h1_tag = soup.find('h1')
        if h1_tag:
            return h1_tag.get_text().strip()
            
        # Try og:title meta tag
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'].strip()
            
        return "Untitled"
        
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract main text content from HTML."""
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
            
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
            
        # Try to find main content area
        main_content = None
        
        # Look for semantic HTML5 elements
        for selector in ['main', 'article', '[role="main"]', '.content', '#content', '.main', '#main']:
            main_content = soup.select_one(selector)
            if main_content:
                break
                
        # If no main content found, use body
        if not main_content:
            main_content = soup.find('body') or soup
            
        # Extract text using a simpler, more robust method
        text = self._extract_text_simple(main_content)
        
        # Clean up whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Multiple newlines to double
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces to single
        text = text.strip()
        
        return text
        
    def _extract_text_simple(self, element) -> str:
        """Extract text using a simpler, more robust approach."""
        if not element:
            return ""
            
        # Use BeautifulSoup's built-in text extraction with some structure preservation
        text_parts = []
        
        # Handle headings specially
        for heading in element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            heading_text = heading.get_text().strip()
            if heading_text:
                text_parts.append(f"\n\n{heading_text}\n")
                heading.replace_with(f"\n\n{heading_text}\n")
                
        # Handle list items
        for li in element.find_all('li'):
            li_text = li.get_text().strip()
            if li_text:
                li.replace_with(f"\n• {li_text}")
                
        # Handle paragraphs and divs
        for para in element.find_all(['p', 'div']):
            para_text = para.get_text().strip()
            if para_text:
                para.replace_with(f"\n{para_text}\n")
                
        # Get the final text
        final_text = element.get_text()
        
        return final_text
        
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract and resolve all links from the page."""
        links = []
        
        # Extract href links
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            if href and not href.startswith('#'):  # Skip anchors
                absolute_url = urljoin(base_url, href)
                links.append(absolute_url)
                
        # Extract PDF links specifically
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            if href.lower().endswith('.pdf'):
                absolute_url = urljoin(base_url, href)
                links.append(absolute_url)
                
        # Remove duplicates while preserving order
        seen = set()
        unique_links = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
                
        return unique_links
        
    def _extract_metadata(self, soup: BeautifulSoup, fetch_result: FetchResult) -> Dict[str, Any]:
        """Extract metadata from HTML."""
        metadata = {
            'content_length': len(fetch_result.content),
            'final_url': fetch_result.final_url,
            'status_code': fetch_result.status_code
        }
        
        # Extract meta tags
        for meta in soup.find_all('meta'):
            name = meta.get('name') or meta.get('property')
            content = meta.get('content')
            if name and content:
                metadata[f'meta_{name}'] = content
                
        # Extract language
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            metadata['language'] = html_tag['lang']
            
        return metadata


class PdfParser:
    """Parses PDF content and extracts text and metadata."""
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        
    def parse(self, fetch_result: FetchResult) -> Optional[ParsedDocument]:
        """
        Parse PDF content from fetch result.
        
        Args:
            fetch_result: The fetch result containing PDF
            
        Returns:
            ParsedDocument or None if parsing failed
        """
        try:
            # Try pypdf first (faster)
            content, metadata = self._parse_with_pypdf(fetch_result.content)
            
            # If pypdf fails or returns little content, try pdfminer
            if not content or len(content.strip()) < 100:
                logger.debug("pypdf extracted little content, trying pdfminer")
                content_alt, metadata_alt = self._parse_with_pdfminer(fetch_result.content)
                if len(content_alt.strip()) > len(content.strip()):
                    content, metadata = content_alt, {**metadata, **metadata_alt}
                    
            # Clean up content
            content = self._clean_pdf_text(content)
            
            # Generate title from content or URL
            title = self._extract_pdf_title(content, fetch_result.url, metadata)
            
            # Generate content hash
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
            
            # Update metadata
            metadata.update({
                'content_length': len(fetch_result.content),
                'final_url': fetch_result.final_url,
                'status_code': fetch_result.status_code,
                'text_length': len(content)
            })
            
            logger.debug(f"Parsed PDF: {len(content)} chars, {metadata.get('pages', 0)} pages")
            
            return ParsedDocument(
                url=fetch_result.url,
                title=title,
                content=content,
                content_hash=content_hash,
                content_type='application/pdf',
                links=[],  # PDFs don't typically have extractable links
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Failed to parse PDF from {fetch_result.url}: {e}")
            return None
            
    def _parse_with_pypdf(self, pdf_content: bytes) -> Tuple[str, Dict[str, Any]]:
        """Parse PDF using pypdf library."""
        import io
        
        pdf_file = io.BytesIO(pdf_content)
        reader = pypdf.PdfReader(pdf_file)
        
        # Extract text
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text())
            
        content = '\n\n'.join(text_parts)
        
        # Extract metadata
        metadata = {
            'pages': len(reader.pages),
            'parser': 'pypdf'
        }
        
        # Add PDF metadata if available
        if reader.metadata:
            pdf_meta = reader.metadata
            for key in ['/Title', '/Author', '/Subject', '/Creator', '/Producer']:
                if key in pdf_meta:
                    clean_key = key.replace('/', '').lower()
                    metadata[f'pdf_{clean_key}'] = str(pdf_meta[key])
                    
        return content, metadata
        
    def _parse_with_pdfminer(self, pdf_content: bytes) -> Tuple[str, Dict[str, Any]]:
        """Parse PDF using pdfminer library (more robust but slower)."""
        import io
        
        pdf_file = io.BytesIO(pdf_content)
        
        # Extract text
        content = pdf_extract_text(pdf_file)
        
        # Count pages
        pdf_file.seek(0)
        pages = list(PDFPage.get_pages(pdf_file))
        
        metadata = {
            'pages': len(pages),
            'parser': 'pdfminer'
        }
        
        return content, metadata
        
    def _clean_pdf_text(self, text: str) -> str:
        """Clean up extracted PDF text."""
        if not text:
            return ""
            
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Remove page headers/footers (common patterns)
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip likely headers/footers
            if (len(line) < 60 and 
                (re.match(r'^\d+$', line) or  # Page numbers
                 re.match(r'^Page \d+', line, re.I) or
                 'policy address' in line.lower() and len(line) < 40)):
                continue
            cleaned_lines.append(line)
            
        return '\n'.join(cleaned_lines).strip()
        
    def _extract_pdf_title(self, content: str, url: str, metadata: Dict[str, Any]) -> str:
        """Extract or generate a title for the PDF."""
        # Try PDF metadata title first
        pdf_title = metadata.get('pdf_title', '').strip()
        if pdf_title and len(pdf_title) > 3:
            return pdf_title
            
        # Try to extract from first lines of content
        if content:
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            if lines:
                first_line = lines[0]
                if len(first_line) < 200:  # Reasonable title length
                    return first_line
                    
        # Generate from URL
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        if filename.endswith('.pdf'):
            return filename[:-4].replace('_', ' ').replace('-', ' ').title()
            
        return "PDF Document"


class DocumentParser:
    """Main parser that coordinates HTML and PDF parsing."""
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.html_parser = HtmlParser(config)
        self.pdf_parser = PdfParser(config)
        self.deduplicator = ContentDeduplicator()
        
    def parse(self, fetch_result: FetchResult) -> Optional[ParsedDocument]:
        """
        Parse a fetch result based on its content type.
        
        Args:
            fetch_result: The fetch result to parse
            
        Returns:
            ParsedDocument or None if parsing failed
        """
        if not fetch_result.is_success:
            logger.warning(f"Cannot parse failed fetch: {fetch_result.url}")
            return None
            
        try:
            if fetch_result.is_html:
                return self.html_parser.parse(fetch_result, fetch_result.final_url)
            elif fetch_result.is_pdf:
                return self.pdf_parser.parse(fetch_result)
            else:
                logger.warning(f"Unsupported content type {fetch_result.content_type} for {fetch_result.url}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error parsing {fetch_result.url}: {e}")
            return None
            
    def check_duplicate(self, document: ParsedDocument) -> Tuple[bool, Optional[str]]:
        """Check if document content is duplicate."""
        return self.deduplicator.is_duplicate(document.content, document.url)
        
    def save_raw_content(self, fetch_result: FetchResult, save_dir: Path) -> Optional[str]:
        """
        Save raw content to disk.
        
        Args:
            fetch_result: The fetch result to save
            save_dir: Directory to save in
            
        Returns:
            Saved file path or None if saving failed
        """
        if not fetch_result.is_success:
            return None
            
        try:
            # Create save directory
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename from URL
            parsed_url = urlparse(fetch_result.final_url)
            filename = os.path.basename(parsed_url.path)
            
            if not filename or filename == '/':
                # Generate filename from host and path
                host = parsed_url.netloc.replace('www.', '')
                path_parts = [p for p in parsed_url.path.split('/') if p]
                if path_parts:
                    filename = '_'.join(path_parts)
                else:
                    filename = 'index'
                    
            # Ensure proper extension
            if fetch_result.is_html and not filename.endswith('.html'):
                filename += '.html'
            elif fetch_result.is_pdf and not filename.endswith('.pdf'):
                filename += '.pdf'
                
            # Make filename safe
            filename = re.sub(r'[^\w\-_\.]', '_', filename)
            
            # Save file
            file_path = save_dir / filename
            
            # Handle duplicate filenames
            counter = 1
            original_path = file_path
            while file_path.exists():
                stem = original_path.stem
                suffix = original_path.suffix
                file_path = save_dir / f"{stem}_{counter}{suffix}"
                counter += 1
                
            with open(file_path, 'wb') as f:
                f.write(fetch_result.content)
                
            logger.debug(f"Saved raw content: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Failed to save raw content for {fetch_result.url}: {e}")
            return None
