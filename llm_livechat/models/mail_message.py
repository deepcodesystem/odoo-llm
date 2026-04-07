import html
import logging
import re

from odoo import api, models

_logger = logging.getLogger(__name__)


# Mapping of Slack/Discord-style emoji codes to Unicode emojis
EMOJI_MAP = {
    ":rocket:": "🚀",
    ":wrench:": "🔧",
    ":high_voltage:": "⚡",
    ":bar_chart:": "📊",
    ":books:": "📚",
    ":link:": "🔗",
    ":checkmarkbutton:": "✅",
    ":checkmark:": "✅",
    ":check:": "✅",
    ":cross_mark:": "❌",
    ":x:": "❌",
    ":mobile_phone:": "📱",
    ":lockedwithkey:": "🔐",
    ":locked:": "🔒",
    ":shield:": "🛡️",
    ":robot:": "🤖",
    ":memo:": "📝",
    ":e-mail:": "📧",
    ":email:": "📧",
    ":telephone_receiver:": "📞",
    ":phone:": "📞",
    ":counterclockwisearrowsbutton:": "🔄",
    ":clipboard:": "📋",
    ":test_tube:": "🧪",
    ":light_bulb:": "💡",
    ":bulb:": "💡",
    ":clamp:": "🗜️",
    ":floppy_disk:": "💾",
    ":office_building:": "🏢",
    ":bullseye:": "🎯",
    ":crescent_moon:": "🌙",
    ":warning:": "⚠️",
    ":fire:": "🔥",
    ":star:": "⭐",
    ":thumbs_up:": "👍",
    ":thumbsup:": "👍",
    ":thumbs_down:": "👎",
    ":thumbsdown:": "👎",
    ":wave:": "👋",
    ":smile:": "😊",
    ":tada:": "🎉",
    ":raised_hands:": "🙌",
    ":eyes:": "👀",
    ":brain:": "🧠",
    ":heart:": "❤️",
    ":package:": "📦",
    ":gear:": "⚙️",
    ":hammer:": "🔨",
    ":key:": "🔑",
    ":chart_increasing:": "📈",
    ":dollar:": "💰",
    ":stopwatch:": "⏱️",
    ":alarm_clock:": "⏰",
    ":calendar:": "📅",
    ":mag:": "🔍",
    ":mag_right:": "🔎",
}

# Single compiled pattern for all emoji codes (longest first to avoid partial matches)
_EMOJI_PATTERN = re.compile(
    "|".join(re.escape(code) for code in sorted(EMOJI_MAP, key=len, reverse=True))
)


def _convert_emoji_codes(text):
    """Convert :emoji_code: to Unicode emojis using a single regex pass."""
    if not text:
        return text
    return _EMOJI_PATTERN.sub(lambda m: EMOJI_MAP[m.group(0)], text)


def _safe_link_replacement(match):
    """Build a safe anchor tag, allowing only http/https URLs."""
    link_text = match.group(1)  # already HTML-escaped by caller
    url = match.group(2)
    if re.match(r"^https?://", url, re.IGNORECASE):
        return f'<a href="{url}" target="_blank">{link_text}</a>'
    # Discard unsafe URL schemes; show the link text only
    return link_text


def _convert_markdown_to_html(text):
    """Convert basic Markdown to HTML for Odoo live chat.

    Handles:
    - Bold: **text** or __text__ → <strong>text</strong>
    - Italic: *text* → <em>text</em>
    - Links: [text](url) → <a href="url">text</a> (http/https only)
    - Inline code: `code` → <code>code</code>
    - Line breaks: preserve \\n as <br>
    """
    if not text:
        return text

    # Escape HTML entities first to prevent injection via LLM-generated content
    text = html.escape(text)

    # Bold: **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)

    # Italic: *text* — negative lookaround avoids matching bold markers
    text = re.sub(
        r"(?<!\*)\*(?!\*)([^\*]+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text
    )
    # Italic: _text_ — only at word/line boundaries to avoid false positives
    text = re.sub(
        r"(?:^|(?<=\s))_([^_]+?)_(?:(?=\s)|$)",
        r"<em>\1</em>",
        text,
        flags=re.MULTILINE,
    )

    # Links: [text](url) — only safe http/https URLs are kept
    text = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", _safe_link_replacement, text)

    # Inline code: `code`
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # Line breaks: convert \n to <br>
    text = text.replace("\n", "<br>")

    return text


def _format_llm_response(text):
    """Format LLM response for display in Odoo live chat.

    Combines emoji code conversion and basic Markdown-to-HTML conversion.
    """
    if not text:
        return text
    text = _convert_emoji_codes(text)
    text = _convert_markdown_to_html(text)
    return text


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        """Intercept live chat messages to trigger LLM assistant."""
        messages = super().create(vals_list)

        for message in messages:
            if (
                message.model == "discuss.channel"
                and message.message_type == "comment"
                and not self.env.context.get("llm_response")
            ):
                self._maybe_trigger_llm_response(message)

        return messages

    def _maybe_trigger_llm_response(self, message):
        """Check if we should trigger LLM response for this message."""
        try:
            channel = self.env["discuss.channel"].browse(message.res_id)

            if not channel.livechat_channel_id:
                return

            livechat_config = channel.livechat_channel_id
            if (
                not livechat_config.llm_auto_reply
                or not livechat_config.llm_assistant_id
            ):
                return

            # Don't respond to the bot's own messages (OdooBot / admin)
            bot_partner = self.env.ref("base.partner_root", raise_if_not_found=False)
            if bot_partner and message.author_id == bot_partner:
                return

            # Don't respond to operator messages – only to visitors (partners without users)
            if message.author_id and message.author_id.user_ids:
                return

            self._send_llm_response(channel.id, message.id)

        except Exception as e:
            _logger.error("Error in _maybe_trigger_llm_response: %s", e)

    @api.model
    def _send_llm_response(self, channel_id, user_message_id):
        """Generate and send LLM response to live chat channel."""
        try:
            channel = self.env["discuss.channel"].browse(channel_id)
            user_message = self.env["mail.message"].browse(user_message_id)

            if not channel.exists() or not user_message.exists():
                return

            thread = channel._get_or_create_llm_thread()
            if not thread:
                return

            llm_message = thread.message_post(
                body=user_message.body,
                llm_role="user",
                author_id=user_message.author_id.id,
            )

            final_body = None
            for event in thread.generate_messages(llm_message):
                if event.get("type") == "message_update":
                    body = event.get("message", {}).get("body")
                    if body and body.strip():
                        final_body = body

            if final_body:
                formatted_body = _format_llm_response(final_body)
                channel.with_context(llm_response=True).message_post(
                    body=formatted_body,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )

        except Exception as e:
            _logger.error(
                "Error generating LLM response for channel %s: %s",
                channel_id,
                e,
            )
