# LLM Live Chat Integration

Connect LLM Assistants to Odoo Live Chat for automatic, AI-powered responses to website visitors.

## Features

- Configure AI assistants per live chat channel
- Automatic response to visitor messages
- Configurable delay before auto-reply
- Optional AI-generated greeting when a chat session starts
- Thread-based conversation management with full history

## Configuration

1. Go to **Live Chat → Configuration → Channels**
2. Select (or create) a channel, e.g. *Support*
3. In the **AI Assistant** section:
   - **AI Assistant**: select your configured LLM assistant
   - **Auto Reply**: enable automatic responses
   - **Response Delay**: seconds to wait before replying (allows human operators to respond first)
   - **Send Greeting**: send an AI-generated greeting when a visitor opens the chat

## Message Formatting

The module intelligently handles both Markdown and HTML responses from the LLM.

### HTML Responses (LLM generates HTML)

If the LLM response already contains HTML tags (`<p>`, `<div>`, etc.), the module:

- Converts emoji shortcodes to Unicode (`:wave:` → 👋)
- Preserves the HTML structure as-is
- Uses `Markup()` to prevent Odoo from re-escaping the HTML

**Example:**

```
Input:  <p>Salut! :wave:</p>
Output: <p>Salut! 👋</p>
```

### Markdown Responses (LLM generates Markdown)

If the response is plain text or Markdown, the module:

- Converts emoji shortcodes to Unicode
- Converts Markdown to HTML (`**bold**`, `*italic*`, `[links](url)`)
- Wraps paragraphs in `<p>` tags for proper structure

**Example:**

```
Input:  Hello **world** :rocket:
Output: <p>Hello <strong>world</strong> 🚀</p>
```

### Assistant Configuration

For best results, configure your assistant to output either:

1. **Plain text with Markdown** (recommended for simplicity)
2. **Valid HTML** (for complex formatting)

Avoid mixing Markdown and HTML in the same response.

## Supported Emoji Shortcodes

Common shortcodes are converted to Unicode automatically:

| Shortcode | Emoji |
|-----------|-------|
| `:wave:` / `:waving_hand:` | 👋 |
| `:rocket:` | 🚀 |
| `:tada:` | 🎉 |
| `:bulb:` | 💡 |
| `:white_check_mark:` | ✅ |
| `:warning:` | ⚠️ |
| `:thumbs_up:` / `:+1:` | 👍 |
| `:sparkles:` | ✨ |

## Technical Notes

- `_format_llm_response()` in `models/mail_message.py` handles all formatting
- `Markup()` from `markupsafe` (bundled with Odoo) prevents HTML double-escaping
- The `EMOJI_MAP` dict in `models/mail_message.py` can be extended with additional shortcodes
