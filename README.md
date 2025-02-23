# FragBot README

FragBot is a versatile Discord bot powered by the Gemini API, designed to chat, analyze images, and respond in unique personas like AOLMAN and LEET. Just for funsies

## 1. Features of the Bot and How to Use

FragBot offers multiple ways to interact, with support for text, images, and customizable personas. Here’s what it can do and how to use it:

### Features
- **Text Chat**: Ask questions or chat publicly by mentioning the bot or privately via slash commands.
- **Image Analysis**: Share images via attachments or URLs, and FragBot will respond with comments or answers to your questions.
- **Personas**: Switch between a normal tone or quirky styles:
  - **AOLMAN**: Wild, misspelled, chaotic ‘90s internet vibes (e.g., "H3Y N00B!!! PHISHEZZ R TEH W0RST").
  - **LEET**: Gamer-style LEETSPEAK (e.g., "h4x0r5 r0xx n00b5 suxx0r").
  - **Normal**: Straightforward and clean responses.
- **Session Memory**: Remembers conversations per channel (for mentions) or per user (for slash commands).
- **Help Command**: Get a quick rundown of commands anytime.

### How to Use
- **Public Chat**: Mention the bot with `@FragBot [persona] <text>` (e.g., `@FragBot AOLMAN wuts up`). Add images via attachments or URLs for analysis.
- **Slash Commands**:
  - `/ask <question> [persona]` - Private Q&A (e.g., `/ask What’s the weather like? LEET`).
  - `/see <image_url> [question] [persona]` - Analyze an image (e.g., `/see https://example.com/cat.jpg What’s this? AOLMAN`).
  - `/bothelp` - See command details (ephemeral response).
- **Image Handling**: Attach images or include image URLs (e.g., `.jpg`, `.png`) in your message. Add text for context if desired.

**Tips**:
- Persona is optional; defaults to "Normal" if omitted.
- Responses animate with a "Thinking..." effect before delivering the full reply.
- Long replies split into chunks for Discord’s 2000-character limit.

## 2. How to Install the Bot

Setting up FragBot requires a few dependencies and configuration steps. Here’s how to get it running:

### Prerequisites
- Python 3.8+
- A Discord bot token (create one at [Discord Developer Portal](https://discord.com/developers/applications)).
- A Gemini API key (get one from Google’s Gemini API documentation).
- Git (optional, for cloning).

### Steps
1. **Clone or Download**:
   - Clone the repo: `git clone <repository-url>` or download the code manually.
   - Navigate to the project folder: `cd <folder-name>`.

2. **Install Dependencies**:
   - Run: `pip install discord.py google-genai requests pillow python-dotenv`.
   - These handle Discord integration, Gemini API, image processing, and environment variables.

3. **Set Up Environment Variables**:
   - Create a `config.env` file in the project root.
   - Add:
     ```
     DISCORD_BOT_TOKEN=your-discord-bot-token-here
     GEMINI_API_KEY=your-gemini-api-key-here
     ```
   - Replace placeholders with your actual keys.

4. **Run the Bot**:
   - Execute: `python bot.py` (assuming the script is named `bot.py`).
   - You’ll see logs like “Logged in as FragBot#1234” when it’s online.

5. **Invite to Server**:
   - In the Discord Developer Portal, go to your bot’s application > OAuth2 > URL Generator.
   - Select `bot` and `applications.commands` scopes, then permissions like `Send Messages` and `Read Message History`.
   - Use the generated URL to invite the bot to your server.

**Troubleshooting**:
- Ensure `config.env` is in the same directory as the script.
- Check for typos in tokens/keys if the bot fails to start.

## 3. How to Add Personas

FragBot’s personas are defined in the code and can be expanded easily. Here’s how to create and integrate new ones:

### Steps
1. **Define the Persona**:
   - In the script, add a new system instruction string under "Persona definitions". Example:
     ```python
     PIRATE_SYSTEM_INSTRUCTION = "Ye be a salty pirate! Speak in pirate lingo, arr! Use 'ye', 'matey', and 'shiver me timbers'. Be rowdy and bold."
     ```

2. **Update `get_system_instruction`**:
   - Modify the function to recognize your persona:
     ```python
     def get_system_instruction(persona: str) -> str | None:
         if persona.upper() == "AOLMAN":
             return AOLMAN_SYSTEM_INSTRUCTION
         elif persona.upper() == "LEET":
             return LEET_SYSTEM_INSTRUCTION
         elif persona.upper() == "PIRATE":  # New persona
             return PIRATE_SYSTEM_INSTRUCTION
         return None
     ```

3. **Add to Slash Command Choices**:
   - Update the `persona` choices in `/ask` and `/see` commands:
     ```python
     @app_commands.choices(persona=[
         discord.app_commands.Choice(name="Normal", value="normal"),
         discord.app_commands.Choice(name="AOLMAN", value="AOLMAN"),
         discord.app_commands.Choice(name="LEET", value="LEET"),
         discord.app_commands.Choice(name="PIRATE", value="PIRATE"),  # New choice
     ])
     ```

4. **Test It**:
   - Restart the bot and try `@FragBot PIRATE ye scurvy dogs` or `/ask Where’s me treasure? PIRATE`.
   - The bot will adopt the new persona’s style.

**Tips**:
- Keep system instructions concise but descriptive to shape the tone.
- Personas persist per session; switching resets the chat context.
- Sync commands after changes: Restarting the bot usually triggers this, or use a manual sync if needed.
