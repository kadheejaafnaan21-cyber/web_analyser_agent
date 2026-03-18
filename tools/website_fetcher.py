"""
tools/website_fetcher.py
────────────────────────
Fetches a webpage and returns the raw HTML + metadata.

This is the foundation for ALL analysis tools — SEO, accessibility, and
content tools all call fetch_page() first to get the HTML they need.
"""

import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config.settings import REQUEST_TIMEOUT
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PageData:
    """Everything we need about a fetched page, bundled in one object."""
    url: str
    html: str
    soup: BeautifulSoup          # Parsed HTML tree (BeautifulSoup object)
    status_code: int
    response_time_ms: float      # How long the server took to respond
    page_size_kb: float          # Size of the HTML document in kilobytes
    final_url: str               # URL after any redirects
    error: str | None = None     # Non-None if fetching failed
    headers: dict = field(default_factory=dict)


def fetch_page(url: str) -> PageData:
    """
    Download a web page and return a PageData object.

    Steps:
      1. Ensure URL has http/https scheme
      2. Send GET request with a browser-like User-Agent
      3. Record timing and size
      4. Parse HTML with BeautifulSoup
      5. Return PageData (or PageData with error set if something fails)
    """
    # Ensure URL has a scheme (http:// or https://)
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    logger.info(f"Fetching page: {url}")

    try:
        start = time.time()
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={
                # Pretend to be a regular browser so sites don't block us
                "User-Agent": (
                    "Mozilla/5.0 (compatible; SEOBot/1.0; "
                    "+https://github.com/your-repo)"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
            allow_redirects=True,
        )
        elapsed_ms = (time.time() - start) * 1000
        page_size_kb = len(response.content) / 1024

        # Parse HTML — lxml is faster than Python's built-in parser
        soup = BeautifulSoup(response.text, "lxml")

        logger.info(
            f"Fetched {url} → {response.status_code} "
            f"({page_size_kb:.1f} KB, {elapsed_ms:.0f} ms)"
        )

        return PageData(
            url=url,
            html=response.text,
            soup=soup,
            status_code=response.status_code,
            response_time_ms=elapsed_ms,
            page_size_kb=page_size_kb,
            final_url=response.url,
            headers=dict(response.headers),
        )

    except requests.exceptions.Timeout:
        msg = f"Timeout after {REQUEST_TIMEOUT}s fetching {url}"
        logger.warning(msg)
        return _error_page(url, msg)

    except requests.exceptions.ConnectionError as e:
        msg = f"Connection error for {url}: {e}"
        logger.warning(msg)
        return _error_page(url, msg)

    except Exception as e:
        msg = f"Unexpected error fetching {url}: {e}"
        logger.error(msg)
        return _error_page(url, msg)


def _error_page(url: str, error: str) -> PageData:
    """Return a PageData with empty content and the error set."""
    return PageData(
        url=url,
        html="",
        soup=BeautifulSoup("", "lxml"),
        status_code=0,
        response_time_ms=0.0,
        page_size_kb=0.0,
        final_url=url,
        error=error,
    )


def check_url_exists(url: str) -> bool:
    """
    Quick HEAD request to check if a URL is reachable.
    Used by the content analyzer for broken-link detection.
    """
    try:
        resp = requests.head(url, timeout=5, allow_redirects=True)
        return resp.status_code < 400
    except Exception:
        return False


def resolve_url(base_url: str, href: str) -> str:
    """Turn a relative href like '/about' into an absolute URL."""
    return urljoin(base_url, href)


def get_domain(url: str) -> str:
    """Extract the domain from a URL, e.g. 'https://example.com/page' → 'example.com'."""
    return urlparse(url).netloc