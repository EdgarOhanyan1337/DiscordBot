# 📊 Discord Poll Bot

A feature-rich Discord poll bot with an interactive admin panel, button-based voting, live countdowns, and SQLite persistence.

---

## ✨ Features

- **Admin Panel** (`/admin_panel_poll`) — Create polls, view history, end polls early, set allowed roles
- **Interactive Voting** — Beautiful embeds with colored buttons for each answer option
- **Duplicate Prevention** — One vote per user per poll (enforced at the database level)
- **Live Countdown** — Embed footer auto-updates with time remaining every 30 seconds
- **Auto-Expiry** — Polls end automatically; embed is edited to show results with a winner crown 🏆
- **Early Termination** — Admins can end any poll at any time via a button
- **Poll History** (`/poll_history`) — Browse past polls with detailed results
- **Role-Based Access** — Server admins can restrict who uses the admin panel
- **Persistent Views** — Voting buttons survive bot restarts
- **Progress Bars** — Visual vote distribution bars in results

---

## 📁 Project Structure

```
DiscordBot-1/
├── bot.py              # Main entry point — slash commands, background tasks, poll lifecycle
├── views.py            # All UI components — modals, buttons, select menus, embed builders
├── db.py               # SQLite database layer — CRUD operations for polls and votes
├── config.py           # Colors, emojis, button styles, timing constants
├── .env                # Your bot token (create from .env.example)
├── .env.example        # Template for environment variables
├── requirements.txt    # Python dependencies
└── polls.db            # SQLite database (auto-created on first run)
```

---

## 🚀 Setup — Step by Step

### Step 1: Create a Discord Bot on the Developer Portal

1. Go to **[Discord Developer Portal](https://discord.com/developers/applications)**
2. Click **"New Application"** → give it a name (e.g. "Poll Bot") → click **Create**
3. In the left sidebar, go to **"Bot"**
4. Click **"Reset Token"** → copy the **Bot Token** and save it (you'll need it in Step 3)
5. Scroll down and enable these **Privileged Gateway Intents**:
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**
6. Click **Save Changes**

### Step 2: Invite the Bot to Your Server

1. In the Developer Portal, go to **"OAuth2"** → **"URL Generator"**
2. Under **Scopes**, check:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Under **Bot Permissions**, check:
   - ✅ `Send Messages`
   - ✅ `Embed Links`
   - ✅ `Read Message History`
   - ✅ `Use Application Commands`
   - ✅ `Manage Messages` (optional — for editing embeds)
4. Copy the generated **URL** at the bottom
5. Open the URL in your browser → select your server → click **Authorize**

### Step 3: Install Python Dependencies

Make sure you have **Python 3.10+** installed, then open a terminal in the project folder:

```bash
pip install -r requirements.txt
```

This installs:
- `discord.py` — the Discord API wrapper
- `python-dotenv` — loads environment variables from `.env`

### Step 4: Configure the Bot Token

1. Copy the example env file:
   ```bash
   copy .env.example .env
   ```
2. Open `.env` in a text editor and replace the placeholder with your actual bot token:
   ```
   BOT_TOKEN=your-actual-bot-token-here
   ```
   > ⚠️ **Never share your bot token or commit it to Git!**

### Step 5: Run the Bot

```bash
python bot.py
```

You should see output like:
```
🚀 Starting Poll Bot…
✅ Logged in as PollBot#1234 (ID: 123456789)
📡 Connected to 1 guild(s)
🔄 Restored 0 active poll view(s)
⚡ Synced 2 slash command(s)
```

> 💡 **Tip:** The first time you run the bot, slash commands may take up to 1 hour to appear globally. To speed this up during development, you can sync commands to a specific guild (see the FAQ below).

---

## 🎮 How to Use

### Creating a Poll

1. Type `/admin_panel_poll` in any channel
2. The admin panel appears with 4 buttons:
   - 📝 **Create Poll** — opens a form to fill out
   - 📜 **View Past Polls** — shows recently completed polls
   - 🛑 **End Poll Early** — terminates an active poll
   - ⚙️ **Set Allowed Roles** — restricts who can use the admin panel
3. Click **📝 Create Poll** and fill in:
   - **Question** — e.g. "What should we eat for lunch?"
   - **Description** — optional extra context
   - **Duration** — how many minutes the poll stays open (1–10080)
   - **Answer Options** — comma-separated, e.g. `Pizza, Sushi, Burgers, Salad`
4. Click **Submit** → choose the target channel → poll is posted!

### Voting

- Users click the colored buttons on the poll embed to vote
- Each user can only vote **once** per poll
- Live vote counts and progress bars update after each vote

### Poll Ends

When the timer runs out (or an admin ends it early):
- The embed updates to show **final results** with progress bars
- The **winner** gets a 👑 crown
- All buttons become **disabled** (greyed out)

### Viewing Poll History

- Type `/poll_history` to see a summary of all past and active polls
- Shows winner, total votes, and per-option breakdown

---

## 🔒 Setting Allowed Roles

By default, **any member** can open the admin panel. To restrict it:

1. Run `/admin_panel_poll`
2. Click **⚙️ Set Allowed Roles**
3. Select one or more roles from the dropdown
4. Only users with those roles (or server administrators) can use the panel

> **Note:** Role settings are stored in memory and will reset when the bot restarts. For persistent role settings, you can extend the database.

---

## ❓ FAQ

**Q: Slash commands don't appear after running the bot?**  
A: Global slash commands can take up to 1 hour to propagate. Wait and try again. If you want instant commands for testing, you can modify `bot.py` to sync to a specific guild:
```python
# In the on_ready event, replace:
synced = await bot.tree.sync()
# With:
guild = discord.Object(id=YOUR_GUILD_ID)
synced = await bot.tree.sync(guild=guild)
```

**Q: The bot says "Missing Permissions"?**  
A: Make sure the bot has `Send Messages`, `Embed Links`, and `Read Message History` permissions in the channel where you're posting polls.

**Q: Where is the database stored?**  
A: The SQLite database (`polls.db`) is created automatically in the same folder as `bot.py`. You can inspect it with any SQLite viewer (e.g. DB Browser for SQLite).

**Q: Can I change the poll colors or emojis?**  
A: Yes! Edit `config.py` — all colors, emojis, button styles, and timing constants are there.

---

## 🛠 Customization

| Setting | File | Variable |
|---|---|---|
| Embed colors | `config.py` | `COLOR_PRIMARY`, `COLOR_SUCCESS`, etc. |
| Button emojis | `config.py` | `OPTION_EMOJIS` |
| Button styles | `config.py` | `BUTTON_STYLES` |
| Max options per poll | `config.py` | `MAX_OPTIONS` (default: 10) |
| Max poll duration | `config.py` | `MAX_POLL_DURATION_MINUTES` (default: 7 days) |
| Expiry check interval | `config.py` | `POLL_CHECK_INTERVAL` (default: 15s) |
| Countdown refresh rate | `config.py` | `COUNTDOWN_UPDATE_INTERVAL` (default: 30s) |
| Progress bar style | `config.py` | `BAR_FULL`, `BAR_EMPTY`, `BAR_LENGTH` |
