import re
import logging
from datetime import timedelta
from html import unescape

from odoo import api, fields, models

try:
    import emoji
    HAS_EMOJI = True
except ImportError:
    HAS_EMOJI = False

_logger = logging.getLogger(__name__)


# Simple emoji code to Unicode mapping (fallback if emoji library not available)
EMOJI_MAP = {
    ":wave:": "👋",
    ":waving_hand:": "👋",
    ":wavinghand:": "👋",
    ":hand:": "👋",
    ":rocket:": "🚀",
    ":wrench:": "🔧",
    ":hammer:": "🔨",
    ":gear:": "⚙️",
    ":bulb:": "💡",
    ":light_bulb:": "💡",
    ":lightbulb:": "💡",
    ":fire:": "🔥",
    ":zap:": "⚡",
    ":high_voltage:": "⚡",
    ":star:": "⭐",
    ":sparkles:": "✨",
    ":tada:": "🎉",
    ":party:": "🎉",
    ":party_popper:": "🎉",
    ":partypopper:": "🎉",
    ":checkmark:": "✅",
    ":white_check_mark:": "✅",
    ":check:": "✅",
    ":checkmarkbutton:": "✅",
    ":x:": "❌",
    ":cross_mark:": "❌",
    ":warning:": "⚠️",
    ":bell:": "🔔",
    ":loudspeaker:": "📢",
    ":eyes:": "👀",
    ":brain:": "🧠",
    ":heart:": "❤️",
    ":red_heart:": "❤️",
    ":redheart:": "❤️",
    ":thumbsup:": "👍",
    ":thumbs_up:": "👍",
    ":+1:": "👍",
    ":thumbsdown:": "👎",
    ":thumbs_down:": "👎",
    ":-1:": "👎",
    ":raised_hands:": "🙌",
    ":raising_hands:": "🙌",
    ":clap:": "👏",
    ":clapping_hands:": "👏",
    ":smile:": "😊",
    ":smiley:": "😊",
    ":grinning:": "😀",
    ":grinning_face:": "😀",
    ":grinningface:": "😀",
    ":wink:": "😉",
    ":thinking:": "🤔",
    ":books:": "📚",
    ":book:": "📖",
    ":memo:": "📝",
    ":pencil:": "✏️",
    ":clipboard:": "📋",
    ":calendar:": "📅",
    ":package:": "📦",
    ":inbox_tray:": "📥",
    ":outbox_tray:": "📤",
    ":link:": "🔗",
    ":email:": "📧",
    ":envelope:": "✉️",
    ":phone:": "📞",
    ":telephone_receiver:": "📞",
    ":mobile_phone:": "📱",
    ":iphone:": "📱",
    ":bar_chart:": "📊",
    ":chart_increasing:": "📈",
    ":chart_with_upwards_trend:": "📈",
    ":mag:": "🔍",
    ":mag_right:": "🔎",
    ":key:": "🔑",
    ":lock:": "🔒",
    ":locked:": "🔒",
    ":unlock:": "🔓",
    ":shield:": "🛡️",
    ":robot:": "🤖",
    ":telescope:": "🔭",
    ":dollar:": "💰",
    ":moneybag:": "💵",
    ":stopwatch:": "⏱️",
    ":alarm_clock:": "⏰",
    ":hourglass:": "⏳",
    ":dart:": "🎯",
    ":bullseye:": "🎯",
    ":trophy:": "🏆",
    ":office:": "🏢",
    ":office_building:": "🏢",
    ":house:": "🏠",
    ":test_tube:": "🧪",
    ":microscope:": "🔬",
    ":flexed_biceps:": "💪",
    ":muscle:": "💪",
    ":handshake:": "🤝",
    ":money_bag:": "💰",
    ":smilingfacewithsmilingeyes:": "😊",
    ":smiling_face_with_smiling_eyes:": "😊",
    ":crossed_fingers:": "🤞",
}

def _html_to_plain_text(html_text):
    """Convert HTML to plain text for live chat display.
    
    Live chat widget doesn't render HTML, so we convert it to plain text
    while preserving basic formatting like paragraphs and line breaks.
    """
    if not html_text:
        return html_text
    
    # Replace paragraph tags with double newlines
    text = re.sub(r'</p>\s*<p>', '\n\n', html_text)
    text = re.sub(r'<p>', '', text)
    text = re.sub(r'</p>', '\n', text)
    
    # Replace <br> and <br/> with newlines
    text = re.sub(r'<br\s*/?>', '\n', text)
    
    # Replace list items with bullet points
    text = re.sub(r'<li>', '• ', text)
    text = re.sub(r'</li>', '\n', text)
    text = re.sub(r'</?ul>', '\n', text)
    text = re.sub(r'</?ol>', '\n', text)
    
    # Replace <strong> and <b> with **text**
    text = re.sub(r'<strong>(.*?)</strong>', r'**\1**', text)
    text = re.sub(r'<b>(.*?)</b>', r'**\1**', text)
    
    # Replace <em> and <i> with *text*
    text = re.sub(r'<em>(.*?)</em>', r'*\1*', text)
    text = re.sub(r'<i>(.*?)</i>', r'*\1*', text)
    
    # Remove any remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Unescape HTML entities (&nbsp;, &amp;, etc.)
    text = unescape(text)
    
    # Clean up multiple consecutive newlines (max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text

def _convert_emoji_codes(text):
    """Convert :emoji_code: to Unicode emojis, handling HTML corruption.
    
    The LLM may return HTML where underscores in emoji codes are converted
    to <em> tags. For example:
    :smiling_face_with_smiling_eyes: becomes :smiling_face</em>with<em>smiling_eyes:
    
    This function repairs and converts these codes.
    """
    if not text:
        return text
    
    def fix_and_convert_emoji(match):
        """Fix HTML-corrupted emoji code and convert it."""
        code = match.group(0)
        
        # Remove all <em> and </em> tags, replace with underscore
        cleaned = code.replace('<em>', '_').replace('</em>', '_')
        
        # Remove duplicate underscores
        cleaned = re.sub(r'_+', '_', cleaned)
        
        # Remove underscores at start/end
        cleaned = re.sub(r':_+', ':', cleaned)
        cleaned = re.sub(r'_+:', ':', cleaned)
        
        # Try emoji library
        if HAS_EMOJI:
            try:
                converted = emoji.emojize(cleaned, language='alias')
                if converted != cleaned:
                    return converted
            except Exception:
                pass
        
        # Fallback to manual map
        for emoji_code, emoji_char in EMOJI_MAP.items():
            if emoji_code == cleaned:
                return emoji_char
        
        return code
    
    # Match emoji codes including those with HTML corruption and hyphens
    text = re.sub(
        r':[a-z0-9_\-<>/em]+:',
        fix_and_convert_emoji,
        text,
        flags=re.IGNORECASE
    )
    
    return text

class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        """Intercept live chat messages to trigger LLM assistant."""
        messages = super().create(vals_list)

        for message in messages:
            if message.model == "discuss.channel" and message.message_type == "comment":
                # CRITICAL: Use postcommit to avoid blocking notifications
                channel_id = message.res_id
                message_id = message.id
                
                # Defer LLM processing until AFTER transaction commits
                self.env.cr.postcommit.add(
                    lambda cid=channel_id, mid=message_id: (
                        self.env["mail.message"]._send_llm_response_async(cid, mid)
                    )
                )

        return messages

    @api.model
    def _send_llm_response_async(self, channel_id, message_id):
        """Async wrapper that runs after commit with new cursor."""
        with self.pool.cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            try:
                env["mail.message"]._send_llm_response(channel_id, message_id)
                cr.commit()
            except Exception as e:
                _logger.exception("Failed async LLM response: %s", e)
                cr.rollback()

    def _maybe_trigger_llm_response(self, message):
        """Check if we should trigger LLM response for this message."""
        # CRITICAL: Skip if this message was posted by the LLM system itself
        if self.env.context.get("llm_response"):
            return

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

            # Don't respond to the bot's own messages
            bot_partner = self.env.ref("base.partner_root", raise_if_not_found=False)
            if bot_partner and message.author_id == bot_partner:
                return

            # Don't respond to operator messages – only to visitors
            if message.author_id and message.author_id.user_ids:
                return

            # Rate limiting protection
            last_messages = self.env["mail.message"].search(
                [
                    ("model", "=", "discuss.channel"),
                    ("res_id", "=", channel.id),
                    ("create_date", ">", fields.Datetime.now() - timedelta(seconds=5)),
                ],
                order="create_date DESC",
                limit=5,
            )

            visitor_count = sum(
                1
                for msg in last_messages
                if msg.author_id and not msg.author_id.user_ids
            )

            if visitor_count > 2:
                _logger.warning(
                    "Rate limit: Too many visitor messages in channel %s",
                    channel.id,
                )
                return

            self._send_llm_response(channel.id, message.id)

        except Exception as e:
            _logger.exception("Error in _maybe_trigger_llm_response: %s", e)

    @api.model
    def _send_llm_response(self, channel_id, user_message_id):
        """Generate and send LLM response to live chat channel."""
        try:
            # Use sudo for reading
            channel = self.env["discuss.channel"].sudo().browse(channel_id)
            user_message = self.env["mail.message"].sudo().browse(user_message_id)

            if not channel.exists() or not user_message.exists():
                return

            # Skip if context says this is already an LLM response
            if self.env.context.get("llm_response"):
                return

            # Check config
            if not channel.livechat_channel_id:
                return

            livechat_config = channel.livechat_channel_id
            if not livechat_config.llm_auto_reply or not livechat_config.llm_assistant_id:
                return

            # Don't respond to operator messages
            if user_message.author_id and user_message.author_id.user_ids:
                return

            thread = channel.sudo()._get_or_create_llm_thread()
            if not thread:
                return

            llm_message = thread.sudo().message_post(
                body=user_message.body,
                llm_role="user",
                author_id=user_message.author_id.id,
            )

            final_body = None
            for event in thread.sudo().generate_messages(llm_message):
                if event.get("type") == "message_update":
                    body = event.get("message", {}).get("body")
                    if body and body.strip():
                        final_body = body

            # Post the final response
            if final_body:
                # STEP 1: Convert HTML to plain text for live chat
                plain_text = _html_to_plain_text(final_body)
                
                # STEP 2: Convert emoji codes (handling HTML corruption)
                formatted_body = _convert_emoji_codes(plain_text)
                
                # Get the bot user as author
                if channel.livechat_channel_id.user_ids:
                    author_id = channel.livechat_channel_id.user_ids[0].partner_id.id
                else:
                    author_id = self.env.ref("base.partner_root").id
                
                # Post message
                posted_message = channel.sudo().with_context(llm_response=True).message_post(
                    body=formatted_body,
                    message_type="comment",
                    author_id=author_id,
                )
                
                _logger.info(
                    "LLM response posted to channel %s (message_id: %s)", 
                    channel_id, 
                    posted_message.id if posted_message else None
                )

        except Exception as e:
            _logger.error(
                "Error generating LLM response for channel %s: %s",
                channel_id,
                e,
            )
            import traceback
            _logger.error(traceback.format_exc())