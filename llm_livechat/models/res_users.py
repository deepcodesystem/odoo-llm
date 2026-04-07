import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _cron_keep_bot_operators_online(self):
        """Cron job to keep bot operators online.
        
        This ensures that users who are members of live chat channels with
        AI auto-reply enabled always appear as "online" to website visitors.
        
        Runs every 15 minutes to update their presence status.
        """
        # Find all live chat channels with AI auto-reply enabled
        channels = self.env["im_livechat.channel"].search([
            ("llm_auto_reply", "=", True),
            ("llm_assistant_id", "!=", False),
        ])
        
        if not channels:
            _logger.debug("No live chat channels with AI auto-reply found")
            return
        
        # Collect all unique users from these channels
        bot_users = self.env["res.users"]
        for channel in channels:
            bot_users |= channel.user_ids
        
        if not bot_users:
            _logger.warning(
                "Channels with AI auto-reply have no members: %s",
                channels.mapped("name")
            )
            return
        
        # Update their presence status to keep them "online"
        # Use bus.presence model which manages user online status in Odoo 18.0
        BusPresence = self.env["bus.presence"]
        
        for user in bot_users:
            # Check if presence record exists
            presence = BusPresence.search([("user_id", "=", user.id)], limit=1)
            
            if presence:
                # Update existing presence
                presence.write({
                    "last_presence": fields.Datetime.now(),
                    "last_poll": fields.Datetime.now(),
                })
            else:
                # Create new presence record
                BusPresence.create({
                    "user_id": user.id,
                    "last_presence": fields.Datetime.now(),
                    "last_poll": fields.Datetime.now(),
                })
        
        _logger.info(
            "Kept %d bot operators online for channels: %s",
            len(bot_users),
            ", ".join(channels.mapped("name"))
        )
