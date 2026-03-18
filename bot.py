"""
bot.py — Main entry point for the Discord Poll Bot.

Provides:
  - /admin_panel_poll  →  Opens the interactive admin panel
  - /poll_history      →  Shows past polls and their results
  - Background task    →  Monitors active polls for expiry and updates embeds
"""

import os
import json
import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone
from dotenv import load_dotenv

import db
from config import (
    COLOR_ADMIN,
    COLOR_INFO,
    COLOR_SUCCESS,
    POLL_CHECK_INTERVAL,
    COUNTDOWN_UPDATE_INTERVAL,
)
from views import (
    AdminPanelView,
    PollView,
    build_results_embed,
    build_active_poll_embed,
)

# ──────────────────────────────────────────────
#  Load environment variables
# ──────────────────────────────────────────────
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN not found. Create a .env file with BOT_TOKEN=your-token-here"
    )

# ──────────────────────────────────────────────
#  Bot setup
# ──────────────────────────────────────────────
intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)

# In-memory storage for admin role IDs per guild
# { guild_id: [role_id, ...] }
bot.admin_role_ids = {}


# ═══════════════════════════════════════════════
#  Events
# ═══════════════════════════════════════════════

@bot.event
async def on_ready():
    """Called when the bot is ready. Initializes DB, syncs commands, and starts tasks."""
    db.init_db()
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"📡 Connected to {len(bot.guilds)} guild(s)")

    # Re-register persistent views for active polls
    active_polls = db.get_active_polls()
    for poll in active_polls:
        options = json.loads(poll["options"])
        view = PollView(poll_id=poll["id"], options=options)
        bot.add_view(view)
    print(f"🔄 Restored {len(active_polls)} active poll view(s)")

    # Sync slash commands globally
    try:
        synced = await bot.tree.sync()
        print(f"⚡ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

    # Start background tasks
    if not poll_expiry_checker.is_running():
        poll_expiry_checker.start()
    if not poll_countdown_updater.is_running():
        poll_countdown_updater.start()


# ═══════════════════════════════════════════════
#  Slash Commands
# ═══════════════════════════════════════════════

@bot.tree.command(name="admin_panel_poll", description="📊 Open the poll administration panel")
async def admin_panel_poll(interaction: discord.Interaction):
    """Open the admin panel for managing polls."""
    # Check if user has the required role or is an administrator
    allowed_roles = bot.admin_role_ids.get(interaction.guild_id, [])

    if allowed_roles:
        user_role_ids = {role.id for role in interaction.user.roles}
        has_role = bool(user_role_ids & set(allowed_roles))
        is_admin = interaction.user.guild_permissions.administrator
        if not has_role and not is_admin:
            await interaction.response.send_message(
                "❌ You don't have permission to use the admin panel.\n"
                "Required roles have been set by a server administrator.",
                ephemeral=True,
            )
            return

    # Build the admin panel embed
    embed = discord.Embed(
        title="⚙️  Poll Admin Panel",
        description=(
            "Welcome to the Poll Admin Panel!\n"
            "Use the buttons below to manage polls.\n\n"
            "**Available Actions:**\n"
            "📝 **Create Poll** — Start a new poll with custom options\n"
            "📜 **View Past Polls** — Browse completed polls and results\n"
            "🛑 **End Poll Early** — Terminate an active poll immediately\n"
            "⚙️ **Set Allowed Roles** — Configure who can use this panel"
        ),
        color=COLOR_ADMIN,
    )

    # Show current active polls count
    active_count = len([
        p for p in db.get_active_polls() if p["guild_id"] == interaction.guild_id
    ])
    past_count = len(db.get_past_polls(interaction.guild_id, limit=100))

    embed.add_field(name="📊 Active Polls", value=f"**{active_count}**", inline=True)
    embed.add_field(name="📜 Past Polls", value=f"**{past_count}**", inline=True)

    if allowed_roles:
        role_mentions = []
        for rid in allowed_roles:
            role = interaction.guild.get_role(rid)
            role_mentions.append(role.mention if role else f"Unknown ({rid})")
        embed.add_field(
            name="🔒 Allowed Roles",
            value=", ".join(role_mentions),
            inline=False,
        )
    else:
        embed.add_field(
            name="🔓 Access",
            value="All members can use this panel (no role restriction set)",
            inline=False,
        )

    embed.set_footer(text="Poll Bot Admin Panel  •  Use buttons below")
    embed.timestamp = datetime.now(timezone.utc)

    view = AdminPanelView(allowed_role_ids=allowed_roles)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="poll_history", description="📜 View past poll results")
async def poll_history(interaction: discord.Interaction):
    """Display an overview of past polls in this server."""
    polls = db.get_all_guild_polls(interaction.guild_id, limit=15)

    if not polls:
        await interaction.response.send_message(
            "📭 No polls have been created in this server yet.", ephemeral=True
        )
        return

    embed = discord.Embed(
        title="📜  Poll History",
        description=f"Showing the last **{len(polls)}** poll(s) for this server:",
        color=COLOR_INFO,
    )

    for p in polls:
        vote_counts = db.get_vote_counts(p["id"])
        total = sum(vote_counts.values())
        status = "✅ Ended" if p["ended"] else "🟢 Active"
        winner = p["winning_option"] or "—"
        options = json.loads(p["options"])

        # Build a mini result summary
        result_lines = []
        for opt in options:
            count = vote_counts.get(opt, 0)
            result_lines.append(f"`{opt}`: {count}")
        results_str = "  |  ".join(result_lines)

        embed.add_field(
            name=f"{status}  #{p['id']} — {p['question']}",
            value=(
                f"🏆 Winner: **{winner}**  •  🗳️ Votes: **{total}**\n"
                f"{results_str}\n"
                f"📅 {p['created_at'][:16].replace('T', ' ')} UTC"
            ),
            inline=False,
        )

    embed.set_footer(text="Poll Bot  •  /admin_panel_poll to manage polls")
    embed.timestamp = datetime.now(timezone.utc)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ═══════════════════════════════════════════════
#  Poll Lifecycle — End and Update
# ═══════════════════════════════════════════════

async def end_poll_and_update(client: discord.Client, poll_id: int) -> None:
    """
    End a poll: determine winner, update DB, edit the message embed,
    and disable all voting buttons.
    """
    poll = db.get_poll(poll_id)
    if poll is None or poll["ended"]:
        return

    # Determine the winner
    vote_counts = db.get_vote_counts(poll_id)
    if vote_counts:
        max_votes = max(vote_counts.values())
        winners = [opt for opt, cnt in vote_counts.items() if cnt == max_votes]
        winning_text = ", ".join(winners)
    else:
        winning_text = "No votes cast"

    # Update the database
    db.end_poll(poll_id, winning_option=winning_text)

    # Try to edit the original message
    try:
        channel = client.get_channel(poll["channel_id"])
        if channel is None:
            channel = await client.fetch_channel(poll["channel_id"])

        message = await channel.fetch_message(poll["message_id"])

        # Build the final results embed
        updated_poll = db.get_poll(poll_id)
        results_embed = build_results_embed(updated_poll, is_ended=True)

        # Create a disabled view
        options = json.loads(poll["options"])
        disabled_view = PollView(poll_id=poll_id, options=options, disabled=True)

        await message.edit(embed=results_embed, view=disabled_view)
    except discord.NotFound:
        print(f"⚠️ Poll #{poll_id}: message not found, skipping embed update.")
    except discord.Forbidden:
        print(f"⚠️ Poll #{poll_id}: missing permissions to edit message.")
    except Exception as e:
        print(f"⚠️ Poll #{poll_id}: error updating message: {e}")


# ═══════════════════════════════════════════════
#  Background Tasks
# ═══════════════════════════════════════════════

@tasks.loop(seconds=POLL_CHECK_INTERVAL)
async def poll_expiry_checker():
    """Periodically check for polls that have passed their end time."""
    now = datetime.now(timezone.utc)
    active_polls = db.get_active_polls()

    for poll in active_polls:
        ends_at = datetime.fromisoformat(poll["ends_at"])
        if now >= ends_at:
            print(f"⏰ Poll #{poll['id']} has expired. Ending…")
            await end_poll_and_update(bot, poll["id"])


@poll_expiry_checker.before_loop
async def before_poll_checker():
    """Wait until the bot is ready before starting the expiry checker."""
    await bot.wait_until_ready()


@tasks.loop(seconds=COUNTDOWN_UPDATE_INTERVAL)
async def poll_countdown_updater():
    """Periodically update active poll embeds with refreshed countdown timers."""
    active_polls = db.get_active_polls()

    for poll in active_polls:
        try:
            channel = bot.get_channel(poll["channel_id"])
            if channel is None:
                continue

            message = await channel.fetch_message(poll["message_id"])
            # Update embed with fresh time remaining
            updated_poll = db.get_poll(poll["id"])
            total_votes = db.get_total_votes(poll["id"])

            if total_votes > 0:
                # Show live results with countdown
                embed = build_results_embed(updated_poll, is_ended=False)
            else:
                # Show the initial embed with updated countdown
                embed = build_active_poll_embed(updated_poll)

            await message.edit(embed=embed)
        except (discord.NotFound, discord.Forbidden):
            pass
        except Exception as e:
            print(f"⚠️ Countdown update error for poll #{poll['id']}: {e}")

        # Small delay between updates to avoid rate limits
        await asyncio.sleep(1)


@poll_countdown_updater.before_loop
async def before_countdown_updater():
    """Wait until the bot is ready before starting the countdown updater."""
    await bot.wait_until_ready()


# ═══════════════════════════════════════════════
#  Run the bot
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    print("🚀 Starting Poll Bot…")
    bot.run(BOT_TOKEN)
