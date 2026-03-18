"""
tests/test_tools.py
────────────────────
Unit tests for the analysis tools.

Run with:  pytest tests/ -v

Beginner tip: Each function starting with "test_" is automatically
discovered and run by pytest. assert = "this must be true or the test fails".
"""

import pytest
from bs4 import BeautifulSoup
from unittest.mock import patch, MagicMock

from tools.website_fetcher import PageData, get_domain, resolve_url
from tools.seo_analyzer import analyze_seo
from tools.accessibility_analyzer import analyze_accessibility
from tools.content_analyzer import analyze_content


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_page(html: str, url: str = "https://example.com") -> PageData:
    """Create a PageData object from raw HTML for testing."""
    return PageData(
        url=url,
        html=html,
        soup=BeautifulSoup(html, "lxml"),
        status_code=200,
        response_time_ms=100.0,
        page_size_kb=len(html) / 1024,
        final_url=url,
    )


# ── SEO Tests ─────────────────────────────────────────────────────────────────

class TestSEOAnalyzer:

    def test_good_page_gets_high_score(self):
        html = """
        <html>
          <head>
            <title>Perfect SEO Page - Example Website</title>
            <meta name="description" content="This is a well-optimised meta description that is exactly the right length for SEO purposes and search results."/>
            <meta property="og:title" content="Perfect Page"/>
          </head>
          <body>
            <h1>Main Heading</h1>
            <h2>Section 1</h2>
            <img src="photo.jpg" alt="A descriptive alt text"/>
          </body>
        </html>"""
        result = analyze_seo(make_page(html))
        assert result["title_ok"] is True
        assert result["meta_desc_ok"] is True
        assert result["h1_count"] == 1
        assert result["images_missing_alt"] == 0
        assert result["overall_score"] > 60

    def test_missing_title_lowers_score(self):
        html = "<html><head></head><body><h1>Title</h1></body></html>"
        result = analyze_seo(make_page(html))
        assert result["title"] == ""
        assert result["title_ok"] is False
        assert result["overall_score"] < 70

    def test_multiple_h1_flagged(self):
        html = """<html><head><title>A Good Title For SEO</title></head>
        <body><h1>First H1</h1><h1>Second H1</h1></body></html>"""
        result = analyze_seo(make_page(html))
        assert result["h1_count"] == 2
        assert result["header_hierarchy_ok"] is False

    def test_images_without_alt_counted(self):
        html = """<html><head><title>Test Page Title Here For SEO</title></head>
        <body>
          <img src="a.jpg" alt="good"/>
          <img src="b.jpg"/>
          <img src="c.jpg"/>
        </body></html>"""
        result = analyze_seo(make_page(html))
        assert result["total_images"] == 3
        assert result["images_missing_alt"] == 2

    def test_error_page_returns_zero_score(self):
        page = PageData(
            url="https://fail.com", html="", soup=BeautifulSoup("", "lxml"),
            status_code=0, response_time_ms=0, page_size_kb=0,
            final_url="https://fail.com", error="Connection refused"
        )
        result = analyze_seo(page)
        assert result["overall_score"] == 0.0
        assert "error" in result


# ── Accessibility Tests ───────────────────────────────────────────────────────

class TestAccessibilityAnalyzer:

    def test_good_accessible_page(self):
        html = """
        <html lang="en">
          <body>
            <header><a href="#main">Skip to content</a></header>
            <nav aria-label="Main navigation"><a href="/">Home</a></nav>
            <main id="main">
              <img src="x.jpg" alt="Description"/>
              <form>
                <label for="name">Name</label>
                <input id="name" type="text"/>
              </form>
            </main>
            <footer>Footer</footer>
          </body>
        </html>"""
        result = analyze_accessibility(make_page(html))
        assert result["has_lang_attr"] is True
        assert result["has_main_landmark"] is True
        assert result["has_nav_landmark"] is True
        assert result["images_missing_alt"] == 0

    def test_missing_alt_counted(self):
        html = """<html lang="en"><body>
          <img src="a.jpg"/>
          <img src="b.jpg" alt="ok"/>
          <img src="c.jpg"/>
        </body></html>"""
        result = analyze_accessibility(make_page(html))
        assert result["images_missing_alt"] == 2

    def test_unlabelled_input_counted(self):
        html = """<html lang="en"><body>
          <input type="text" id="noLabel"/>
          <label for="hasLabel">OK</label>
          <input type="text" id="hasLabel"/>
        </body></html>"""
        result = analyze_accessibility(make_page(html))
        assert result["inputs_missing_label"] == 1


# ── Content Tests ─────────────────────────────────────────────────────────────

class TestContentAnalyzer:

    @patch("tools.content_analyzer.check_url_exists", return_value=True)
    def test_word_count(self, mock_check):
        words = " ".join(["word"] * 400)
        html = f"<html><body><p>{words}</p></body></html>"
        result = analyze_content(make_page(html))
        assert result["word_count"] >= 300

    @patch("tools.content_analyzer.check_url_exists", return_value=True)
    def test_duplicate_content_flag_low_word_count(self, mock_check):
        html = "<html><body><p>Very short.</p></body></html>"
        result = analyze_content(make_page(html))
        assert result["duplicate_content_flag"] is True


# ── Utility Tests ─────────────────────────────────────────────────────────────

class TestUtilities:

    def test_get_domain(self):
        assert get_domain("https://www.example.com/page") == "www.example.com"
        assert get_domain("http://blog.site.co.uk/post/1") == "blog.site.co.uk"

    def test_resolve_url(self):
        assert resolve_url("https://example.com/", "/about") == "https://example.com/about"
        assert resolve_url("https://example.com/page", "../other") == "https://example.com/other"