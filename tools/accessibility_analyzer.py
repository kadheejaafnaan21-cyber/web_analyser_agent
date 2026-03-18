"""
tools/accessibility_analyzer.py
────────────────────────────────
Evaluates a webpage for accessibility (a11y) compliance.

Checks (all heuristic — not a full WCAG 2.1 audit):
  ✅ Images without alt text
  ✅ Form inputs without associated <label>
  ✅ ARIA landmark roles (main, nav, header, footer)
  ✅ ARIA labels on interactive elements
  ✅ Basic color contrast flag (low-contrast inline styles)
  ✅ Semantic HTML structure
  ✅ Skip-navigation link
  ✅ Lang attribute on <html>
"""

import re

from bs4 import BeautifulSoup, Tag
from tools.website_fetcher import PageData
from utils.logger import get_logger

logger = get_logger(__name__)


def _safe_attr(el, key) -> str | None:
    """
    Safely call el.get(key) — guards against:
      - el not being a Tag (NavigableString, etc.)
      - el.attrs being None (bs4 edge case with malformed HTML)
    """
    if not isinstance(el, Tag):
        return None
    if el.attrs is None:
        return None
    return el.attrs.get(key)


def _safe_find_all(soup, *args, **kwargs) -> list:
    """
    Wrapper around soup.find_all() that:
      - Catches AttributeError from bs4's internal iterator
      - Filters results to Tag objects with non-None attrs only
    """
    try:
        return [el for el in soup.find_all(*args, **kwargs)
                if isinstance(el, Tag) and el.attrs is not None]
    except AttributeError:
        return []


def analyze_accessibility(page: PageData) -> dict:
    """
    Run all accessibility checks on a PageData object.
    Returns a dict that maps to AccessibilityReport model fields.
    """
    if page.error:
        return {"error": page.error, "overall_score": 0.0}

    soup = page.soup

    # ── Guard: ensure soup is a proper BeautifulSoup/Tag object ──────────────
    if not isinstance(soup, (BeautifulSoup, Tag)):
        logger.warning("page.soup is not a BeautifulSoup object — attempting re-parse")
        try:
            raw_html = page.html if hasattr(page, "html") else str(soup)
            soup = BeautifulSoup(raw_html, "html.parser")
        except Exception as e:
            logger.error(f"Failed to re-parse HTML: {e}")
            return {"error": f"Failed to parse HTML: {e}", "overall_score": 0.0}

    results = {}
    scores = []  # (name, score 0–100, weight)

    # ── 1. Images missing alt text ────────────────────────────────────────────
    all_imgs = _safe_find_all(soup, "img")
    imgs_missing_alt = [img for img in all_imgs if not _safe_attr(img, "alt")]
    results["images_missing_alt"] = len(imgs_missing_alt)
    results["total_images"] = len(all_imgs)
    alt_score = (
        100 if len(all_imgs) == 0
        else max(0, 100 - (len(imgs_missing_alt) / len(all_imgs)) * 100)
    )
    scores.append(("image_alt", alt_score, 20))

    # ── 2. Form inputs without labels ─────────────────────────────────────────
    inputs = _safe_find_all(
        soup, "input",
        type=lambda t: t is None or t not in ["hidden", "submit", "button", "reset"]
    )
    inputs_missing_label = []
    for inp in inputs:
        inp_id = _safe_attr(inp, "id")
        has_label = (
            (inp_id and soup.find("label", attrs={"for": inp_id}))
            or _safe_attr(inp, "aria-label")
            or _safe_attr(inp, "aria-labelledby")
            or _safe_attr(inp, "title")
        )
        if not has_label:
            inputs_missing_label.append(inp)

    results["total_form_inputs"] = len(inputs)
    results["inputs_missing_label"] = len(inputs_missing_label)
    form_score = (
        100 if len(inputs) == 0
        else max(0, 100 - (len(inputs_missing_label) / len(inputs)) * 100)
    )
    scores.append(("form_labels", form_score, 20))

    # ── 3. ARIA landmark roles ────────────────────────────────────────────────
    def _has_landmark(tag_name: str, role_value: str) -> bool:
        try:
            return bool(
                soup.find(tag_name)
                or soup.find(attrs={"role": role_value})
            )
        except AttributeError:
            return False

    has_main   = _has_landmark("main", "main")
    has_nav    = _has_landmark("nav", "navigation")
    has_header = _has_landmark("header", "banner")
    has_footer = _has_landmark("footer", "contentinfo")

    results["has_main_landmark"]   = has_main
    results["has_nav_landmark"]    = has_nav
    results["has_header_landmark"] = has_header
    results["has_footer_landmark"] = has_footer

    landmark_count = sum([has_main, has_nav, has_header, has_footer])
    landmark_score = (landmark_count / 4) * 100
    scores.append(("landmarks", landmark_score, 15))

    # ── 4. ARIA labels on interactive elements ────────────────────────────────
    interactive = _safe_find_all(soup, ["button", "a", "input", "select", "textarea"])
    aria_labeled = sum(
        1 for el in interactive
        if _safe_attr(el, "aria-label") or _safe_attr(el, "aria-labelledby") or _safe_attr(el, "title")
    )
    results["aria_labels_count"] = aria_labeled
    results["missing_aria_labels"] = max(0, len(interactive) - aria_labeled)

    aria_score = min(100, (aria_labeled / max(len(interactive), 1)) * 100)
    scores.append(("aria_labels", aria_score, 15))

    # ── 5. Language attribute ─────────────────────────────────────────────────
    try:
        html_tag = soup.find("html")
        has_lang = bool(_safe_attr(html_tag, "lang"))
    except AttributeError:
        has_lang = False
    results["has_lang_attr"] = has_lang
    lang_score = 100 if has_lang else 0
    scores.append(("lang_attr", lang_score, 10))

    # ── 6. Skip navigation link ───────────────────────────────────────────────
    skip_links = _safe_find_all(soup, "a", href=re.compile(r"#(main|content|skip)", re.I))
    results["has_skip_nav"] = len(skip_links) > 0
    skip_score = 100 if results["has_skip_nav"] else 0
    scores.append(("skip_nav", skip_score, 5))

    # ── 7. Basic colour contrast heuristic ───────────────────────────────────
    contrast_issues = _count_contrast_issues(soup)
    results["contrast_issues"] = contrast_issues
    contrast_score = max(0, 100 - (contrast_issues * 10))
    scores.append(("contrast", contrast_score, 15))

    # ── 8. Tab index abuse ────────────────────────────────────────────────────
    bad_tabindex = _safe_find_all(soup, attrs={"tabindex": re.compile(r"^[1-9]\d*$")})
    results["tabindex_issues"] = len(bad_tabindex)

    # ── Overall Score ─────────────────────────────────────────────────────────
    total_weight = sum(w for _, _, w in scores)
    overall = sum(s * w for _, s, w in scores) / total_weight if total_weight else 0
    results["overall_score"] = round(overall, 1)

    # ── Recommendations ───────────────────────────────────────────────────────
    recs = []
    if imgs_missing_alt:
        recs.append(f"Add alt text to {len(imgs_missing_alt)} image(s).")
    if inputs_missing_label:
        recs.append(f"Add labels to {len(inputs_missing_label)} form input(s).")
    if not has_main:
        recs.append("Add a <main> landmark element.")
    if not has_nav:
        recs.append("Add a <nav> landmark element.")
    if not has_lang:
        recs.append("Add lang attribute to <html> tag (e.g., lang='en').")
    if not results["has_skip_nav"]:
        recs.append("Add a 'skip to main content' link for keyboard users.")
    if contrast_issues:
        recs.append(f"Review {contrast_issues} potential colour contrast issue(s).")

    results["recommendations"] = recs
    results["details"] = {
        "score_breakdown": {n: s for n, s, _ in scores},
        "recommendations": recs,
    }

    logger.info(f"Accessibility analysis complete: score={results['overall_score']}")
    return results


def _count_contrast_issues(soup) -> int:
    """
    Heuristic contrast check: look for inline styles that set
    very light text colors (white, #fff, #ffffff, light grays).
    This is NOT a full WCAG contrast audit — just a quick flag.
    """
    issues = 0
    light_pattern = re.compile(
        r"color\s*:\s*(white|#fff(?:fff)?|rgb\(25[0-5],\s*25[0-5],\s*25[0-5]\))",
        re.I,
    )
    for tag in _safe_find_all(soup, style=True):
        style = _safe_attr(tag, "style") or ""
        if style and light_pattern.search(style):
            issues += 1
    return issues