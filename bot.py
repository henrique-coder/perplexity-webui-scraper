# Standard modules
import asyncio
import os

# Third-party modules
import discord
from dotenv import load_dotenv
from rich.console import Console
from rich.theme import Theme

# Local imports
from perplexity import ModelType, Perplexity


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
    console.log(f"[error]Failed to initialize Perplexity client: {e}[/error]", exc_info=True)
    exit(1)

# --- Bot Configuration ---
intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

# --- Rate Limiting ---
user_rate_limit = {}
RATE_LIMIT_SECONDS = 5

# --- Model Configuration ---
# Key: Internal identifier
# Value: Tuple (ModelType object, User-facing name, Description)
AVAILABLE_MODELS = {
    "pro_best": (ModelType.Pro.Best, "Best (Auto)", "Selects the best model for each query"),
    "pro_sonar": (ModelType.Pro.Sonar, "Sonar (Pro)", "Perplexity's fast model"),
    "pro_claude37sonnet": (ModelType.Pro.Claude37Sonnet, "Claude 3.7 Sonnet (Pro)", "Anthropic's advanced model"),
    "pro_gpt4o": (ModelType.Pro.GPT4o, "GPT-4o (Pro)", "OpenAI's versatile model"),
    "pro_gemini25pro": (ModelType.Pro.Gemini25Pro, "Gemini 2.5 Pro (Pro)", "Google's latest model"),
    "pro_grok2": (ModelType.Pro.Grok2, "Grok 2 (Pro)", "xAI's latest model"),
    "pro_reasoning_r11776": (ModelType.Pro.Reasoning.R11776, "R1 (Pro & Reasoning)", "Perplexity's unbiased reasoning model"),
    "pro_reasoning_o3mini": (ModelType.Pro.Reasoning.o3mini, "GPT-4o mini (Pro & Reasoning)", "OpenAI's reasoning model"),
    "pro_reasoning_claude37sonnetthinking": (
        ModelType.Pro.Reasoning.Claude37SonnetThinking,
        "Claude 3.7 Sonnet Thinking (Pro & Reasoning)",
        "Anthropic's reasoning model",
    ),
    "deepresearch": (ModelType.DeepResearch, "Deep Research", "In-depth reports on complex topics (very slow)"),
}
DEFAULT_MODEL_KEY = "pro_best"

# Generate discord.OptionChoice list (Descriptions aren't shown in choices, only name/value)
model_choices = [
    discord.OptionChoice(name=name, value=key)
    for key, (_, name, _) in AVAILABLE_MODELS.items()  # Unpack includes description now
]


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
    model: discord.Option(str, description="Choose the AI model (optional)", required=True, choices=model_choices),
) -> None:
    user = ctx.author
    guild_name = ctx.guild.name if ctx.guild else "Direct Message"

    # 1. Rate Limit Check
    if not await check_rate_limit(user.id):
        # Use respond for final messages in a path like rate limit error
        await ctx.respond(f"⏳ Please wait {RATE_LIMIT_SECONDS} seconds before sending another query.", ephemeral=True)
        console.log(f"[warning]Rate limit hit for [highlight]{user}[/highlight] in '{guild_name}'[/warning]")

        return None

    # 2. Send Initial Custom Waiting Message
    # Use respond() here for the initial message
    await ctx.respond("⏳ Thinking... Your request is being processed by the AI, please wait a moment.", ephemeral=False)

    # 3. Determine Selected Model
    selected_model_key = model if model else DEFAULT_MODEL_KEY
    # Use get with a fallback to default model info if key is somehow invalid
    model_info = AVAILABLE_MODELS.get(selected_model_key, AVAILABLE_MODELS[DEFAULT_MODEL_KEY])

    # Unpack the model info tuple (now includes description, assigned to _)
    selected_model_type, model_display_name, _ = model_info

    console.log(f"[info]📩 Query from [highlight]{user}[/highlight] in '{guild_name}'[/info]")
    console.log(f"   Query: '{query}'")
    console.log(f"   Model: [model]{model_display_name}[/model] ({selected_model_key})")

    # 4. Process Query with AI
    try:
        # Run the AI call (this might take time)
        ai_client.ask(query=query, model=selected_model_type, save_to_library=False, language="en-US")
        response_content = ai_client.answer

        if not response_content:
            response_content = "The AI returned an empty response. Please try rephrasing your query."
            console.log(f"[warning]Empty response received for query from [highlight]{user}[/highlight][/warning]")

        # Edit the original message (sent via ctx.respond) with the final answer
        await ctx.interaction.edit_original_response(content=response_content)
        console.log(f"[success]✅ Response sent to [highlight]{user}[/highlight] in '{guild_name}'[/success]")

    except Exception as e:
        console.log(f"[error]❌ Error processing query for [highlight]{user}[/highlight]: {e}[/error]", exc_info=True)

        try:
            # Edit the original message (sent via ctx.respond) to show the error
            await ctx.interaction.edit_original_response(
                content="⚠️ An unexpected error occurred while contacting the AI. The developers have been notified."
            )
        except discord.NotFound:
            console.log(f"[warning]Could not edit original response for {user}, interaction likely expired or deleted.[/warning]")
        except Exception as edit_error:
            console.log(f"[error]Failed to edit original response with error for {user}: {edit_error}")


# --- DM Handling (Still uses default model for simplicity) ---
@bot.event
async def on_message(message: discord.Message) -> None:
    # Basic checks: ignore bots, ignore non-DMs, ignore messages not starting with /ask
    if message.author.bot or message.guild is not None or not message.content.lower().startswith("/ask "):
        return None

    user = message.author
    query = message.content[5:].strip()

    if not query:
        await message.channel.send("Please provide your query after `/ask `.")

        return None

    if not await check_rate_limit(user.id):
        await message.channel.send(f"⏳ Please wait {RATE_LIMIT_SECONDS} seconds between queries.")
        console.log(f"[warning]Rate limit hit for DM user [highlight]{user}[/highlight][/warning]")

        return None

    # Get default model info for logging and initial message
    default_model_type, default_model_name, _ = AVAILABLE_MODELS[DEFAULT_MODEL_KEY]
    console.log(
        f"[info]📩 DM Query from [highlight]{user}[/highlight]: '{query}' (Using [model]{default_model_name}[/model])[/info]"
    )

    # Send custom initial processing message for DMs
    processing_msg = await message.channel.send(
        f"⏳ Thinking... Processing your DM request using the {default_model_name} model..."
    )

    try:
        ai_client.ask(
            query=query,
            model=default_model_type,  # Use default model for DMs
            save_to_library=False,
            language="en-US",
        )
        response_content = ai_client.answer

        if not response_content:
            response_content = "The AI returned an empty response."
            console.log(f"[warning]Empty DM response received for query from [highlight]{user}[/highlight][/warning]")

        # Edit the processing message with the final answer
        await processing_msg.edit(content=response_content)
        console.log(f"[success]✅ DM Response sent to [highlight]{user}[/highlight][/success]")

    except Exception as e:
        console.log(f"[error]❌ Error processing DM query for [highlight]{user}[/highlight]: {e}[/error]", exc_info=True)

        try:
            await processing_msg.edit(content="⚠️ An unexpected error occurred while processing your query in DMs.")
        except Exception as edit_error:
            console.log(f"[error]Failed to edit DM error message for {user}: {edit_error}")


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
        console.log(
            f"[error]❌ An attribute error occurred, possibly due to an incorrect ModelType structure: {e}[/error]", exc_info=True
        )
    except Exception as e:
        console.log(f"[error]❌ An unexpected error occurred during bot startup or runtime: {e}[/error]", exc_info=True)
    finally:
        console.log("[info]⏹ Bot shutdown process initiated.[/info]")
