"""
views.py — Discord UI components for the Poll Bot.

Contains all Views (button layouts), Modals, and Select menus that power
the admin panel and the voting interface.
"""

import json
import discord
from discord import ui
from datetime import datetime, timezone, timedelta

import db
from config import (
    OPTION_EMOJIS,
    BUTTON_STYLES,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_DANGER,
    COLOR_ADMIN,
    COLOR_INFO,
    BAR_FULL,
    BAR_EMPTY,
    BAR_LENGTH,
    MAX_OPTIONS,
    MIN_POLL_DURATION_MINUTES,
    MAX_POLL_DURATION_MINUTES,
)


# ═══════════════════════════════════════════════
#  Helper — build a results embed
# ═══════════════════════════════════════════════

def build_results_embed(poll: dict, *, is_ended: bool = True) -> discord.Embed:
    """
    Build a beautifully styled embed showing poll results.
    Used both for live updates and final results.
    """
    vote_counts = db.get_vote_counts(poll["id"])
    total_votes = sum(vote_counts.values())
    options = json.loads(poll["options"])

    # Determine the winner(s)
    max_votes = max(vote_counts.values()) if vote_counts else 0
    winners = [opt for opt in options if vote_counts.get(opt, 0) == max_votes and max_votes > 0]

    if is_ended:
        color = COLOR_SUCCESS
        title = "📊  Poll Results — Ended"
        if winners:
            winner_text = ", ".join(f"**{w}**" for w in winners)
            title = f"🏆  Poll Ended — Winner: {winner_text}"
    else:
        color = COLOR_PRIMARY
        title = f"📊  {poll['question']}"

    embed = discord.Embed(title=title, color=color)

    if is_ended:
        embed.description = (
            f"**{poll['question']}**\n"
            f"_{poll['description']}_\n\n"
            f"Total votes: **{total_votes}**"
        )
    else:
        embed.description = (
            f"_{poll['description']}_\n\n"
            f"Total votes so far: **{total_votes}**"
        )

    # Build result bars for each option
    for i, option in enumerate(options):
        count = vote_counts.get(option, 0)
        percentage = (count / total_votes * 100) if total_votes > 0 else 0
        filled = int(BAR_LENGTH * percentage / 100)
        bar = BAR_FULL * filled + BAR_EMPTY * (BAR_LENGTH - filled)

        emoji = OPTION_EMOJIS[i] if i < len(OPTION_EMOJIS) else "▫️"
        is_winner = option in winners and is_ended and max_votes > 0
        crown = " 👑" if is_winner else ""

        embed.add_field(
            name=f"{emoji} {option}{crown}",
            value=f"`{bar}` **{count}** ({percentage:.1f}%)",
            inline=False,
        )

    if is_ended:
        embed.set_footer(text=f"Poll ID: {poll['id']}  •  Poll has ended")
        embed.timestamp = datetime.now(timezone.utc)
    else:
        # Show time remaining
        ends_at = datetime.fromisoformat(poll["ends_at"])
        now = datetime.now(timezone.utc)
        remaining = ends_at - now
        if remaining.total_seconds() > 0:
            mins, secs = divmod(int(remaining.total_seconds()), 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                time_str = f"{hours}h {mins}m remaining"
            else:
                time_str = f"{mins}m {secs}s remaining"
            embed.set_footer(text=f"⏱ {time_str}  •  Poll ID: {poll['id']}")
        else:
            embed.set_footer(text=f"⏱ Ending soon…  •  Poll ID: {poll['id']}")

    return embed


def build_active_poll_embed(poll: dict) -> discord.Embed:
    """Build the initial poll embed before any votes, with a live countdown."""
    options = json.loads(poll["options"])
    ends_at = datetime.fromisoformat(poll["ends_at"])
    now = datetime.now(timezone.utc)
    remaining = ends_at - now

    embed = discord.Embed(
        title=f"📊  {poll['question']}",
        description=(
            f"{poll['description']}\n\n"
            "**Vote by clicking a button below!**\n"
            "You can only vote once."
        ),
        color=COLOR_PRIMARY,
    )

    # List the options
    option_lines = []
    for i, option in enumerate(options):
        emoji = OPTION_EMOJIS[i] if i < len(OPTION_EMOJIS) else "▫️"
        option_lines.append(f"{emoji}  **{option}**")
    embed.add_field(name="Options", value="\n".join(option_lines), inline=False)

    # Time remaining
    if remaining.total_seconds() > 0:
        mins, secs = divmod(int(remaining.total_seconds()), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            time_str = f"{hours}h {mins}m"
        else:
            time_str = f"{mins}m {secs}s"
        embed.set_footer(text=f"⏱ Ends in {time_str}  •  Poll ID: {poll['id']}")
    else:
        embed.set_footer(text=f"⏱ Ending soon…  •  Poll ID: {poll['id']}")

    embed.timestamp = ends_at
    return embed


# ═══════════════════════════════════════════════
#  Admin Panel — Main View
# ═══════════════════════════════════════════════

class AdminPanelView(ui.View):
    """
    The main admin panel view with buttons for:
    - Creating a new poll
    - Viewing past polls
    - Ending a poll early
    """

    def __init__(self, *, allowed_role_ids: list[int] | None = None):
        super().__init__(timeout=300)  # 5 minute timeout
        self.allowed_role_ids = allowed_role_ids or []

    def _is_authorized(self, interaction: discord.Interaction) -> bool:
        """Check if the user has one of the allowed roles."""
        if not self.allowed_role_ids:
            return True  # No restrictions set
        user_role_ids = {role.id for role in interaction.user.roles}
        return bool(user_role_ids & set(self.allowed_role_ids))

    @ui.button(label="📝 Create Poll", style=discord.ButtonStyle.success, row=0)
    async def create_poll_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self._is_authorized(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to create polls.", ephemeral=True
            )
            return
        await interaction.response.send_modal(CreatePollModal())

    @ui.button(label="📜 View Past Polls", style=discord.ButtonStyle.primary, row=0)
    async def view_past_polls_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self._is_authorized(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to view polls.", ephemeral=True
            )
            return
        polls = db.get_past_polls(interaction.guild_id, limit=10)
        if not polls:
            await interaction.response.send_message("📭 No past polls found.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📜  Past Polls",
            description="Here are the most recent completed polls:",
            color=COLOR_INFO,
        )
        for p in polls:
            vote_counts = db.get_vote_counts(p["id"])
            total = sum(vote_counts.values())
            winner = p["winning_option"] or "No votes"
            embed.add_field(
                name=f"#{p['id']} — {p['question']}",
                value=(
                    f"🏆 Winner: **{winner}**\n"
                    f"🗳️ Total votes: **{total}**\n"
                    f"📅 Created: {p['created_at'][:10]}"
                ),
                inline=False,
            )
        embed.set_footer(text="Use /poll_history for more details")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="🛑 End Poll Early", style=discord.ButtonStyle.danger, row=0)
    async def end_poll_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self._is_authorized(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to end polls.", ephemeral=True
            )
            return

        # Show active polls for this guild
        active = [p for p in db.get_active_polls() if p["guild_id"] == interaction.guild_id]
        if not active:
            await interaction.response.send_message("✅ No active polls to end.", ephemeral=True)
            return

        # Create a select menu listing active polls
        view = EndPollSelectView(active_polls=active)
        await interaction.response.send_message(
            "Select a poll to end early:", view=view, ephemeral=True
        )

    @ui.button(label="⚙️ Set Allowed Roles", style=discord.ButtonStyle.secondary, row=1)
    async def set_roles_button(self, interaction: discord.Interaction, button: ui.Button):
        # Only server admins can change allowed roles
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only server administrators can change allowed roles.", ephemeral=True
            )
            return
        view = RoleSelectView()
        await interaction.response.send_message(
            "Select roles that can use the admin panel:", view=view, ephemeral=True
        )


# ═══════════════════════════════════════════════
#  Create Poll Modal
# ═══════════════════════════════════════════════

class CreatePollModal(ui.Modal, title="📊 Create a New Poll"):
    """Modal form for entering poll details."""

    question = ui.TextInput(
        label="Question",
        placeholder="What should we have for lunch?",
        style=discord.TextStyle.short,
        max_length=256,
        required=True,
    )
    description = ui.TextInput(
        label="Description",
        placeholder="Vote for your favorite option! (optional)",
        style=discord.TextStyle.paragraph,
        max_length=1024,
        required=False,
    )
    duration = ui.TextInput(
        label="Duration (minutes)",
        placeholder="5",
        style=discord.TextStyle.short,
        max_length=6,
        required=True,
        default="5",
    )
    options_input = ui.TextInput(
        label="Answer Options (comma-separated)",
        placeholder="Pizza, Sushi, Burgers, Salad",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Validate inputs and show the channel selection view."""
        # Validate duration
        try:
            dur = int(self.duration.value.strip())
            if dur < MIN_POLL_DURATION_MINUTES or dur > MAX_POLL_DURATION_MINUTES:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                f"❌ Duration must be a number between {MIN_POLL_DURATION_MINUTES} and "
                f"{MAX_POLL_DURATION_MINUTES} minutes.",
                ephemeral=True,
            )
            return

        # Parse options
        options = [opt.strip() for opt in self.options_input.value.split(",") if opt.strip()]
        if len(options) < 2:
            await interaction.response.send_message(
                "❌ You need at least 2 answer options.", ephemeral=True
            )
            return
        if len(options) > MAX_OPTIONS:
            await interaction.response.send_message(
                f"❌ Maximum {MAX_OPTIONS} options allowed.", ephemeral=True
            )
            return

        # Check for duplicate options
        if len(options) != len(set(options)):
            await interaction.response.send_message(
                "❌ Duplicate options are not allowed.", ephemeral=True
            )
            return

        # Store data and show channel picker
        poll_data = {
            "question": self.question.value.strip(),
            "description": (self.description.value or "").strip(),
            "duration": dur,
            "options": options,
        }

        view = ChannelSelectView(poll_data=poll_data)
        embed = discord.Embed(
            title="📍 Select a Channel",
            description=(
                f"**Question:** {poll_data['question']}\n"
                f"**Duration:** {poll_data['duration']} minute(s)\n"
                f"**Options:** {', '.join(poll_data['options'])}\n\n"
                "Choose the channel where the poll will be posted:"
            ),
            color=COLOR_ADMIN,
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ═══════════════════════════════════════════════
#  Channel Select for Poll Posting
# ═══════════════════════════════════════════════

class ChannelSelectView(ui.View):
    """Dropdown to select which text channel the poll will be posted in."""

    def __init__(self, *, poll_data: dict):
        super().__init__(timeout=120)
        self.poll_data = poll_data

    @ui.select(
        cls=ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Select a channel…",
        min_values=1,
        max_values=1,
    )
    async def channel_select(self, interaction: discord.Interaction, select: ui.ChannelSelect):
        selected = select.values[0]
        channel_id = selected.id

        # Try multiple methods to resolve the channel
        resolved_channel = None

        # Method 1: Bot client cache
        resolved_channel = interaction.client.get_channel(channel_id)

        # Method 2: Fetch via API
        if resolved_channel is None:
            try:
                resolved_channel = await interaction.client.fetch_channel(channel_id)
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ Bot doesn't have permission to access this channel.\n"
                    "Make sure the bot has **View Channel** permission.",
                    ephemeral=True,
                )
                return
            except discord.NotFound:
                await interaction.response.send_message(
                    "❌ Channel not found. It may have been deleted.",
                    ephemeral=True,
                )
                return
            except Exception as e:
                print(f"⚠️ Channel fetch error: {type(e).__name__}: {e}")
                await interaction.response.send_message(
                    f"❌ Failed to access channel: {type(e).__name__}",
                    ephemeral=True,
                )
                return

        # Create the poll in the database
        now = datetime.now(timezone.utc)
        ends_at = now + timedelta(minutes=self.poll_data["duration"])

        poll_id = db.create_poll(
            guild_id=interaction.guild_id,
            channel_id=resolved_channel.id,
            question=self.poll_data["question"],
            description=self.poll_data["description"],
            options_json=json.dumps(self.poll_data["options"]),
            duration_minutes=self.poll_data["duration"],
            created_at=now.isoformat(),
            ends_at=ends_at.isoformat(),
        )

        # Build the poll embed and view
        poll = db.get_poll(poll_id)
        embed = build_active_poll_embed(poll)
        vote_view = PollView(poll_id=poll_id, options=self.poll_data["options"])

        # Send the poll to the target channel
        try:
            msg = await resolved_channel.send(embed=embed, view=vote_view)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ Bot can't send messages in that channel.\n"
                f"Make sure the bot has **Send Messages** and **Embed Links** permissions.",
                ephemeral=True,
            )
            return

        db.set_poll_message_id(poll_id, msg.id)

        # Confirm to the admin
        await interaction.response.send_message(
            f"✅ Poll **#{poll_id}** has been posted in <#{resolved_channel.id}>!",
            ephemeral=True,
        )


# ═══════════════════════════════════════════════
#  Poll Voting View (buttons for each option)
# ═══════════════════════════════════════════════

class PollView(ui.View):
    """
    Dynamically generated buttons for poll voting.
    Each button corresponds to one answer option.
    This view is persistent (timeout=None) so it survives bot restarts.
    """

    def __init__(self, *, poll_id: int, options: list[str], disabled: bool = False):
        super().__init__(timeout=None)
        self.poll_id = poll_id

        for i, option in enumerate(options):
            emoji = OPTION_EMOJIS[i] if i < len(OPTION_EMOJIS) else None
            style = BUTTON_STYLES[i % len(BUTTON_STYLES)]
            button = PollOptionButton(
                poll_id=poll_id,
                option_label=option,
                emoji=emoji,
                style=style,
                row=i // 5,       # 5 buttons per row
                disabled=disabled,
            )
            self.add_item(button)


class PollOptionButton(ui.Button):
    """A single vote button for a poll option."""

    def __init__(
        self,
        *,
        poll_id: int,
        option_label: str,
        emoji: str | None,
        style: discord.ButtonStyle,
        row: int,
        disabled: bool = False,
    ):
        # custom_id must be unique and deterministic for persistent views
        super().__init__(
            label=option_label,
            emoji=emoji,
            style=style,
            row=row,
            disabled=disabled,
            custom_id=f"poll_{poll_id}_option_{option_label}",
        )
        self.poll_id = poll_id
        self.option_label = option_label

    async def callback(self, interaction: discord.Interaction):
        # Check if poll is still active
        poll = db.get_poll(self.poll_id)
        if poll is None or poll["ended"]:
            await interaction.response.send_message(
                "⏰ This poll has already ended!", ephemeral=True
            )
            return

        # Check time expiry
        ends_at = datetime.fromisoformat(poll["ends_at"])
        if datetime.now(timezone.utc) >= ends_at:
            await interaction.response.send_message(
                "⏰ This poll has already ended!", ephemeral=True
            )
            return

        # Attempt to record the vote
        success = db.record_vote(self.poll_id, interaction.user.id, self.option_label)

        if not success:
            await interaction.response.send_message(
                "🚫 You have already voted in this poll!", ephemeral=True
            )
            return

        # Vote recorded — update the embed with live counts
        total = db.get_total_votes(self.poll_id)
        await interaction.response.send_message(
            f"✅ Vote recorded for **{self.option_label}**! "
            f"(Total votes: {total})",
            ephemeral=True,
        )

        # Update the poll embed to show live results
        updated_poll = db.get_poll(self.poll_id)
        results_embed = build_results_embed(updated_poll, is_ended=False)
        await interaction.message.edit(embed=results_embed)


# ═══════════════════════════════════════════════
#  End Poll Early — Select Menu
# ═══════════════════════════════════════════════

class EndPollSelectView(ui.View):
    """Select menu listing active polls so an admin can pick one to end."""

    def __init__(self, *, active_polls: list[dict]):
        super().__init__(timeout=60)
        options = []
        for p in active_polls[:25]:  # Discord max 25 select options
            label = f"#{p['id']} — {p['question']}"
            if len(label) > 100:
                label = label[:97] + "…"
            options.append(
                discord.SelectOption(label=label, value=str(p["id"]))
            )

        self.select = ui.Select(
            placeholder="Choose a poll to end…",
            options=options,
            min_values=1,
            max_values=1,
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        poll_id = int(self.select.values[0])
        poll = db.get_poll(poll_id)

        if poll is None or poll["ended"]:
            await interaction.response.send_message(
                "This poll has already ended.", ephemeral=True
            )
            return

        # Confirm ending
        view = EndPollConfirmView(poll_id=poll_id)
        await interaction.response.send_message(
            f"⚠️ Are you sure you want to end poll **#{poll_id}** "
            f"(**{poll['question']}**) early?",
            view=view,
            ephemeral=True,
        )


class EndPollConfirmView(ui.View):
    """Confirmation buttons for ending a poll early."""

    def __init__(self, *, poll_id: int):
        super().__init__(timeout=30)
        self.poll_id = poll_id

    @ui.button(label="✅ Yes, End It", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        from bot import end_poll_and_update  # Import here to avoid circular imports
        await end_poll_and_update(interaction.client, self.poll_id)
        await interaction.response.send_message(
            f"🛑 Poll **#{self.poll_id}** has been ended early.", ephemeral=True
        )

    @ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Cancelled.", ephemeral=True)


# ═══════════════════════════════════════════════
#  Role Select View
# ═══════════════════════════════════════════════

class RoleSelectView(ui.View):
    """Select roles that are allowed to use the admin panel."""

    def __init__(self):
        super().__init__(timeout=60)

    @ui.select(
        cls=ui.RoleSelect,
        placeholder="Select allowed roles…",
        min_values=1,
        max_values=10,
    )
    async def role_select(self, interaction: discord.Interaction, select: ui.RoleSelect):
        role_ids = [role.id for role in select.values]
        role_names = [role.name for role in select.values]

        # Store in the bot instance for this guild
        if not hasattr(interaction.client, "admin_role_ids"):
            interaction.client.admin_role_ids = {}
        interaction.client.admin_role_ids[interaction.guild_id] = role_ids

        role_list = ", ".join(f"**@{name}**" for name in role_names)
        await interaction.response.send_message(
            f"✅ Admin panel access set to: {role_list}",
            ephemeral=True,
        )
