import logging

from odoo import fields, models

# Import emoji converters
from .mail_message import _convert_emoji_codes, _html_to_plain_text

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    llm_thread_id = fields.Many2one(
        "llm.thread",
        string="LLM Thread",
        ondelete="set null",
        help="Associated LLM thread for AI conversations",
        copy=False,
    )

    def _get_or_create_llm_thread(self):
        """Get or create LLM thread for this channel."""
        self.ensure_one()

        if (
                not self.livechat_channel_id
                or not self.livechat_channel_id.llm_assistant_id
        ):
            return None

        if self.llm_thread_id:
            return self.llm_thread_id

        assistant = self.livechat_channel_id.llm_assistant_id

        # Préparer les valeurs de création
        create_vals = {
            "name": f"Live Chat - {self.name}",
            "model": self._name,
            "res_id": self.id,
            "assistant_id": assistant.id,
            "provider_id": assistant.provider_id.id,
            "model_id": assistant.model_id.id,
        }

        # CRITIQUE : Copier le prompt_id de l'assistant
        if assistant.prompt_id:
            create_vals["prompt_id"] = assistant.prompt_id.id

        thread = self.env["llm.thread"].sudo().create(create_vals)
        self.sudo().write({"llm_thread_id": thread.id})
        return thread

    def _send_llm_greeting(self):
        """Send AI greeting message when chat starts."""
        self.ensure_one()

        if (
                not self.livechat_channel_id
                or not self.livechat_channel_id.llm_greeting_enabled
        ):
            return

        thread = self.sudo()._get_or_create_llm_thread()
        if not thread:
            return

        try:
            greeting_prompt = "Greet the visitor and ask how you can help them."
            llm_message = thread.sudo().message_post(
                body=greeting_prompt,
                llm_role="user",
                author_id=self.env.user.partner_id.id,
            )

            final_body = None
            for event in thread.sudo().generate_messages(llm_message):
                if event.get("type") == "message_update":
                    body = event.get("message", {}).get("body")
                    if body and body.strip():
                        final_body = body

            if final_body:
                # Convert HTML to plain text
                plain_text = _html_to_plain_text(final_body)

                # Convert emoji codes
                formatted_body = _convert_emoji_codes(plain_text)

                # Get bot user as author
                if self.livechat_channel_id.user_ids:
                    author_id = self.livechat_channel_id.user_ids[0].partner_id.id
                else:
                    author_id = self.env.ref("base.partner_root").id

                # Use context to prevent re-triggering
                self.sudo().with_context(llm_response=True).message_post(
                    body=formatted_body,
                    message_type="comment",
                    author_id=author_id,
                )
                _logger.info("LLM greeting posted to channel %s", self.id)

        except Exception as e:
            _logger.error(
                "Error sending LLM greeting to channel %s: %s",
                self.id,
                e,
            )
