# LLM Live Chat Integration

Connects LLM Assistants to Odoo's Live Chat, enabling automatic AI-powered responses to website visitors.

## Features

- **Automatic AI responses** to visitor messages in live chat channels
- **Per-channel configuration**: choose which assistant to use, set reply delay, enable/disable auto-reply
- **Optional greeting message** when a chat session starts
- **Automatic formatting** of LLM responses (emoji codes + Markdown → HTML)

## Configuration

1. Go to **Live Chat → Configuration → Channels**
2. Select (or create) a channel
3. Open the **AI Assistant** tab and configure:
   - **AI Assistant**: select your LLM assistant
   - **Automatic Reply**: enable/disable auto-responses
   - **Reply Delay**: seconds to wait before responding (default: 2)
   - **Enable Greeting**: send an AI greeting when the session opens

## Message Formatting

LLM responses are automatically formatted for better readability in Odoo live chat.

### Emoji Support

Slack/Discord-style emoji codes are converted to Unicode emojis:

```
:rocket:   → 🚀
:wrench:   → 🔧
:bulb:     → 💡
:checkmark: → ✅
:warning:  → ⚠️
```

Over 50 common emoji codes are supported. See `EMOJI_MAP` in `models/mail_message.py` to add more.

### Markdown Support

Basic Markdown is converted to HTML:

| Syntax | Result |
|--------|--------|
| `**bold**` | **bold** |
| `*italic*` | *italic* |
| `` `code` `` | `code` |
| `[text](url)` | clickable link |
| newlines | `<br>` |

### Assistant Configuration Tips

For best results, configure your LLM assistant prompt with:

```
- Use emoji codes like :rocket: :bulb: :checkmark: for visual appeal
- Format lists clearly with numbers or bullets
- Use **bold** for emphasis
- Keep responses concise and structured
- Use line breaks for better readability
```

### Custom Emoji Mapping

To add more emoji codes, edit the `EMOJI_MAP` dictionary in `models/mail_message.py`:

```python
EMOJI_MAP = {
    ':your_code:': '🎯',
    # ... add more
}
```
