# Discord Bot

A Discord bot with music player functionality and Telegram integration.

## Features

### Music Player
- Play music from YouTube, SoundCloud, and other supported platforms
- Queue management with shuffle support
- Interactive UI with buttons for playback control
- Lyrics fetching via lrclib.net
- Auto-disconnect after 5 minutes of inactivity
- Per-server queue management

### Voice State Notifications
- Notifies Telegram when users join/leave voice channels
- Tracks user movements between voice channels

## Setup

1. **Environment Variables**
   Create a `.env` file in the project root:
   ```
   DISCORD_TOKEN=your_discord_bot_token
   TELEGRAM_TOKEN=your_telegram_bot_token
   TELEGRAM_CHAT_ID=your_telegram_chat_id
   ```

2. **Dependencies**
   The required dependencies are already installed via `uv`:
   - discord.py
   - yt-dlp
   - aiohttp

3. **FFmpeg**
   FFmpeg is required for audio playback. Install it:
   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg

   # macOS
   brew install ffmpeg

   # Windows
   # Download from https://ffmpeg.org/download.html
   ```

## Running the Bot

```bash
cd /home/focky/Projects/TeleService/discordbot
python3 main.py
```

## Music Commands

### Basic Commands
- `!play <url or query>` - Add song to queue or start playing
- `!queue [page]` - View the music queue
- `!shuffle` - Toggle shuffle mode
- `!skip` - Skip current song
- `!pause` - Pause playback
- `!resume` - Resume playback
- `!stop` - Stop and clear queue
- `!nowplaying` - Show current song info
- `!lyrics` - Show lyrics for current song
- `!disconnect` - Disconnect from voice channel

### Queue Management
- `!clear` - Clear the entire queue
- `!remove <position>` - Remove song by position
- `!move <from> <to>` - Move song between positions

See `MUSIC_COMMANDS.md` for detailed command documentation.

## Architecture

```
discordbot/
├── handlers/
│   ├── __init__.py
│   ├── music_utils.py      # yt-dlp, download, lyrics (lrclib.net)
│   ├── music_player.py      # MusicPlayer class (state management)
│   ├── music_ui.py          # Embeds, buttons, interactive UI
│   └── music_commands.py    # Command handlers
├── tmp/                      # Temporary audio files
├── config.py                 # Configuration
├── main.py                   # Bot entry point
└── MUSIC_COMMANDS.md         # Command documentation
```

## Configuration

### yt-dlp Options
The bot uses the following yt-dlp configuration:
```python
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}
```

### Lyrics Provider
Lyrics are fetched from lrclib.net (free API, no key required).

## Bot Permissions

The bot requires the following Discord permissions:
- Connect to voice channels
- Speak in voice channels
- Send messages
- Embed links
- Read message history

## Troubleshooting

### Bot won't join voice channel
- Check if the bot has permission to connect and speak
- Verify FFmpeg is installed and accessible

### Music won't play
- Check the URL format (YouTube, SoundCloud, etc.)
- Verify internet connection
- Check bot logs for errors

### Lyrics not found
- lrclib.net may not have lyrics for all songs
- Try a different song or search manually

### Bot disconnects unexpectedly
- Check Discord API status
- Verify bot token is correct
- Check bot logs for errors

## Notes

- Each Discord server has its own music queue
- Audio is streamed, not downloaded to your server
- The bot will automatically disconnect after 5 minutes of inactivity
- Voice state notifications are sent to Telegram for all users (not just the bot's voice channel)
