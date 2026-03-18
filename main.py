"""
main.py
───────
Entry point for the LangGraph SEO Agent chatbot.

Run modes:
  python main.py          → interactive chat loop
  python main.py --demo   → run 5 pre-built demo scenarios automatically
"""
import argparse
import sys
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from agent.chatbot import SEOChatbot

console = Console()


# ═════════════════════════════════════════════════════════════════════════════
# Demo scenarios — showcases 5 real-world use cases
# ═════════════════════════════════════════════════════════════════════════════

DEMO_SCENARIOS = [
    # Scenario 1: Full website analysis + auto-save to DB
    {
        "title": "📊 Scenario 1: Full Website Analysis",
        "message": "Analyse the SEO, accessibility and content quality of https://example.com",
    },
    # Scenario 2: Show all sites with low SEO scores
    {
        "title": "🔍 Scenario 2: Find Low-SEO Sites",
        "message": "Show me all sites with low SEO scores",
    },
    # Scenario 3: List all registered sites
    {
        "title": "📋 Scenario 3: List All Sites",
        "message": "List all registered sites in the database",
    },
    # Scenario 4: Delete old reports
    {
        "title": "🗑️  Scenario 4: Delete Old Reports",
        "message": "Delete all reports older than 30 days",
    },
    # Scenario 5: View audit logs
    {
        "title": "📜 Scenario 5: View Operation Logs",
        "message": "Show me the recent database operation logs",
    },
]


# ═════════════════════════════════════════════════════════════════════════════
# Main functions
# ═════════════════════════════════════════════════════════════════════════════

def run_demo(bot: SEOChatbot) -> None:
    """Run all demo scenarios automatically."""
    console.print(Panel.fit(
        "[bold cyan]🚀 Running Demo Scenarios[/bold cyan]\n"
        "This will demonstrate 5 real-world use cases of the SEO Agent.",
        border_style="cyan",
    ))

    for i, scenario in enumerate(DEMO_SCENARIOS, 1):
        console.print(f"\n[bold yellow]{scenario['title']}[/bold yellow]")
        console.print(f"[dim]Query: {scenario['message']}[/dim]\n")

        response = bot.chat(scenario["message"])
        console.print(Markdown(response))
        console.print("[dim]─" * 60)

        if i < len(DEMO_SCENARIOS):
            input("\nPress Enter for next scenario...")

    console.print("\n[bold green]✅ All demo scenarios completed![/bold green]")


def run_interactive(bot: SEOChatbot) -> None:
    """Run an interactive chat loop."""
    console.print(Panel.fit(
        "[bold green]🤖 SEO & Accessibility Agent[/bold green]\n"
        "[dim]Powered by LangGraph + Claude[/dim]\n\n"
        "Commands:\n"
        "  • Type any message to chat\n"
        "  • 'demo' — run demo scenarios\n"
        "  • 'reset' — clear conversation history\n"
        "  • 'quit' or 'exit' — exit",
        border_style="green",
    ))

    console.print("\n[bold]Example queries you can try:[/bold]")
    examples = [
        "Analyse https://example.com for SEO issues",
        "Store SEO results of https://python.org",
        "Show me all sites with low SEO scores",
        "List all registered sites",
        "Delete reports older than 30 days",
        "Show me the recent database logs",
        "Update SEO score for report ID 1 to 85",
    ]
    for ex in examples:
        console.print(f"  [cyan]→[/cyan] {ex}")

    console.print()

    while True:
        try:
            user_input = Prompt.ask("[bold green]You[/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Goodbye! 👋[/yellow]")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            console.print("[yellow]Goodbye! 👋[/yellow]")
            break

        if user_input.lower() == "reset":
            bot.reset()
            console.print("[green]✅ Conversation history cleared.[/green]")
            continue

        if user_input.lower() == "demo":
            run_demo(bot)
            continue

        console.print("\n[dim]Thinking...[/dim]")
        response = bot.chat(user_input)
        console.print()
        console.print(Panel(
            Markdown(response),
            title="[bold blue]Agent[/bold blue]",
            border_style="blue",
        ))
        console.print()


# ═════════════════════════════════════════════════════════════════════════════
# Entry point
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="LangGraph SEO & Accessibility Agent"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run pre-built demo scenarios instead of interactive mode",
    )
    args = parser.parse_args()

    # Check API key
    from config.settings import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your_anthropic_api_key_here":
        console.print(
            "[bold red]❌ Error:[/bold red] ANTHROPIC_API_KEY not set.\n"
            "Copy .env.example to .env and add your API key:\n"
            "  cp .env.example .env\n"
            "  # Edit .env and set ANTHROPIC_API_KEY=sk-ant-..."
        )
        sys.exit(1)

    bot = SEOChatbot()

    if args.demo:
        run_demo(bot)
    else:
        run_interactive(bot)


if __name__ == "__main__":
    main()