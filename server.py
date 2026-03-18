"""
server.py
─────────
Flask API server that connects the frontend to the LangGraph SEO agent.

Run this instead of main.py when using the frontend:
    python server.py

Then open frontend/index.html in your browser.

Endpoints:
    POST /chat        → send a message, get agent response
    GET  /health      → check if server is running
    GET  /history     → get conversation history
    POST /reset       → clear conversation history
"""

import re

from flask import Flask, request, jsonify
from flask_cors import CORS

from agent.chatbot import SEOChatbot
from database.connection import init_db
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Flask app setup ───────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, origins="*")

# ── Single chatbot instance (maintains conversation history) ──────────────────
bot = SEOChatbot()
logger.info("🚀 Flask server starting...")


# ═════════════════════════════════════════════════════════════════════════════
# Score extraction — injects [[SCORES:...]] tag for the frontend score cards
# ═════════════════════════════════════════════════════════════════════════════

def _extract_scores(text: str) -> tuple:
    """
    Try to pull SEO, Accessibility and Content scores out of the agent response.
    Covers many formatting styles the LLM might use.
    Returns (seo, a11y, content) — each a string or None.
    """
    def _find(*patterns):
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    seo = _find(
        r'seo\s+score[:\s]+(\d+(?:\.\d+)?)',
        r'\*\*seo[^*]*\*\*[:\s]+(\d+(?:\.\d+)?)',
        r'seo[:\s]+(\d+(?:\.\d+)?)\s*/\s*100',
        r'seo[:\s]+(\d+(?:\.\d+)?)',
        r'📊[^:]*seo[^:]*:\s*(\d+(?:\.\d+)?)',
        r'seo.*?(\d+(?:\.\d+)?)\s*/\s*100',
    )

    a11y = _find(
        r'accessibility\s+score[:\s]+(\d+(?:\.\d+)?)',
        r'\*\*accessibility[^*]*\*\*[:\s]+(\d+(?:\.\d+)?)',
        r'accessibility[:\s]+(\d+(?:\.\d+)?)\s*/\s*100',
        r'accessibility[:\s]+(\d+(?:\.\d+)?)',
        r'♿[^:]*:\s*(\d+(?:\.\d+)?)',
        r'accessibility.*?(\d+(?:\.\d+)?)\s*/\s*100',
    )

    cont = _find(
        r'content\s+(?:quality\s+)?score[:\s]+(\d+(?:\.\d+)?)',
        r'\*\*content[^*]*\*\*[:\s]+(\d+(?:\.\d+)?)',
        r'content[:\s]+(\d+(?:\.\d+)?)\s*/\s*100',
        r'content\s+quality[:\s]+(\d+(?:\.\d+)?)',
        r'📝[^:]*:\s*(\d+(?:\.\d+)?)',
        r'content.*?(\d+(?:\.\d+)?)\s*/\s*100',
    )

    return seo, a11y, cont


def _inject_scores(response: str) -> str:
    """
    If the response contains SEO/accessibility/content scores, prepend the
    [[SCORES:...]] marker that index.html uses to render the score cards.
    """
    seo, a11y, cont = _extract_scores(response)

    # ── DEBUG: always log what was found so you can tune patterns ────────────
    logger.info(f"📊 SCORE EXTRACTION → SEO={seo} | A11Y={a11y} | CONTENT={cont}")
    logger.info(f"📝 RAW RESPONSE (first 400 chars):\n{response[:400]}")
    # ─────────────────────────────────────────────────────────────────────────

    if seo and a11y and cont:
        tag = f"[[SCORES:SEO={seo},A11Y={a11y},CONTENT={cont}]]"
        return f"{tag}\n{response}"
    return response


# ═════════════════════════════════════════════════════════════════════════════
# Routes
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    """Simple health check — frontend pings this to confirm server is alive."""
    return jsonify({
        "status": "ok",
        "message": "SEO Agent server is running ✅",
        "conversation_turns": len(bot.conversation_history) // 2,
    })


@app.route("/chat", methods=["POST"])
def chat():
    """
    Main chat endpoint.

    Request body (JSON):
        { "message": "Analyse https://example.com" }

    Response (JSON):
        { "response": "[[SCORES:...]]## SEO Report...", "success": true }
    """
    data = request.get_json()

    if not data or not data.get("message"):
        return jsonify({
            "success": False,
            "error": "Missing 'message' field in request body."
        }), 400

    user_message = data["message"].strip()
    if not user_message:
        return jsonify({"success": False, "error": "Message cannot be empty."}), 400

    logger.info(f"📨 /chat → '{user_message[:80]}'")

    try:
        response = bot.chat(user_message)
        enriched = _inject_scores(response)
        return jsonify({
            "success": True,
            "response": enriched,
            "conversation_turns": len(bot.conversation_history) // 2,
        })
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
            "response": f"❌ Agent error: {str(e)}"
        }), 500


@app.route("/history", methods=["GET"])
def history():
    """Return the full conversation history."""
    return jsonify({
        "success": True,
        "history": bot.conversation_history,
        "turns": len(bot.conversation_history) // 2,
    })


@app.route("/reset", methods=["POST"])
def reset():
    """Clear conversation history and start fresh."""
    bot.reset()
    return jsonify({"success": True, "message": "Conversation history cleared."})


# ═════════════════════════════════════════════════════════════════════════════
# Run
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  🤖 SEO Agent API Server")
    print("="*55)
    print("  Backend: http://localhost:5000")
    print("  Health:  http://localhost:5000/health")
    print("  Chat:    POST http://localhost:5000/chat")
    print("-"*55)
    print("  Now open: frontend/index.html in your browser")
    print("="*55 + "\n")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False,
    )