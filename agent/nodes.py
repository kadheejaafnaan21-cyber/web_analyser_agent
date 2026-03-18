import json
import re
import os
from groq import Groq

from agent.state import AgentState
from tools.website_fetcher import fetch_page
from tools.seo_analyzer import analyze_seo
from tools.accessibility_analyzer import analyze_accessibility
from tools.content_analyzer import analyze_content
from database import db_operations as db_ops
from utils.logger import get_logger

logger = get_logger(__name__)
_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = "llama-3.3-70b-versatile"

def parse_intent(state: AgentState) -> dict:
    user_input = state["user_input"]
    prompt = f"""You are an intent-parsing assistant. Respond ONLY with JSON.
User message: "{user_input}"
Return: {{"intent": "analyze_website|list_sites|list_reports|db_query|delete_old_reports|update_score|show_logs|unknown", "target_url": null, "db_action": null, "db_params": {{"days": null, "report_id": null, "new_score": null, "site_id": null}}}}"""
    response = _client.chat.completions.create(
        model=GROQ_MODEL, max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"```(?:json)?", "", raw).strip("` \n")
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = {"intent": "unknown", "target_url": None, "db_action": None, "db_params": {}}
    logger.info(f"[parse_intent] intent={parsed.get('intent')} url={parsed.get('target_url')}")
    return {"intent": parsed.get("intent","unknown"), "target_url": parsed.get("target_url"), "db_action": parsed.get("db_action"), "db_params": parsed.get("db_params") or {}}

_page_cache = {}
def _store_page(url, page): _page_cache[url] = page
def _get_page(url): return _page_cache.get(url)

def fetch_website(state: AgentState) -> dict:
    url = state.get("target_url")
    if not url: return {"fetch_error": "No URL provided."}
    page = fetch_page(url)
    if page.error: return {"fetch_error": page.error}
    _store_page(url, page)
    return {"fetch_error": None}

def run_seo_analysis(state: AgentState) -> dict:
    page = _get_page(state.get("target_url"))
    if not page or state.get("fetch_error"): return {"seo_result": {"error": "No page"}}
    return {"seo_result": analyze_seo(page)}

def run_accessibility_analysis(state: AgentState) -> dict:
    page = _get_page(state.get("target_url"))
    if not page or state.get("fetch_error"): return {"accessibility_result": {"error": "No page"}}
    return {"accessibility_result": analyze_accessibility(page)}

def run_content_analysis(state: AgentState) -> dict:
    page = _get_page(state.get("target_url"))
    if not page or state.get("fetch_error"): return {"content_result": {"error": "No page"}}
    return {"content_result": analyze_content(page)}

def execute_db_operation(state: AgentState) -> dict:
    intent = state.get("intent","unknown")
    db_action = state.get("db_action")
    url = state.get("target_url")
    params = state.get("db_params") or {}
    try:
        if intent == "analyze_website" and url:
            site_info = db_ops.get_or_create_site(url)
            site_id = site_info["id"]
            saved = {}
            if state.get("seo_result") and not state["seo_result"].get("error"):
                saved["seo"] = db_ops.save_seo_report(site_id, state["seo_result"])
            if state.get("accessibility_result") and not state["accessibility_result"].get("error"):
                saved["accessibility"] = db_ops.save_accessibility_report(site_id, state["accessibility_result"])
            if state.get("content_result") and not state["content_result"].get("error"):
                saved["content"] = db_ops.save_content_report(site_id, state["content_result"])
            return {"db_result": {"action": "saved", "site": site_info, "reports": saved}}
        elif intent == "list_sites" or db_action == "list":
            return {"db_result": {"action": "list_sites", "data": db_ops.list_sites()}}
        elif db_action == "get_low_seo":
            return {"db_result": {"action": "get_low_seo", "data": db_ops.get_low_seo_sites()}}
        elif intent == "list_reports":
            return {"db_result": {"action": "list_reports", "data": db_ops.get_seo_reports()}}
        elif intent == "delete_old_reports":
            return {"db_result": {"action": "delete_old", "result": db_ops.delete_old_reports(days=int(params.get("days") or 30))}}
        elif intent == "update_score":
            rid = params.get("report_id")
            ns = params.get("new_score")
            if rid and ns is not None:
                return {"db_result": {"action": "update_score", "result": db_ops.update_seo_score(int(rid), float(ns))}}
        elif intent == "show_logs":
            return {"db_result": {"action": "show_logs", "data": db_ops.get_operation_logs(limit=20)}}
        return {"db_result": {"action": "none"}}
    except Exception as e:
        logger.error(f"DB error: {e}")
        return {"db_error": str(e), "db_result": None}

def format_response(state: AgentState) -> dict:
    parts = [f"User asked: {state['user_input']}"]
    if state.get("fetch_error"): parts.append(f"Fetch error: {state['fetch_error']}")
    if state.get("seo_result") and not state["seo_result"].get("error"):
        r = state["seo_result"]
        parts.append(f"SEO Score: {r.get('overall_score')}/100. Title: {r.get('title')} ({r.get('title_length')} chars). H1s: {r.get('h1_count')}. Missing alt: {r.get('images_missing_alt')}. Sitemap: {r.get('has_sitemap')}. Recommendations: {r.get('recommendations')}")
    if state.get("accessibility_result") and not state["accessibility_result"].get("error"):
        r = state["accessibility_result"]
        parts.append(f"Accessibility Score: {r.get('overall_score')}/100. Missing alt: {r.get('images_missing_alt')}. Missing labels: {r.get('inputs_missing_label')}. Recommendations: {r.get('recommendations')}")
    if state.get("content_result") and not state["content_result"].get("error"):
        r = state["content_result"]
        parts.append(f"Content Score: {r.get('overall_score')}/100. Words: {r.get('word_count')}. Readability: {r.get('readability_score')}. Broken links: {r.get('broken_links_count')}. Recommendations: {r.get('recommendations')}")
    if state.get("db_result"): parts.append(f"DB result: {json.dumps(state['db_result'])}")
    if state.get("db_error"): parts.append(f"DB error: {state['db_error']}")

    prompt = f"""You are a helpful SEO assistant. Write a clear friendly response with ## headers, bullets, emojis.
If scores exist include this exact line FIRST: [[SCORES:SEO=<n>,A11Y=<n>,CONTENT=<n>]]
Data: {chr(10).join(parts)}"""

    response = _client.chat.completions.create(
        model=GROQ_MODEL, max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    final_response = response.choices[0].message.content.strip()
    return {"final_response": final_response, "messages": [{"role": "user", "content": state["user_input"]}, {"role": "assistant", "content": final_response}]}
