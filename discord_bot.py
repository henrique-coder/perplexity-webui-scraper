# Standard modules
import asyncio
import io
import os
from sys import exit

# Third-party modules
import discord
from dotenv import load_dotenv
from rich.console import Console
from rich.theme import Theme

# Local imports
from src.perplexity_webui_scraper import ModelType, Perplexity


# --- Rich Console Setup ---
custom_theme = Theme({
    "info": "cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "highlight": "bold magenta",
    "model": "blue",
})
console = Console(theme=custom_theme)

# --- Load Environment Variables ---
load_dotenv()
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PERPLEXITY_SESSION_TOKEN = os.getenv("PERPLEXITY_SESSION_TOKEN")

if not BOT_TOKEN:
    console.log("[error]DISCORD_BOT_TOKEN not found in .env file![/error]")
    exit(1)
if not PERPLEXITY_SESSION_TOKEN:
    console.log("[error]PERPLEXITY_SESSION_TOKEN not found in .env file![/error]")
    exit(1)

# --- Initialize Perplexity Client ---
try:
    ai_client = Perplexity(session_token=PERPLEXITY_SESSION_TOKEN)
    console.log("[success]Perplexity client initialized successfully.[/success]")
except Exception as e:
    console.log(f"[error]Failed to initialize Perplexity client: {e}[/error]")
    exit(1)

# --- Bot Configuration ---
intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

# --- Constants ---
RATE_LIMIT_SECONDS = 5
MESSAGE_CHARACTER_LIMIT = 2000

# --- Rate Limiting ---
user_rate_limit = {}

# --- Model Configuration ---
# Key: Internal identifier
# Value: Tuple (ModelType object, User-facing name, Description)
AVAILABLE_MODELS = {
    "pro_best": (ModelType.Pro.Best, "Best (Auto & Pro)"),
    "pro_sonar": (ModelType.Pro.Sonar, "Sonar (Pro)"),
    "pro_claude40sonnet": (ModelType.Pro.Claude40Sonnet, "Claude 4.0 Sonnet (Pro)"),
    "pro_gpt41": (ModelType.Pro.GPT41, "GPT-4.1 (Pro)"),
    "pro_gemini25pro": (ModelType.Pro.Gemini25Pro, "Gemini 2.5 Pro (Pro)"),
    "pro_grok3beta": (ModelType.Pro.Grok3Beta, "Grok 2 (Pro)"),
    "pro_reasoning_r11776": (ModelType.Pro.Reasoning.R11776, "R1 (Pro & Reasoning)"),
    "pro_reasoning_o4mini": (ModelType.Pro.Reasoning.o4mini, "o4 mini (Pro & Reasoning)"),
    "pro_reasoning_claude40sonnetthinking": (
        ModelType.Pro.Reasoning.Claude40SonnetThinking,
        "Claude 4.0 Sonnet Thinking (Pro & Reasoning)",
    ),
    "research": (ModelType.Research, "Research"),
}
DEFAULT_MODEL_KEY = "pro_best"

model_choices = [discord.OptionChoice(name=name, value=key) for key, (_, name) in AVAILABLE_MODELS.items()]


async def check_rate_limit(user_id: int) -> bool:
    now = asyncio.get_event_loop().time()

    if now - user_rate_limit.get(user_id, 0) < RATE_LIMIT_SECONDS:
        return False

    user_rate_limit[user_id] = now

    return True


# --- Bot Events ---
@bot.event
async def on_ready() -> None:
    console.log(f"[success]✔ Bot authenticated as [highlight]{bot.user}[/highlight] (ID: {bot.user.id})")
    console.log(f"[info]↳ Pycord version: {discord.__version__}")
    console.log("[success]Perplexity AI Scraper is ready and listening!")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/ask"))


# --- Slash Command ---
@bot.slash_command(name="ask", description="Ask Perplexity AI anything, optionally choosing a specific model.")
async def ask(
    ctx: discord.ApplicationContext,
    query: discord.Option(str, description="Your question for the AI", required=True),
    model: discord.Option(
        str, description="Choose the AI model. Defaults to 'Best (Auto & Pro)'", required=False, choices=model_choices
    ),
) -> None:
    user = ctx.author
    guild_name = ctx.guild.name if ctx.guild else "Direct Message"

    # 1. Rate Limit Check
    if not await check_rate_limit(user.id):
        await ctx.respond(f"⏳ Please wait {RATE_LIMIT_SECONDS} seconds before sending another query.", ephemeral=True)
        console.log(f"[warning]Rate limit hit for [highlight]{user}[/highlight] in '{guild_name}'[/warning]")
        return

    # 2. Defer Interaction (shows "Bot is thinking...")
    await ctx.defer(ephemeral=False)

    # 3. Determine Selected Model
    selected_model_key = model if model else DEFAULT_MODEL_KEY
    model_info = AVAILABLE_MODELS.get(selected_model_key, AVAILABLE_MODELS[DEFAULT_MODEL_KEY])
    selected_model_type, model_display_name, model_description = model_info

    console.log(f"[info]📩 Query from [highlight]{user}[/highlight] in '{guild_name}'[/info]")
    console.log(f"   Query: '{query}'")
    console.log(f"   Model: [model]{model_display_name}[/model] ({selected_model_key})")

    # 4. Process Query with AI
    try:
        ai_client.ask(query=query, model=selected_model_type, save_to_library=False, language="en-US")
        response_content = ai_client.answer
        search_results = ai_client.search_results

        if search_results:
            search_results_str = ", ".join(f"[[{i + 1}]](<{result['url']}>)" for i, result in enumerate(search_results))
            search_results = f"\n\n**Search Results**: {search_results_str}"

        full_response = f"{response_content}{search_results or ''}"

        if not full_response.strip():
            response_content = "The AI returned an empty response. Please try rephrasing your query."
            console.log(f"[warning]Empty response received for query from [highlight]{user}[/highlight][/warning]")
            # Send short empty response directly
            await ctx.followup.send(content=response_content)

        # --- Check response length and send accordingly ---
        elif len(full_response) <= MESSAGE_CHARACTER_LIMIT:
            # Send response normally if within limit
            await ctx.followup.send(content=full_response)
        else:
            # Send response as a file if over limit
            console.log(f"[warning]Response exceeded character limit ({len(response_content)} chars). Sending as file.[/warning]")
            # Create file-like object in memory
            response_bytes = io.BytesIO(response_content.encode("utf-8"))
            # Create discord.File object
            response_file = discord.File(response_bytes, filename="perplexity.md")
            # Send the file using followup
            await ctx.followup.send(
                content=f"The AI response was too long to display directly. See the attached file.{search_results}",
                file=response_file,
            )

        console.log(f"[success]✅ Response sent to [highlight]{user}[/highlight] in '{guild_name}'[/success]")
    except Exception as e:
        console.log(f"[error]❌ Error processing query for [highlight]{user}[/highlight]: {e}[/error]")

        try:
            # Use followup for errors after defer()
            await ctx.followup.send(
                "⚠️ An unexpected error occurred while contacting the AI. The developers have been notified.", ephemeral=True
            )
        except discord.NotFound:
            console.log(f"[warning]Could not send error followup to {user}, interaction likely expired.[/warning]")
        except Exception as followup_error:
            console.log(f"[error]Failed to send error followup to {user}: {followup_error}")


# --- Main Execution ---
if __name__ == "__main__":
    console.log("[info]🚀 Starting Perplexity AI Scraper...[/info]")

    try:
        bot.run(BOT_TOKEN)
    except discord.LoginFailure:
        console.log("[error]❌ Invalid DISCORD_BOT_TOKEN. Please check your .env file.[/error]")
    except ImportError as e:
        console.log(f"[error]❌ Failed to import a required library: {e}. Ensure all dependencies are installed.[/error]")
    except AttributeError as e:
        console.log(f"[error]❌ An attribute error occurred, possibly due to an incorrect ModelType structure: {e}[/error]")
    except Exception as e:
        console.log(f"[error]❌ An unexpected error occurred during bot startup or runtime: {e}[/error]")
    finally:
        console.log("[info]⏹ Bot shutdown process initiated.[/info]")
