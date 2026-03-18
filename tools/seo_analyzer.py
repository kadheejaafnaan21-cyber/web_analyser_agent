"""
tools/seo_analyzer.py
─────────────────────
Evaluates a webpage for SEO best practices.

Checks performed:
  ✅ Meta title — presence, length (30–60 chars)
  ✅ Meta description — presence, length (120–160 chars)
  ✅ Header hierarchy — H1 count, H2/H3 structure
  ✅ Image alt attributes — coverage percentage
  ✅ Sitemap detection — /sitemap.xml
  ✅ robots.txt detection
  ✅ Page size (performance indicator)

Each check returns a sub-score; the overall_score is a weighted average.
"""

import re
from urllib.parse import urljoin

import requests

from config.settings import (
    SEO_TITLE_MIN_LENGTH, SEO_TITLE_MAX_LENGTH,
    SEO_DESC_MIN_LENGTH, SEO_DESC_MAX_LENGTH,
    REQUEST_TIMEOUT,
)
from tools.website_fetcher import PageData
from utils.logger import get_logger

logger = get_logger(__name__)


def analyze_seo(page: PageData) -> dict:
    """
    Run all SEO checks on a PageData object.
    Returns a dict that maps directly to SEOReport model fields.
    """
    if page.error:
        return {"error": page.error, "overall_score": 0.0}

    soup = page.soup
    results = {}
    scores = []  # We'll average these at the end

    # ── 1. Meta Title ────────────────────────────────────────────────────────
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    title_len = len(title)
    title_ok = SEO_TITLE_MIN_LENGTH <= title_len <= SEO_TITLE_MAX_LENGTH

    results["title"] = title
    results["title_length"] = title_len
    results["title_ok"] = title_ok
    title_score = 100 if title_ok else (50 if title else 0)
    scores.append(("title", title_score, 20))  # (name, score, weight)

    # ── 2. Meta Description ───────────────────────────────────────────────────
    meta_desc_tag = soup.find("meta", attrs={"name": re.compile("description", re.I)})
    meta_desc = meta_desc_tag.get("content", "").strip() if meta_desc_tag else ""
    meta_desc_len = len(meta_desc)
    meta_desc_ok = SEO_DESC_MIN_LENGTH <= meta_desc_len <= SEO_DESC_MAX_LENGTH

    results["meta_description"] = meta_desc
    results["meta_desc_length"] = meta_desc_len
    results["meta_desc_ok"] = meta_desc_ok
    desc_score = 100 if meta_desc_ok else (50 if meta_desc else 0)
    scores.append(("meta_desc", desc_score, 20))

    # ── 3. Header Hierarchy ───────────────────────────────────────────────────
    h1_tags = soup.find_all("h1")
    h2_tags = soup.find_all("h2")
    h3_tags = soup.find_all("h3")

    h1_count = len(h1_tags)
    h2_count = len(h2_tags)
    h3_count = len(h3_tags)
    # Ideal: exactly one H1
    header_hierarchy_ok = h1_count == 1

    results["h1_count"] = h1_count
    results["h2_count"] = h2_count
    results["h3_count"] = h3_count
    results["header_hierarchy_ok"] = header_hierarchy_ok
    results["h1_texts"] = [h.get_text(strip=True) for h in h1_tags]
    results["h2_texts"] = [h.get_text(strip=True) for h in h2_tags[:5]]

    header_score = 100 if h1_count == 1 else (50 if h1_count > 1 else 0)
    scores.append(("headers", header_score, 15))

    # ── 4. Image Alt Attributes ───────────────────────────────────────────────
    all_images = soup.find_all("img")
    total_images = len(all_images)
    images_with_alt = sum(1 for img in all_images if img.get("alt", "").strip())
    images_missing_alt = total_images - images_with_alt
    alt_coverage = (images_with_alt / total_images * 100) if total_images > 0 else 100.0

    results["total_images"] = total_images
    results["images_missing_alt"] = images_missing_alt
    results["alt_coverage_pct"] = round(alt_coverage, 1)
    alt_score = alt_coverage  # Already 0–100
    scores.append(("alt_attrs", alt_score, 15))

    # ── 5. Canonical Tag ──────────────────────────────────────────────────────
    canonical = soup.find("link", rel="canonical")
    results["has_canonical"] = canonical is not None

    # ── 6. Open Graph Tags ────────────────────────────────────────────────────
    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")
    results["has_og_tags"] = bool(og_title or og_desc)
    og_score = 100 if results["has_og_tags"] else 0
    scores.append(("og_tags", og_score, 10))

    # ── 7. Sitemap Detection ──────────────────────────────────────────────────
    base = urljoin(page.final_url, "/")
    has_sitemap = _url_exists(base + "sitemap.xml")
    has_robots  = _url_exists(base + "robots.txt")
    results["has_sitemap"] = has_sitemap
    results["has_robots_txt"] = has_robots
    tech_score = (50 if has_sitemap else 0) + (50 if has_robots else 0)
    scores.append(("tech_files", tech_score, 10))

    # ── 8. Page Size ──────────────────────────────────────────────────────────
    results["page_size_kb"] = round(page.page_size_kb, 1)
    # Under 100 KB = excellent, under 500 KB = OK, over 1 MB = poor
    size_score = 100 if page.page_size_kb < 100 else (
        70 if page.page_size_kb < 500 else 30
    )
    scores.append(("page_size", size_score, 10))

    # ── Overall Score ─────────────────────────────────────────────────────────
    total_weight = sum(w for _, _, w in scores)
    overall = sum(s * w for _, s, w in scores) / total_weight if total_weight else 0
    results["overall_score"] = round(overall, 1)

    # ── Recommendations ───────────────────────────────────────────────────────
    recommendations = []
    if not title_ok:
        recommendations.append(
            f"Fix meta title (current: {title_len} chars, ideal: {SEO_TITLE_MIN_LENGTH}–{SEO_TITLE_MAX_LENGTH})"
        )
    if not meta_desc_ok:
        recommendations.append(
            f"Fix meta description (current: {meta_desc_len} chars, ideal: {SEO_DESC_MIN_LENGTH}–{SEO_DESC_MAX_LENGTH})"
        )
    if h1_count != 1:
        recommendations.append(f"Use exactly one H1 tag (found {h1_count})")
    if images_missing_alt > 0:
        recommendations.append(f"Add alt text to {images_missing_alt} image(s)")
    if not has_sitemap:
        recommendations.append("Add a sitemap.xml file")
    if not has_robots:
        recommendations.append("Add a robots.txt file")

    results["recommendations"] = recommendations
    results["details"] = {
        "score_breakdown": {name: score for name, score, _ in scores},
        "recommendations": recommendations,
    }

    logger.info(f"SEO analysis complete for {page.url}: score={results['overall_score']}")
    return results


def _url_exists(url: str) -> bool:
    """Quick check if a URL returns 200 OK."""
    try:
        r = requests.head(url, timeout=5, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False