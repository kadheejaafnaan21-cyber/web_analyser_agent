"""
tools/content_analyzer.py
──────────────────────────
Evaluates content quality and structure of a webpage.

Checks:
  ✅ Word count and content depth
  ✅ Readability (Flesch Reading Ease via textstat)
  ✅ Broken links detection (checks href URLs)
  ✅ Internal vs external link ratio
  ✅ Duplicate content heuristic (title == h1, very short content)
"""

import re
from urllib.parse import urlparse

import requests

try:
    import textstat  # pip install textstat
    TEXTSTAT_AVAILABLE = True
except ImportError:
    TEXTSTAT_AVAILABLE = False

from config.settings import MIN_WORD_COUNT, READABILITY_GOOD_THRESHOLD
from tools.website_fetcher import PageData, check_url_exists, resolve_url, get_domain
from utils.logger import get_logger

logger = get_logger(__name__)


def analyze_content(page: PageData) -> dict:
    """
    Run all content quality checks on a PageData object.
    Returns a dict that maps to ContentReport model fields.
    """
    if page.error:
        return {"error": page.error, "overall_score": 0.0}

    soup = page.soup
    results = {}
    scores = []

    # ── Extract visible text ──────────────────────────────────────────────────
    # Remove script/style tags so we only count real content
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    visible_text = soup.get_text(separator=" ", strip=True)
    # Collapse whitespace
    visible_text = re.sub(r"\s+", " ", visible_text).strip()

    # ── 1. Word Count ─────────────────────────────────────────────────────────
    words = visible_text.split()
    word_count = len(words)
    results["word_count"] = word_count
    wc_score = min(100, (word_count / MIN_WORD_COUNT) * 100)
    scores.append(("word_count", wc_score, 20))

    # ── 2. Readability Score ──────────────────────────────────────────────────
    if TEXTSTAT_AVAILABLE and word_count > 10:
        readability = textstat.flesch_reading_ease(visible_text)
        grade = textstat.text_standard(visible_text, float_output=False)
    else:
        # Fallback: very rough estimate based on avg word length
        avg_word_len = sum(len(w) for w in words) / max(word_count, 1)
        readability = max(0, 100 - (avg_word_len - 4) * 10)
        grade = "N/A (textstat not installed)"

    results["readability_score"] = round(readability, 1)
    results["readability_grade"] = str(grade)
    # Flesch: 60–70 = standard, <30 = very hard, >80 = easy
    read_score = min(100, max(0, readability))
    scores.append(("readability", read_score, 25))

    # ── 3. Link Analysis ──────────────────────────────────────────────────────
    page_domain = get_domain(page.final_url)
    all_links = soup.find_all("a", href=True)
    internal_links = []
    external_links = []
    broken_links = []

    for link in all_links:
        href = link.get("href", "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        absolute = resolve_url(page.final_url, href)
        link_domain = get_domain(absolute)

        if link_domain == page_domain or not link_domain:
            internal_links.append(absolute)
        else:
            external_links.append(absolute)

    # Check for broken links (sample up to 10 to avoid being too slow)
    links_to_check = (internal_links + external_links)[:10]
    for url in links_to_check:
        if not check_url_exists(url):
            broken_links.append(url)

    results["internal_links_count"] = len(internal_links)
    results["external_links_count"] = len(external_links)
    results["broken_links_count"] = len(broken_links)
    results["broken_links"] = broken_links

    link_score = max(0, 100 - (len(broken_links) * 10))
    scores.append(("links", link_score, 20))

    # ── 4. Duplicate Content Heuristic ───────────────────────────────────────
    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True).lower() if title_tag else ""
    h1_tag = soup.find("h1")
    h1_text = h1_tag.get_text(strip=True).lower() if h1_tag else ""

    dup_flag = False
    dup_reason = None
    if word_count < 50:
        dup_flag = True
        dup_reason = "Page has very little content (< 50 words)"
    elif title_text and h1_text and title_text == h1_text:
        dup_flag = True
        dup_reason = "Title and H1 are identical — potential duplicate content signal"

    results["duplicate_content_flag"] = dup_flag
    results["duplicate_content_reason"] = dup_reason
    dup_score = 50 if dup_flag else 100
    scores.append(("duplicate", dup_score, 15))

    # ── 5. Content Depth ─────────────────────────────────────────────────────
    # Check for structural richness: images, headers, lists, paragraphs
    paragraphs = len(soup.find_all("p"))
    lists = len(soup.find_all(["ul", "ol"]))
    headers = len(soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]))
    depth_score = min(100, (paragraphs * 5) + (lists * 10) + (headers * 8))
    results["content_depth"] = {
        "paragraphs": paragraphs,
        "lists": lists,
        "headers": headers,
    }
    scores.append(("depth", depth_score, 20))

    # ── Overall Score ─────────────────────────────────────────────────────────
    total_weight = sum(w for _, _, w in scores)
    overall = sum(s * w for _, s, w in scores) / total_weight if total_weight else 0
    results["overall_score"] = round(overall, 1)

    # ── Recommendations ───────────────────────────────────────────────────────
    recs = []
    if word_count < MIN_WORD_COUNT:
        recs.append(f"Increase content length (current: {word_count} words, goal: {MIN_WORD_COUNT}+).")
    if readability < READABILITY_GOOD_THRESHOLD:
        recs.append(f"Improve readability (Flesch score: {readability:.0f}, aim for 60+).")
    if broken_links:
        recs.append(f"Fix {len(broken_links)} broken link(s): {broken_links[:3]}")
    if dup_flag:
        recs.append(f"Address duplicate content: {dup_reason}")

    results["recommendations"] = recs
    results["details"] = {
        "score_breakdown": {n: s for n, s, _ in scores},
        "recommendations": recs,
        "broken_links": broken_links,
    }

    logger.info(f"Content analysis complete: score={results['overall_score']}")
    return results