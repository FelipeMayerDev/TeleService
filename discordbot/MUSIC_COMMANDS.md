# Music Player Commands

## Basic Commands

### `!play <url or query>`
Adds a song to the queue or starts playing immediately if nothing is playing.
- URL: Direct link to YouTube/SoundCloud/etc
- Query: Search term (e.g., "never gonna give you up")

**Example:**
```
!play https://youtube.com/watch?v=dQw4w9WgXcQ
!play never gonna give you up
```

### `!queue [page]` / `!q [page]`
Shows the current music queue with pagination.

**Example:**
```
!queue
!queue 2
```

### `!shuffle`
Randomizes the current queue. Toggle on/off.

**Example:**
```
!shuffle
```

### `!skip`
Skips the current song and plays the next one in the queue.

**Example:**
```
!skip
```

### `!pause`
Pauses the current playback.

**Example:**
```
!pause
```

### `!resume`
Resumes paused playback.

**Example:**
```
!resume
```

### `!stop`
Stops playback and clears the queue.

**Example:**
```
!stop
```

### `!nowplaying` / `!np`
Shows information about the currently playing song.

**Example:**
```
!nowplaying
```

### `!lyrics` / `!l`
Shows lyrics for the currently playing song (from lrclib.net).

**Example:**
```
!lyrics
```

### `!disconnect` / `!dc`
Disconnects the bot from the voice channel and clears the queue.

**Example:**
```
!disconnect
```

## Queue Management

### `!clear`
Clears the entire queue.

**Example:**
```
!clear
```

### `!remove <position>`
Removes a song from the queue by its position.

**Example:**
```
!remove 1
!remove 5
```

### `!move <from> <to>`
Moves a song from one position to another in the queue.

**Example:**
```
!move 1 5
```

## Player UI Controls

When a song is playing, you'll see a player card with buttons:

- **⏸️ Pause** - Pause playback
- **▶️ Resume** - Resume playback
- **⏹️ Stop** - Stop and clear queue
- **⏭️ Skip** - Skip to next song
- **🔀 Shuffle** - Toggle shuffle mode
- **📜 Lyrics** - Show lyrics (DM)
- **📋 Queue** - View full queue

## Features

### Queue Management
- Each Discord server has its own queue
- Supports shuffle mode
- Pagination for long queues
- Move/remove songs by position

### Playback Controls
- Play/Pause/Resume/Stop
- Skip songs
- Shuffle queue
- Auto-play next song
- Auto-disconnect after 5 minutes of inactivity

### Lyrics Integration
- Automatic lyrics fetching from lrclib.net
- Cached for performance (1 hour TTL)
- Sent via DM if too long for channel

### Voice Integration
- Auto-joins your voice channel when you play
- Notifies Telegram when users join/leave voice channels
- Handles voice state updates

## Notes

- The bot must have permission to connect to voice channels
- Songs are streamed, not downloaded to your server
- The bot will automatically disconnect after 5 minutes of inactivity
- Lyrics are provided by lrclib.net (free, no API key needed)
