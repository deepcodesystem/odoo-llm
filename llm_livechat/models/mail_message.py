import logging
import re

from markupsafe import Markup

from odoo import api, models

_logger = logging.getLogger(__name__)

# Mapping of Slack/Discord emoji shortcodes to Unicode
EMOJI_MAP = {
    # Common symbols
    ":rocket:": "🚀",
    ":wrench:": "🔧",
    ":high_voltage:": "⚡",
    ":zap:": "⚡",
    ":bar_chart:": "📊",
    ":books:": "📚",
    ":book:": "📖",
    ":link:": "🔗",
    ":checkmarkbutton:": "✅",
    ":checkmark:": "✅",
    ":check:": "✅",
    ":white_check_mark:": "✅",
    ":cross_mark:": "❌",
    ":x:": "❌",
    ":mobile_phone:": "📱",
    ":iphone:": "📱",
    ":lockedwithkey:": "🔐",
    ":locked:": "🔒",
    ":lock:": "🔒",
    ":shield:": "🛡️",
    ":robot:": "🤖",
    ":memo:": "📝",
    ":pencil:": "📝",
    ":e-mail:": "📧",
    ":email:": "📧",
    ":envelope:": "📧",
    ":telephone_receiver:": "📞",
    ":phone:": "📞",
    ":counterclockwisearrowsbutton:": "🔄",
    ":arrows_counterclockwise:": "🔄",
    ":clipboard:": "📋",
    ":test_tube:": "🧪",
    ":light_bulb:": "💡",
    ":bulb:": "💡",
    ":clamp:": "🗜️",
    ":floppy_disk:": "💾",
    ":office_building:": "🏢",
    ":office:": "🏢",
    ":bullseye:": "🎯",
    ":dart:": "🎯",
    ":crescent_moon:": "🌙",
    ":moon:": "🌙",
    ":warning:": "⚠️",
    ":fire:": "🔥",
    ":star:": "⭐",
    ":thumbs_up:": "👍",
    ":thumbsup:": "👍",
    ":+1:": "👍",
    ":thumbs_down:": "👎",
    ":thumbsdown:": "👎",
    ":-1:": "👎",
    ":wave:": "👋",
    ":waving_hand:": "👋",
    ":hand:": "👋",
    ":smile:": "😊",
    ":smiley:": "😊",
    ":grinning:": "😀",
    ":tada:": "🎉",
    ":party:": "🎉",
    ":raised_hands:": "🙌",
    ":eyes:": "👀",
    ":brain:": "🧠",
    ":heart:": "❤️",
    ":package:": "📦",
    ":gear:": "⚙️",
    ":hammer:": "🔨",
    ":key:": "🔑",
    ":chart_increasing:": "📈",
    ":chart_with_upwards_trend:": "📈",
    ":dollar:": "💰",
    ":moneybag:": "💰",
    ":stopwatch:": "⏱️",
    ":alarm_clock:": "⏰",
    ":calendar:": "📅",
    ":mag:": "🔍",
    ":mag_right:": "🔎",
    ":telescope:": "🔭",
    ":sparkles:": "✨",
    ":bell:": "🔔",
    ":loudspeaker:": "📢",
}


def _convert_emoji_codes(text):
    """Convert :emoji_code: shortcodes to Unicode emojis using a single regex pass."""
    if not text:
        return text
    pattern = re.compile("|".join(re.escape(code) for code in EMOJI_MAP))
    return pattern.sub(lambda m: EMOJI_MAP[m.group(0)], text)


def _has_html_tags(text):
    """Return True if text contains HTML tags."""
    if not text:
        return False
    return bool(re.search(r"<[a-z][\s\S]*?>", text, re.IGNORECASE))


def _convert_markdown_to_html(text):
    """Convert basic Markdown to HTML.

    Only applied when the text does not already contain HTML tags.
    Handles bold, italic, links, inline code, and paragraph breaks.
    """
    if not text:
        return text

    if _has_html_tags(text):
        return text

    # Bold: **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)

    # Italic: *text* or _text_ (word-boundary safe)
    text = re.sub(r"\*([^\*\n]+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"\b_([^_\n]+?)_\b", r"<em>\1</em>", text)

    # Links: [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^\)]+)\)",
        r'<a href="\2" target="_blank">\1</a>',
        text,
    )

    # Inline code: `code`
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # Paragraph breaks: double newline → </p><p>; single newline → <br>
    paragraphs = text.split("\n\n")
    if len(paragraphs) > 1:
        text = "</p><p>".join(paragraphs)
        text = f"<p>{text}</p>"
    else:
        text = text.replace("\n", "<br>")

    return text


def _format_llm_response(text):
    """Format an LLM response body for display in Odoo live chat.

    Strategy:
    1. Convert emoji shortcodes to Unicode (always).
    2. If the text already contains HTML tags, preserve the structure.
    3. Otherwise convert Markdown syntax to HTML.
    4. Return as ``Markup`` so Odoo does not re-escape the HTML.

    Security note: ``text`` is sourced from a ``mail.message`` body that has
    already been written through Odoo's Html field (which runs ``html_sanitize``
    on write). Wrapping in ``Markup`` here is therefore safe — it only prevents
    a second round of escaping, not the first sanitization pass.
    """
    if not text:
        return text

    # Step 1: convert emoji shortcodes (:wave: → 👋)
    text = _convert_emoji_codes(text)

    # Step 2: convert Markdown only when there is no HTML yet
    if not _has_html_tags(text):
        text = _convert_markdown_to_html(text)

    # Step 3: wrap in Markup to prevent Odoo from escaping HTML tags
    return Markup(text)


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        """Intercept live chat messages to trigger LLM assistant."""
        messages = super().create(vals_list)

        for message in messages:
            if message.model == "discuss.channel" and message.message_type == "comment":
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
                channel.message_post(
                    body=_format_llm_response(final_body),
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )

        except Exception as e:
            _logger.error(
                "Error generating LLM response for channel %s: %s",
                channel_id,
                e,
            )
