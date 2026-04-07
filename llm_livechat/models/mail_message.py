import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


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

            # Don't respond to the bot's own messages (OdooBot / admin)
            bot_partner = self.env.ref("base.partner_root", raise_if_not_found=False)
            if bot_partner and message.author_id == bot_partner:
                return

            # Don't respond to operator messages – only to visitors (partners without users)
            if message.author_id and message.author_id.user_ids:
                return

            # Additional safety: rate-limit to avoid rapid-fire loops
            last_messages = self.env["mail.message"].search(
                [
                    ("model", "=", "discuss.channel"),
                    ("res_id", "=", channel.id),
                    (
                        "create_date",
                        ">",
                        fields.Datetime.now() - timedelta(seconds=5),
                    ),
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
                    "Rate limit: Too many visitor messages in channel %s, skipping LLM response",
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
                event_type = event.get("type")

                if event_type in ("message_create", "message_update"):
                    body = event.get("message", {}).get("body")
                    if body and body.strip():
                        final_body = body

                elif event_type == "error":
                    _logger.error(
                        "Error during LLM generation for channel %s: %s",
                        channel_id,
                        event.get("error"),
                    )
                    break

            if final_body:
                channel.with_context(llm_response=True).message_post(
                    body=final_body,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
                _logger.info("LLM response posted to channel %s", channel_id)
            else:
                _logger.warning(
                    "No valid response generated for channel %s", channel_id
                )

        except Exception as e:
            _logger.exception(
                "Error generating LLM response for channel %s: %s",
                channel_id,
                e,
            )
