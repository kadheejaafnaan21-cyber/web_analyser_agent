"""
agent/chatbot.py
────────────────
The high-level Chatbot class that wraps the LangGraph agent.

This is what you interact with from main.py or any UI layer.
It maintains conversation history across turns and provides a simple
chat() method.
"""

from agent.graph import agent_graph
from agent.state import AgentState
from database.connection import init_db
from utils.logger import get_logger

logger = get_logger(__name__)


class SEOChatbot:
    """
    A stateful chatbot that wraps the LangGraph SEO agent.

    Usage:
        bot = SEOChatbot()
        response = bot.chat("Analyse https://example.com")
        print(response)
    """

    def __init__(self):
        # Initialize the database (creates tables if they don't exist)
        init_db()
        # Conversation history — grows with each turn
        self.conversation_history: list[dict] = []
        logger.info("🤖 SEOChatbot initialized.")

    def chat(self, user_message: str) -> str:
        """
        Send a message to the agent and get a response.

        Args:
            user_message: The text the user typed.

        Returns:
            The agent's formatted response string.
        """
        logger.info(f"💬 User: {user_message[:100]}")

        # Build the initial state for this turn
        initial_state: AgentState = {
            "messages":              self.conversation_history.copy(),
            "user_input":            user_message,
            "intent":                "",
            "target_url":            None,
            "db_action":             None,
            "db_params":             {},
            "fetch_error":           None,
            "seo_result":            None,
            "accessibility_result":  None,
            "content_result":        None,
            "db_result":             None,
            "db_error":              None,
            "final_response":        "",
        }

        try:
            # Run the LangGraph agent — this executes all the nodes
            final_state = agent_graph.invoke(initial_state)

            # Update conversation history with the new messages
            self.conversation_history = final_state.get("messages", [])

            response = final_state.get("final_response", "Sorry, I couldn't process your request.")
            logger.info(f"🤖 Response length: {len(response)} chars")
            return response

        except Exception as e:
            error_msg = f"❌ An error occurred: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg

    def reset(self) -> None:
        """Clear conversation history (start a fresh session)."""
        self.conversation_history = []
        logger.info("Conversation history cleared.")