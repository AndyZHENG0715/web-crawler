"""
URL frontier and per-host rate/concurrency limiter.
Manages crawl queue with politeness controls and priority scheduling.
"""

import asyncio
import time
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional, Set, Dict, List
from urllib.parse import urlparse
from yarl import URL

from .config import CrawlerConfig

logger = logging.getLogger(__name__)


@dataclass
class QueuedUrl:
    """A URL queued for crawling with metadata."""
    url: str
    depth: int = 0
    parent_url: Optional[str] = None
    priority: int = 0  # Lower number = higher priority
    queued_at: float = field(default_factory=time.time)
    
    def __post_init__(self):
        # Validate URL
        try:
            parsed = urlparse(self.url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid URL: {self.url}")
        except Exception as e:
            raise ValueError(f"Invalid URL {self.url}: {e}")
            
    @property
    def host(self) -> str:
        """Get the host from the URL."""
        return urlparse(self.url).netloc.lower()
        
    @property
    def age_seconds(self) -> float:
        """Get age of this queued URL in seconds."""
        return time.time() - self.queued_at


class HostQueue:
    """Queue for a specific host with rate limiting."""
    
    def __init__(self, host: str, config: CrawlerConfig):
        self.host = host
        self.config = config
        self.queue: deque[QueuedUrl] = deque()
        self.in_progress: Set[str] = set()
        self.last_request_time: float = 0
        self.request_times: deque[float] = deque()
        
    def can_fetch_now(self) -> bool:
        """Check if we can fetch from this host right now."""
        now = time.time()
        
        # Check concurrent connections limit
        if len(self.in_progress) >= self.config.rate_limits.per_host_concurrency:
            return False
            
        # Check rate limit (requests per second)
        min_interval = 1.0 / self.config.rate_limits.per_host_rps
        if now - self.last_request_time < min_interval:
            return False
            
        return True
        
    def time_until_next_fetch(self) -> float:
        """Get seconds to wait before next fetch is allowed."""
        if self.can_fetch_now():
            return 0.0
            
        now = time.time()
        min_interval = 1.0 / self.config.rate_limits.per_host_rps
        time_since_last = now - self.last_request_time
        
        return max(0.0, min_interval - time_since_last)
        
    def add_url(self, queued_url: QueuedUrl):
        """Add a URL to this host's queue."""
        if queued_url.url not in self.in_progress:
            self.queue.append(queued_url)
            logger.debug(f"Added {queued_url.url} to {self.host} queue (depth {queued_url.depth})")
            
    def get_next_url(self) -> Optional[QueuedUrl]:
        """Get the next URL to fetch, if allowed by rate limits."""
        if not self.can_fetch_now() or not self.queue:
            return None
            
        # Sort by priority, then by depth, then by age
        self.queue = deque(sorted(self.queue, key=lambda x: (x.priority, x.depth, x.queued_at)))
        
        queued_url = self.queue.popleft()
        self.in_progress.add(queued_url.url)
        self.last_request_time = time.time()
        
        # Clean old request times (for rate limiting)
        cutoff = time.time() - 60  # Keep last minute
        while self.request_times and self.request_times[0] < cutoff:
            self.request_times.popleft()
        self.request_times.append(self.last_request_time)
        
        logger.debug(f"Fetching {queued_url.url} from {self.host} (queue size: {len(self.queue)})")
        return queued_url
        
    def mark_completed(self, url: str):
        """Mark a URL as completed (remove from in_progress)."""
        self.in_progress.discard(url)
        
    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        return {
            'queued': len(self.queue),
            'in_progress': len(self.in_progress),
            'total': len(self.queue) + len(self.in_progress)
        }


class UrlFrontier:
    """
    Main URL frontier managing multiple host queues.
    Implements politeness and provides crawl coordination.
    """
    
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.host_queues: Dict[str, HostQueue] = {}
        self.seen_urls: Set[str] = set()
        self.completed_urls: Set[str] = set()
        self.active_fetches = 0
        self._lock = asyncio.Lock()
        
    def _get_host_queue(self, host: str) -> HostQueue:
        """Get or create a queue for the given host."""
        if host not in self.host_queues:
            self.host_queues[host] = HostQueue(host, self.config)
            logger.info(f"Created queue for host: {host}")
        return self.host_queues[host]
        
    async def add_url(self, url: str, depth: int = 0, parent_url: Optional[str] = None, priority: int = 0) -> bool:
        """
        Add a URL to the frontier.
        
        Args:
            url: The URL to add
            depth: Crawl depth from seed URLs
            parent_url: URL that linked to this one
            priority: Priority (lower = higher priority)
            
        Returns:
            bool: True if URL was added, False if already seen/invalid
        """
        async with self._lock:
            # Normalize URL
            try:
                url_obj = URL(url)
                normalized_url = str(url_obj)
            except Exception as e:
                logger.warning(f"Invalid URL {url}: {e}")
                return False
                
            # Check if already seen
            if normalized_url in self.seen_urls:
                return False
                
            # Check allowed hosts
            host = url_obj.host.lower()
            if host not in self.config.allowed_hosts:
                logger.debug(f"Host {host} not in allowed hosts, skipping {url}")
                return False
                
            # Check depth limit
            if depth > self.config.depth_limit:
                logger.debug(f"Depth {depth} exceeds limit {self.config.depth_limit}, skipping {url}")
                return False
                
            # Add to seen set
            self.seen_urls.add(normalized_url)
            
            # Create queued URL
            queued_url = QueuedUrl(
                url=normalized_url,
                depth=depth,
                parent_url=parent_url,
                priority=priority
            )
            
            # Add to appropriate host queue
            host_queue = self._get_host_queue(host)
            host_queue.add_url(queued_url)
            
            logger.debug(f"Added URL: {normalized_url} (depth {depth}, host {host})")
            return True
            
    async def add_seed_urls(self, seed_urls: List[str]):
        """Add seed URLs with depth 0 and high priority."""
        added_count = 0
        for url in seed_urls:
            if await self.add_url(url, depth=0, priority=-1):  # High priority
                added_count += 1
        logger.info(f"Added {added_count}/{len(seed_urls)} seed URLs")
        
    async def get_next_url(self) -> Optional[QueuedUrl]:
        """
        Get the next URL to fetch, respecting rate limits and concurrency.
        
        Returns:
            QueuedUrl or None if no URLs available right now
        """
        async with self._lock:
            # Check global concurrency limit
            if self.active_fetches >= self.config.rate_limits.global_concurrency:
                return None
                
            # Find a host queue that can provide a URL
            available_hosts = []
            for host, queue in self.host_queues.items():
                if queue.can_fetch_now() and queue.queue:
                    available_hosts.append((host, queue))
                    
            if not available_hosts:
                return None
                
            # Sort by queue size (smaller queues first for fairness)
            available_hosts.sort(key=lambda x: len(x[1].queue))
            
            # Get URL from the first available host
            host, host_queue = available_hosts[0]
            queued_url = host_queue.get_next_url()
            
            if queued_url:
                self.active_fetches += 1
                logger.debug(f"Dispatched {queued_url.url} (active fetches: {self.active_fetches})")
                
            return queued_url
            
    async def mark_completed(self, url: str, success: bool = True):
        """
        Mark a URL as completed.
        
        Args:
            url: The completed URL
            success: Whether the fetch was successful
        """
        async with self._lock:
            # Find the host and mark completed
            try:
                host = urlparse(url).netloc.lower()
                if host in self.host_queues:
                    self.host_queues[host].mark_completed(url)
                    
                self.completed_urls.add(url)
                self.active_fetches = max(0, self.active_fetches - 1)
                
                logger.debug(f"Completed {url} (success: {success}, active: {self.active_fetches})")
                
            except Exception as e:
                logger.error(f"Error marking {url} as completed: {e}")
                
    async def get_next_available_time(self) -> float:
        """Get the earliest time when a URL might be available."""
        next_times = []
        for host_queue in self.host_queues.values():
            if host_queue.queue:  # Has queued URLs
                wait_time = host_queue.time_until_next_fetch()
                next_times.append(time.time() + wait_time)
                
        return min(next_times) if next_times else time.time() + 1.0
        
    def has_pending_urls(self) -> bool:
        """Check if there are any pending URLs to fetch."""
        return any(queue.queue or queue.in_progress for queue in self.host_queues.values())
        
    def get_stats(self) -> Dict[str, any]:
        """Get comprehensive frontier statistics."""
        host_stats = {}
        total_queued = 0
        total_in_progress = 0
        
        for host, queue in self.host_queues.items():
            stats = queue.get_stats()
            host_stats[host] = stats
            total_queued += stats['queued']
            total_in_progress += stats['in_progress']
            
        return {
            'total_seen': len(self.seen_urls),
            'total_completed': len(self.completed_urls),
            'total_queued': total_queued,
            'total_in_progress': total_in_progress,
            'active_fetches': self.active_fetches,
            'hosts': len(self.host_queues),
            'host_stats': host_stats
        }
