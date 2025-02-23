import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
from dotenv import load_dotenv
from google import genai
import requests
from PIL import Image
from io import BytesIO
import pathlib
import re
from __future__ import annotations


# --- Load environment variables ---
current_file_path = pathlib.Path(__file__).parent.resolve()
dotenv_path = current_file_path / "config.env"
load_dotenv(dotenv_path)

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini API with Client for v1alpha
client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1alpha'})

# Persona definitions
AOLMAN_SYSTEM_INSTRUCTION = "You are AOLMAN. Speak in wild, playful misspellings and phonetic twists. Replace letters with numbers or alternate characters (e.g., 'P00T' for 'put', 'TEH' for 'the'), mix up vowels, and abandon strict grammar. Employ all caps for emphasis. Overuse exclamation points, and insider slang like 'WAREZ' or 'GIFPASTE.' Inject humor with absurd, made-up words and a chaotic, stream-of-consciousness vibe. Alter existing terms (e.g., 'PHISHEZZ'). Keep sentences short and punchy: Use concise phrases with exclamation marks. Inject humor or sarcasm: Add playful elements to your speech, and be extra rude, vulgar, inflammatory, abusive and aggressive."
LEET_SYSTEM_INSTRUCTION = "You are a gamer responding in LEETSPEAK. Replace letters with numbers & symbols (A=4, S=5, T=7). Swap I=1, O=0. Use “u” for you, “2” for to/too, “n00b” for newbie. Caps randomly & combine them: “h4x0r5 r0xx!” Keep it short & edgy."


def get_system_instruction(persona: str) -> str | None:
    if persona.upper() == "AOLMAN":
        return AOLMAN_SYSTEM_INSTRUCTION
    elif persona.upper() == "LEET":
        return LEET_SYSTEM_INSTRUCTION
    return None


# --- Discord bot setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"), intents=intents)

# Store chat sessions
chat_sessions_mentions = {}  # Shared sessions for @FragBot mentions
chat_sessions_slash = {}  # Per-user sessions for slash commands


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    print("------")


def split_message(text: str, limit: int = 2000) -> list[str]:
    """Splits text into chunks at paragraph or word boundaries, preserving newlines."""
    if len(text) <= limit:
        return [text]

    chunks = []
    current_chunk = ""
    paragraphs = text.split("\n")

    for paragraph in paragraphs:
        if not paragraph.strip():
            if current_chunk and len(current_chunk) + 1 <= limit:
                current_chunk += "\n"
            continue

        if len(current_chunk) + len(paragraph) + (1 if current_chunk else 0) <= limit:
            current_chunk += ("\n" + paragraph if current_chunk else paragraph)
        else:
            words = paragraph.split()
            for word in words:
                if len(current_chunk) + len(word) + (1 if current_chunk else 0) <= limit:
                    current_chunk += (" " + word if current_chunk and not current_chunk.endswith("\n") else word)
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = word
            if current_chunk and len(current_chunk) + 1 <= limit:
                current_chunk += "\n"

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


async def animate_thinking(message: discord.Message):
    """Animates a 'Thinking...' message with dots until cancelled."""
    dots = ["Thinking.", "Thinking..", "Thinking..."]
    i = 0
    while True:
        await message.edit(content=dots[i % 3])
        i += 1
        await asyncio.sleep(0.5)


async def process_chat_response(chat, content, channel, interaction=None, user_mention: str = None):
    """Helper function to send a response with live edits, handling both mentions and slash commands."""
    max_retries = 5
    retry_delay = 1
    limit = 2000  # Discord message limit

    prefix = f"{user_mention} " if user_mention else ""

    for attempt in range(max_retries):
        try:
            # Send message asynchronously (non-streaming for thinking model)
            response = await chat.send_message(content)
            full_response = response.text
            message_chunks = split_message(full_response, limit - len(prefix))

            if interaction:  # Slash command: edit the deferred response
                # Send the first chunk
                await interaction.edit_original_response(content=message_chunks[0])
                # Send remaining chunks as follow-ups if needed
                for chunk in message_chunks[1:]:
                    await asyncio.sleep(1)  # Delay between chunks
                    await interaction.followup.send(chunk)
            else:  # Mention: send to channel
                # Send the first chunk and simulate streaming
                current_message = await channel.send(prefix + "...")
                await asyncio.sleep(1)  # Initial delay for live effect
                await current_message.edit(content=prefix + message_chunks[0])
                # Send remaining chunks as new messages
                for chunk in message_chunks[1:]:
                    await asyncio.sleep(1)  # Delay between chunks
                    current_message = await channel.send(prefix + chunk)

            # Debug: Print chat history after message
            print("Chat history after message:")
            for msg in chat._curated_history:
                print(f"role - {msg.role}: {msg.parts[0].text}")
            return current_message if not interaction else None
        except Exception as e:
            if "503" in str(e) and attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed: {e}. Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                error_msg = f"{user_mention} An error occurred: {e}" if user_mention else f"An error occurred: {e}"
                if interaction:
                    await interaction.edit_original_response(content=error_msg)
                else:
                    await channel.send(error_msg)
                return None


def is_image_url(url: str) -> bool:
    """Checks if a URL likely points to an image based on common extensions."""
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp')
    return url.lower().endswith(image_extensions)


async def fetch_image_from_url(url: str) -> Image.Image | None:
    """Fetches an image from a URL and returns a PIL Image object, or None if it fails."""
    try:
        response = requests.get(url, stream=True, timeout=5)
        response.raise_for_status()
        image_data = BytesIO(response.content)
        return Image.open(image_data)
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"Failed to fetch image from {url}: {e}")
        return None


@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    if bot.user in message.mentions:
        user_id = message.author.id
        channel_id = message.channel.id
        session_key = channel_id  # Shared session for mentions
        user_mention = f"<@{user_id}>"

        print(f"Session key (mentions): {session_key}")

        # Parse persona and text content
        text_content = message.content.replace(f"<@{bot.user.id}>", "").strip()
        words = text_content.split()
        persona = "normal"
        if words and words[0].upper() in ["AOLMAN", "LEET"]:
            persona = words[0].upper()
            text_content = " ".join(words[1:]).strip()

        # Initialize or retrieve the shared chat session for mentions
        if session_key not in chat_sessions_mentions:
            chat = client.aio.chats.create(model="gemini-2.0-flash-thinking-exp")
            system_instruction = get_system_instruction(persona)
            if system_instruction:
                await chat.send_message(system_instruction)
            chat_sessions_mentions[session_key] = (chat, persona)
            print(f"New chat created for {session_key} with persona: {persona}")
        else:
            chat, current_persona = chat_sessions_mentions[session_key]
            system_instruction = get_system_instruction(persona)
            if persona != current_persona and system_instruction != get_system_instruction(current_persona):
                chat = client.aio.chats.create(model="gemini-2.0-flash-thinking-exp")
                if system_instruction:
                    await chat.send_message(system_instruction)
                chat_sessions_mentions[session_key] = (chat, persona)
                print(f"Chat reset for {session_key} due to persona change: {current_persona} -> {persona}")
            else:
                print(f"Reusing chat for {session_key} with persona: {current_persona}")

        chat, _ = chat_sessions_mentions[session_key]

        print("Chat history before message (mentions):")
        for msg in chat._curated_history:
            print(f"role - {msg.role}: {msg.parts[0].text}")

        # Process message content
        attachments = message.attachments
        url_pattern = r'https?://\S+'
        urls = re.findall(url_pattern, text_content)
        image_urls = [url for url in urls if is_image_url(url)]
        text_content = re.sub(url_pattern, "", text_content).strip()

        content = [text_content] if text_content else []
        has_images = False

        for attachment in attachments:
            if attachment.content_type.startswith("image/"):
                response = requests.get(attachment.url, stream=True)
                response.raise_for_status()
                image_data = BytesIO(response.content)
                image = Image.open(image_data)
                content.append(image)
                has_images = True

        for url in image_urls:
            image = await fetch_image_from_url(url)
            if image:
                content.append(image)
                has_images = True

        if has_images and not content:
            content = ["Look and opine"]

        if content:
            # Send "Thinking..." message and animate it
            thinking_message = await message.channel.send("Thinking...")
            thinking_task = asyncio.create_task(animate_thinking(thinking_message))

            # Process the response
            await process_chat_response(chat, content, message.channel, user_mention=user_mention)

            # Cancel animation and delete thinking message
            thinking_task.cancel()
            try:
                await thinking_message.delete()
            except asyncio.CancelledError:
                pass

        else:
            await message.channel.send(f"{user_mention} Mention me with some text or an image to get a response!")


# --- Slash Commands ---

@bot.tree.command(name="ask", description="Ask FragAI a question.")
@discord.app_commands.describe(
    question="Your question for FragAI.",
    persona="Choose a persona."
)
@app_commands.choices(persona=[
    discord.app_commands.Choice(name="Normal", value="normal"),
    discord.app_commands.Choice(name="AOLMAN", value="AOLMAN"),
    discord.app_commands.Choice(name="LEET", value="LEET"),
])
async def ask(interaction: discord.Interaction, question: str, persona: str = "normal"):
    await interaction.response.defer(thinking=True)

    user_id = interaction.user.id
    channel_id = interaction.channel.id
    session_key = (user_id, channel_id)

    print(f"Session key (slash): {session_key}")

    if session_key not in chat_sessions_slash:
        chat = client.aio.chats.create(model="gemini-2.0-flash-thinking-exp")
        system_instruction = get_system_instruction(persona)
        if system_instruction:
            await chat.send_message(system_instruction)
        chat_sessions_slash[session_key] = (chat, persona)
        print(f"New chat created for {session_key} with persona: {persona}")
    else:
        chat, current_persona = chat_sessions_slash[session_key]
        system_instruction = get_system_instruction(persona)
        if persona != current_persona and system_instruction != get_system_instruction(current_persona):
            chat = client.aio.chats.create(model="gemini-2.0-flash-thinking-exp")
            if system_instruction:
                await chat.send_message(system_instruction)
            chat_sessions_slash[session_key] = (chat, persona)
            print(f"Chat reset for {session_key} due to persona change: {current_persona} -> {persona}")
        else:
            print(f"Reusing chat for {session_key} with persona: {current_persona}")

    chat, _ = chat_sessions_slash[session_key]

    print("Chat history before message (slash):")
    for message in chat._curated_history:
        print(f"role - {message.role}: {message.parts[0].text}")

    await process_chat_response(chat, question, interaction.channel, interaction=interaction)


@bot.tree.command(name="see", description="Ask Gemini about an image.")
@discord.app_commands.describe(
    image_url="URL of the image.",
    question="Optional question about the image.",
    persona="Choose a persona."
)
@app_commands.choices(persona=[
    discord.app_commands.Choice(name="Normal", value="normal"),
    discord.app_commands.Choice(name="AOLMAN", value="AOLMAN"),
    discord.app_commands.Choice(name="LEET", value="LEET"),
])
async def see(interaction: discord.Interaction, image_url: str, question: str = None, persona: str = "normal"):
    await interaction.response.defer(thinking=True)

    user_id = interaction.user.id
    channel_id = interaction.channel.id
    session_key = (user_id, channel_id)

    print(f"Session key (slash): {session_key}")

    if session_key not in chat_sessions_slash:
        chat = client.aio.chats.create(model="gemini-2.0-flash-thinking-exp")
        system_instruction = get_system_instruction(persona)
        if system_instruction:
            await chat.send_message(system_instruction)
        chat_sessions_slash[session_key] = (chat, persona)
        print(f"New chat created for {session_key} with persona: {persona}")
    else:
        chat, current_persona = chat_sessions_slash[session_key]
        system_instruction = get_system_instruction(persona)
        if persona != current_persona and system_instruction != get_system_instruction(current_persona):
            chat = client.aio.chats.create(model="gemini-2.0-flash-thinking-exp")
            if system_instruction:
                await chat.send_message(system_instruction)
            chat_sessions_slash[session_key] = (chat, persona)
            print(f"Chat reset for {session_key} due to persona change: {current_persona} -> {persona}")
        else:
            print(f"Reusing chat for {session_key} with persona: {current_persona}")

    chat, _ = chat_sessions_slash[session_key]

    print("Chat history before message (slash):")
    for message in chat._curated_history:
        print(f"role - {message.role}: {message.parts[0].text}")

    try:
        response = requests.get(image_url, stream=True)
        response.raise_for_status()
        image_data = BytesIO(response.content)
        image = Image.open(image_data)
        content = [question if question else "Look and opine", image]
        await process_chat_response(chat, content, interaction.channel, interaction=interaction)
    except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as e:
        print(f"Image fetch error: {e}")
        await interaction.edit_original_response(content=f"Error fetching image: {e}")


@bot.tree.command(name="bothelp", description="Show help information.")
async def bothelp(interaction: discord.Interaction):
    """Provides a description of the bot's commands."""
    help_message = (
        "**Available Commands:**\n\n"
        "`/ask <question> [persona]` - Ask Gemini a question privately with `persona` (Normal, AOLMAN, LEET).\n"
        "`/see <image_url> [question] [persona]` - Ask about an image privately with optional question and `persona`.\n"
        "`/bothelp` - Show this help message.\n"
        "`@FragBot [persona] <text>` - Chat publicly in the channel with optional `persona` (AOLMAN, LEET) and text.\n"
        "`@FragBot [persona]` with image(s) or URL(s) - Chat publicly with optional `persona`, image attachments, or image URLs (add text for a question)."
    )
    await interaction.response.send_message(help_message, ephemeral=True)


# Run the bot
bot.run(DISCORD_BOT_TOKEN)
