import asyncio
import re
import os
os.system("pip install pynacl")
import sys
import discord
from datetime import datetime, timedelta
from discord.ext import commands, tasks
from discord import app_commands
from flask import Flask
from threading import Thread
import json
import random
from typing import Optional
from discord.ui import Button, View

# ==========================
# FLASK KEEP-ALIVE
# ==========================
app = Flask('')

@app.route('/')
def home():
    return "🤖 Bot is alive and running!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
    print(f"🌐 Web server running on port {os.environ.get('PORT', 8080)}")

# ==========================
# BOT SETUP
# ==========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.guilds = True
intents.invites = True

bot = commands.Bot(command_prefix="/", intents=intents)  # البادئة موجودة ولكن لن تُستخدم
bot.owner_id = 1454256976048558240

# ==========================
# SETTINGS
# ==========================
BAD_WORDS = ["rab", "omk", "o5tek"]
LOG_CHANNEL_NAME = "logs"
warnings = {}
last_voice_channel = {}
manual_leave = set()
warn_reasons = {}
invite_data = {}
invite_cache = {}
afk_tracker = {}

INVITE_REGEX = re.compile(
    r"(https?://)?(www\.)?(discord\.gg|discord\.com/invite|discord\.app/invite)/\S+",
    re.I
)

# ==========================
# 📊 نظام المستويات (Level System)
# ==========================
LEVEL_FILE = "level_data.json"
user_data = {}
level_rewards = {}
voice_time = {}

def load_levels():
    global user_data, level_rewards
    try:
        with open(LEVEL_FILE, "r") as f:
            data = json.load(f)
            user_data = data.get("user_data", {})
            level_rewards = data.get("level_rewards", {})
        print("✅ Level data loaded!")
    except:
        user_data = {}
        level_rewards = {}
        print("📝 New level data created!")

def save_levels():
    data = {"user_data": user_data, "level_rewards": level_rewards}
    try:
        with open(LEVEL_FILE, "w") as f:
            json.dump(data, f, indent=4)
        print("💾 Level data saved!")
    except Exception as e:
        print(f"❌ Save error: {e}")

load_levels()

def get_user(user_id):
    user_id = str(user_id)
    if user_id not in user_data:
        user_data[user_id] = {"xp": 0, "level": 0}
        save_levels()
    return user_data[user_id]

def add_xp(user_id, amount):
    user = get_user(user_id)
    user["xp"] += amount
    xp_needed = (user["level"] + 1) * 100
    if user["xp"] >= xp_needed:
        user["xp"] = 0
        user["level"] += 1
        save_levels()
        return True
    save_levels()
    return False

async def check_rank(member):
    user = get_user(member.id)
    level = user["level"]
    role_to_give = None
    for role_name, req_level in level_rewards.items():
        if level >= req_level:
            role_to_give = role_name
    if role_to_give is None:
        return
    role = discord.utils.get(member.guild.roles, name=role_to_give)
    if role is None:
        try:
            role = await member.guild.create_role(
                name=role_to_give,
                color=discord.Color.gold(),
                reason=f"Level {level} reached"
            )
            print(f"✅ Created rank: {role_to_give}")
        except:
            return
    if role not in member.roles:
        try:
            await member.add_roles(role, reason=f"Reached Level {level}")
            print(f"🎖️ {member.display_name} got {role_to_give}")
        except:
            pass

async def send_level_up(member, guild, source="chat"):
    user = get_user(member.id)
    new_level = user["level"]
    channel = discord.utils.get(guild.text_channels, name="└📊・𝐋𝐞𝐯𝐞𝐥-𝐔𝐏")
    if channel is None:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(send_messages=True, read_messages=True),
            guild.me: discord.PermissionOverwrite(send_messages=True, read_messages=True)
        }
        channel = await guild.create_text_channel(
            name="└📊・𝐋𝐞𝐯𝐞𝐥-𝐔𝐏",
            overwrites=overwrites,
            reason="Level-Up channel created"
        )
    embed = discord.Embed(
        title="🎉 Level Up!",
        description=f"{member.mention} reached **Level {new_level}**!",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="Keep going! 🚀")
    await channel.send(embed=embed)
    try:
        dm = discord.Embed(
            title="🎉 You Leveled Up!",
            description=f"Congratulations {member.name}! You reached **Level {new_level}**!",
            color=discord.Color.gold()
        )
        await member.send(embed=dm)
    except:
        pass

# ==========================
# 🎵 VOICE STATE + AFK + XP
# ==========================
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id:
        guild = member.guild
        if after.channel:
            last_voice_channel[guild.id] = after.channel.id
            return
        if guild.id in manual_leave:
            manual_leave.remove(guild.id)
            return
        if before.channel and guild.id in last_voice_channel:
            await asyncio.sleep(3)
            try:
                if guild.voice_client is None:
                    channel = guild.get_channel(last_voice_channel[guild.id])
                    if channel:
                        await channel.connect()
                        print(f"🔄 Bot reconnected")
            except Exception as e:
                print(f"❌ Reconnect error: {e}")
        return
    
    if member.bot:
        return
    
    afk_channel = discord.utils.get(member.guild.voice_channels, name="├😴・𝙰𝚏𝚔")
    
    if after.channel == afk_channel:
        if str(member.id) in voice_time:
            del voice_time[str(member.id)]
        if member.id in afk_tracker:
            del afk_tracker[member.id]
        return
    
    if after.self_deaf and not before.self_deaf:
        afk_tracker[member.id] = {
            "start_time": datetime.utcnow(),
            "message_sent": False,
            "channel_id": after.channel.id if after.channel else None
        }
        print(f"🔇 {member.display_name} Self-Deaf")
        asyncio.create_task(afk_monitor(member))
    elif not after.self_deaf and before.self_deaf:
        if member.id in afk_tracker:
            del afk_tracker[member.id]
            print(f"🔊 {member.display_name} cancel Self-Deaf")
    
    if after.channel and before.channel is None and after.channel != afk_channel:
        voice_time[str(member.id)] = datetime.utcnow()
    elif before.channel and after.channel is None:
        if str(member.id) in voice_time:
            start = voice_time[str(member.id)]
            diff = (datetime.utcnow() - start).total_seconds()
            xp = int(diff // 60)
            if xp > 0:
                leveled = add_xp(member.id, xp)
                if leveled:
                    await check_rank(member)
                    await send_level_up(member, member.guild, "voice")
            del voice_time[str(member.id)]

# ==========================
# 🛏️ AFK MONITOR
# ==========================
async def afk_monitor(member):
    await asyncio.sleep(300)
    if member.id not in afk_tracker:
        return
    if not member.voice or not member.voice.self_deaf:
        if member.id in afk_tracker:
            del afk_tracker[member.id]
        return
    if not afk_tracker[member.id]["message_sent"]:
        afk_tracker[member.id]["message_sent"] = True
        try:
            embed = discord.Embed(
                title="🔇 AFK Alert",
                description="You are currently **deafened** in **Death Whisper Community**.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="⏰ Alert",
                value="You will be moved to **AFK** after **1 hour** of being deaf.",
                inline=False
            )
            embed.set_footer(text="🔊 Unmute yourself to cancel AFK")
            await member.send(embed=embed)
        except:
            pass
    await asyncio.sleep(3600)
    if member.id not in afk_tracker:
        return
    if not member.voice or not member.voice.self_deaf:
        if member.id in afk_tracker:
            del afk_tracker[member.id]
        return
    try:
        afk_channel = discord.utils.get(member.guild.voice_channels, name="├😴・𝙰𝚏𝚔")
        if afk_channel is None:
            afk_channel = await member.guild.create_voice_channel(
                name="├😴・𝙰𝚏𝚔",
                reason="AFK channel created"
            )
        await member.move_to(afk_channel, reason="Self-Deaf For one hour")
        channel = discord.utils.get(member.guild.text_channels, name=LOG_CHANNEL_NAME)
        if channel is None:
            channel = member.guild.system_channel
        if channel:
            await channel.send(f"🔇 {member.mention} moved to **AFK** after 1 hour of Self-Deaf.")
        if member.id in afk_tracker:
            del afk_tracker[member.id]
    except Exception as e:
        print(f"❌ AFK error: {e}")

# ==========================
# 📊 LOAD INVITE CACHE
# ==========================
async def load_invite_cache():
    global invite_cache
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            invite_cache[guild.id] = {}
            for invite in invites:
                invite_cache[guild.id][invite.code] = invite
            await asyncio.sleep(0.5)
        except:
            pass

# ==========================
# 🎯 ON_READY (مع تأخير لتجنب Rate Limit)
# ==========================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"✅ Bot is ready!")
    print(f"✅ Connected to {len(bot.guilds)} guilds")
    print(f"👑 Owner ID: {bot.owner_id}")
    
    # تحميل الدعوات
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            for invite in invites:
                if invite.inviter:
                    inviter_id = str(invite.inviter.id)
                    if inviter_id not in invite_data:
                        invite_data[inviter_id] = 0
                    invite_data[inviter_id] += invite.uses
            await asyncio.sleep(1)
        except:
            pass
    print("📊 Invite data loaded!")
    
    # تحميل الكاش
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            invite_cache[guild.id] = {}
            for invite in invites:
                invite_cache[guild.id][invite.code] = invite
            await asyncio.sleep(0.5)
        except:
            pass
    print("📊 Invite cache loaded!")
    
    load_levels()
    update_voice_xp_level.start()
    print("🎵 Voice XP tracker started!")
    
    # مزامنة أوامر Slash مع ديسكورد
    await bot.tree.sync()
    print("✅ Slash commands synced globally!")

# ==========================
# 🔄 VOICE XP UPDATE (5 MIN)
# ==========================
@tasks.loop(minutes=5)
async def update_voice_xp_level():
    if not voice_time:
        return
    current_time = datetime.utcnow()
    for user_id, start_time in list(voice_time.items()):
        diff = (current_time - start_time).total_seconds()
        if diff >= 300:
            leveled = add_xp(int(user_id), 5)
            voice_time[user_id] = current_time
            if leveled:
                for guild in bot.guilds:
                    member = guild.get_member(int(user_id))
                    if member:
                        await check_rank(member)
                        await send_level_up(member, member.guild, "voice")
                        break

# ==========================
# 🎯 ON_MEMBER_JOIN + INVITE
# ==========================
@bot.event
async def on_member_join(member):
    if member.bot:
        return
    guild = member.guild
    
    invite_channel = discord.utils.get(guild.text_channels, name="├💌・𝗜𝗻𝘃𝗶𝘁𝗲")
    if invite_channel is None:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(send_messages=True, read_messages=True),
            guild.me: discord.PermissionOverwrite(send_messages=True, read_messages=True)
        }
        invite_channel = await guild.create_text_channel(
            name="├💌・𝗜𝗻𝘃𝗶𝘁𝗲",
            overwrites=overwrites,
            reason="Invite channel created"
        )
        print("✅ Invite channel created!")
    
    try:
        new_invites = await guild.invites()
        inviter = None
        for invite in new_invites:
            old_invite = invite_cache.get(guild.id, {}).get(invite.code)
            if old_invite:
                if invite.uses > old_invite.uses:
                    inviter = invite.inviter
                    break
            else:
                if invite.uses > 0:
                    inviter = invite.inviter
                    break
        
        for invite in new_invites:
            if guild.id not in invite_cache:
                invite_cache[guild.id] = {}
            invite_cache[guild.id][invite.code] = invite
        
        if inviter and not inviter.bot:
            embed = discord.Embed(
                description=f"{member.mention} **Has Been Invited By** {inviter.mention}",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"ID: {member.id}")
            embed.timestamp = datetime.utcnow()
            
            inviter_id = str(inviter.id)
            invite_data[inviter_id] = invite_data.get(inviter_id, 0) + 1
            try:
                await inviter.send(f"🎉 {member.display_name} joined using your invite! Total: {invite_data[inviter_id]}")
            except:
                pass
        else:
            embed = discord.Embed(
                description=f"{member.mention} **Joined the server!**",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"ID: {member.id}")
            embed.timestamp = datetime.utcnow()
        
        await invite_channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Invite error: {e}")

# ==========================
# 📨 ON_MESSAGE (FILTER + XP)
# ==========================
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if not message.guild:
        return await bot.process_commands(message)
    
    # Filter
    if not message.author.guild_permissions.administrator:
        content = message.content.lower()
        if INVITE_REGEX.search(content):
            await message.delete()
            await message.author.timeout(timedelta(minutes=1), reason="Discord Invite")
            return
        for word in BAD_WORDS:
            if word in content:
                await message.delete()
                warnings[message.author.id] = warnings.get(message.author.id, 0) + 1
                log = discord.utils.get(message.guild.text_channels, name=LOG_CHANNEL_NAME)
                if log:
                    await log.send(f"⚠️ {message.author.mention} used `{word}` ({warnings[message.author.id]}/3)")
                if warnings[message.author.id] >= 3:
                    await message.author.timeout(timedelta(minutes=10), reason="3 Bad Words")
                    warnings[message.author.id] = 0
                return
    
    # XP System
    if message.author.voice and message.author.voice.channel:
        afk_channel = discord.utils.get(message.guild.voice_channels, name="├😴・𝙰𝚏𝚔")
        if message.author.voice.channel == afk_channel:
            await bot.process_commands(message)
            return
    
    xp = random.randint(1, 3)
    if add_xp(message.author.id, xp):
        await check_rank(message.author)
        await send_level_up(message.author, message.guild, "chat")
    
    await bot.process_commands(message)

# ==========================
# 🚀 نظام البوستات (Boost Tracker)
# ==========================
@bot.event
async def on_member_update(before, after):
    if before.premium_since is None and after.premium_since is not None:
        guild = after.guild
        boost_channel = discord.utils.get(guild.text_channels, name="├🚀・𝐁𝐨𝐨𝐬𝐭𝐬")
        if boost_channel is None:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(send_messages=True, read_messages=True),
                guild.me: discord.PermissionOverwrite(send_messages=True, read_messages=True)
            }
            boost_channel = await guild.create_text_channel(
                name="├🚀・𝐁𝐨𝐨𝐬𝐭𝐬",
                overwrites=overwrites,
                reason="تم إنشاء روم البوستات"
            )
            print("✅ تم إنشاء روم البوستات!")
        try:
            embed = discord.Embed(
                description=f"🚀 {after.mention} **boosted the server!** Thank you! 🎉",
                color=discord.Color.purple()
            )
            embed.set_thumbnail(url=after.display_avatar.url)
            embed.add_field(name="⭐ Boost Count", value=f"{guild.premium_subscription_count} boosts", inline=True)
            embed.add_field(name="📊 Boost Level", value=f"Level {guild.premium_tier}", inline=True)
            embed.set_footer(text=f"ID: {after.id} • {after.name}")
            embed.timestamp = datetime.utcnow()
            await boost_channel.send(embed=embed)
        except Exception as e:
            print(f"❌ Erro in booste système : {e}")

# ==========================
# 👋 نظام المغادرة (Leave Tracker)
# ==========================
@bot.event
async def on_member_remove(member):
    if member.bot:
        return
    guild = member.guild
    leave_channel = discord.utils.get(guild.text_channels, name="├👋・𝐋𝐞𝐚𝐯𝐞𝐬")
    if leave_channel is None:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(send_messages=True, read_messages=True),
            guild.me: discord.PermissionOverwrite(send_messages=True, read_messages=True)
        }
        leave_channel = await guild.create_text_channel(
            name="├👋・𝐋𝐞𝐚𝐯𝐞𝐬",
            overwrites=overwrites,
            reason="تم إنشاء روم المغادرين"
        )
        print("✅ تم إنشاء روم المغادرين!")
    try:
        embed = discord.Embed(
            description=f"👋 **𝐆𝐎𝐃𝐁𝐘𝐄** {member.mention}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id} • {member.name}")
        embed.timestamp = datetime.utcnow()
        await leave_channel.send(embed=embed)
    except Exception as e:
        print(f"❌ خطأ في نظام المغادرة: {e}")

# ==========================
# ⚖️ PUNISHMENT SYSTEM (Helper Functions)
# ==========================
def convert_time_to_seconds(time_str: str):
    time_str = time_str.lower()
    if time_str.endswith('s'):
        return int(time_str[:-1])
    elif time_str.endswith('m'):
        return int(time_str[:-1]) * 60
    elif time_str.endswith('h'):
        return int(time_str[:-1]) * 3600
    elif time_str.endswith('d'):
        return int(time_str[:-1]) * 86400
    else:
        return None

async def send_punishment_dm(member, punishment_type, duration, reason, moderator):
    try:
        embed = discord.Embed(
            title=f"⚠️ {punishment_type}",
            description=f"You have been **{punishment_type.lower()}** in **{member.guild.name}**.",
            color=discord.Color.red()
        )
        embed.add_field(name="📌 Reason", value=reason if reason else "No reason provided.", inline=False)
        embed.add_field(name="⏰ Duration", value=duration, inline=True)
        embed.add_field(name="👮 Moderator", value=moderator.display_name, inline=True)
        embed.set_footer(text=f"User ID: {member.id}")
        embed.timestamp = discord.utils.utcnow()
        await member.send(embed=embed)
        print(f"✅ DM sent to {member.display_name}")
    except discord.Forbidden:
        print(f"❌ DM blocked for {member.display_name}")
    except Exception as e:
        print(f"❌ Error sending DM: {e}")

async def send_to_punishment_channel(guild, punishment_type, member, moderator, duration, reason):
    try:
        channel = discord.utils.get(guild.text_channels, name="└🚫・𝗣𝚞𝚗𝚜𝚑𝚒𝚖𝚎𝚗𝚝")
        if channel is None:
            channel = await guild.create_text_channel(
                name="└🚫・𝗣𝚞𝚗𝚜𝚑𝚒𝚖𝚎𝚗𝚝",
                reason="Punishment channel created automatically."
            )
            print("✅ Punishment channel created.")
        embed = discord.Embed(
            title=f"# Member @{member.display_name} has been {punishment_type.lower()}.",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Executed By",
            value=f"User: @{moderator.display_name}\nUser ID: ({moderator.id})",
            inline=False
        )
        embed.add_field(
            name="Punishment Reason",
            value=reason if reason else "No reason provided.",
            inline=False
        )
        if duration and duration != "N/A" and duration != "Permanent":
            embed.add_field(name="Punishment Duration", value=duration, inline=False)
        elif duration == "Permanent":
            embed.add_field(name="Punishment Duration", value="**Permanent**", inline=False)
        embed.set_footer(text=f"Executed at: {discord.utils.utcnow().strftime('%d/%m/%Y %H:%M')}")
        embed.timestamp = discord.utils.utcnow()
        await channel.send(embed=embed)
        print(f"📝 Punishment logged in punishment channel.")
    except Exception as e:
        print(f"❌ Error sending to punishment channel: {e}")

async def log_punishment(guild, punishment_type, member, moderator, duration, reason):
    try:
        log_channel = discord.utils.get(guild.text_channels, name="logs")
        if log_channel is None:
            log_channel = await guild.create_text_channel(
                name="logs",
                reason="Logs channel created automatically."
            )
            print("✅ Logs channel created.")
        embed = discord.Embed(
            title=f"📋 {punishment_type}",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="👤 Member", value=f"{member.mention} ({member.display_name})", inline=False)
        embed.add_field(name="👮 Moderator", value=f"{moderator.mention} ({moderator.display_name})", inline=False)
        embed.add_field(name="⏰ Duration", value=duration, inline=True)
        embed.add_field(name="📌 Reason", value=reason if reason else "No reason provided.", inline=False)
        embed.set_footer(text=f"Member ID: {member.id} | Moderator ID: {moderator.id}")
        embed.timestamp = discord.utils.utcnow()
        await log_channel.send(embed=embed)
        print(f"📝 Punishment logged in logs channel.")
    except Exception as e:
        print(f"❌ Error logging punishment: {e}")

async def unban_after(guild, user_id, delay):
    await asyncio.sleep(delay)
    try:
        user = await guild.fetch_member(user_id)
        if user:
            await guild.unban(user)
            print(f"✅ {user.display_name} has been unbanned automatically.")
            log_channel = discord.utils.get(guild.text_channels, name="logs")
            if log_channel:
                embed = discord.Embed(
                    title="✅ Automatic Unban",
                    description=f"<@{user_id}> has been unbanned automatically.",
                    color=discord.Color.green()
                )
                await log_channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Error in auto-unban: {e}")

# ==========================
# 🎯 SLASH COMMANDS (جميع الأوامر)
# ==========================

# ----- الإدارة والعقوبات -----

@bot.tree.command(name="timeout", description="Timeout a member for a specified duration.")
@app_commands.describe(
    member="The member to timeout",
    duration="e.g., 10m, 1h, 1d",
    reason="Reason for timeout"
)
async def slash_timeout(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided."):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
    seconds = convert_time_to_seconds(duration)
    if seconds is None:
        return await interaction.response.send_message("❌ Invalid time format! Use: `10s`, `5m`, `2h`, `1d`", ephemeral=True)
    if seconds > 2419200:
        return await interaction.response.send_message("❌ Maximum timeout is 28 days.", ephemeral=True)
    try:
        await member.timeout(timedelta(seconds=seconds), reason=reason)
        await send_punishment_dm(member, "Timeout", duration, reason, interaction.user)
        await send_to_punishment_channel(interaction.guild, "Timeout", member, interaction.user, duration, reason)
        await log_punishment(interaction.guild, "⏱️ Timeout", member, interaction.user, duration, reason)
        embed = discord.Embed(
            title="⏱️ Timeout",
            description=f"{member.mention} has been timed out!",
            color=discord.Color.orange()
        )
        embed.add_field(name="Duration", value=duration, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.set_footer(text=f"ID: {member.id}")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="ban", description="Ban a member (permanent or temporary).")
@app_commands.describe(
    member="The member to ban",
    duration="e.g., 1d (leave blank for permanent)",
    reason="Reason for ban"
)
async def slash_ban(interaction: discord.Interaction, member: discord.Member, duration: str = None, reason: str = "No reason provided."):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
    try:
        if duration and duration.lower() != "permanent":
            seconds = convert_time_to_seconds(duration)
            if seconds is None:
                return await interaction.response.send_message("❌ Invalid time format! Use: `10m`, `1h`, `1d`", ephemeral=True)
            await send_punishment_dm(member, "Temporary Ban", duration, reason, interaction.user)
            await member.ban(reason=f"{reason} (Temporary: {duration})")
            await send_to_punishment_channel(interaction.guild, "Temporary Ban", member, interaction.user, duration, reason)
            await log_punishment(interaction.guild, "🔨 Temporary Ban", member, interaction.user, duration, reason)
            asyncio.create_task(unban_after(interaction.guild, member.id, seconds))
            embed = discord.Embed(
                title="🔨 Temporary Ban",
                description=f"{member.mention} has been banned for {duration}!",
                color=discord.Color.red()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            await interaction.response.send_message(embed=embed)
        else:
            await send_punishment_dm(member, "Permanent Ban", "Permanent", reason, interaction.user)
            await member.ban(reason=reason)
            await send_to_punishment_channel(interaction.guild, "Permanent Ban", member, interaction.user, "Permanent", reason)
            await log_punishment(interaction.guild, "🔨 Permanent Ban", member, interaction.user, "Permanent", reason)
            embed = discord.Embed(
                title="🔨 Permanent Ban",
                description=f"{member.mention} has been banned permanently!",
                color=discord.Color.dark_red()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="kick", description="Kick a member from the server.")
@app_commands.describe(
    member="The member to kick",
    reason="Reason for kick"
)
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided."):
    if not interaction.user.guild_permissions.kick_members:
        return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
    try:
        await send_punishment_dm(member, "Kick", "N/A", reason, interaction.user)
        await member.kick(reason=reason)
        await send_to_punishment_channel(interaction.guild, "Kick", member, interaction.user, "N/A", reason)
        await log_punishment(interaction.guild, "👢 Kick", member, interaction.user, "N/A", reason)
        embed = discord.Embed(
            title="👢 Kick",
            description=f"{member.mention} has been kicked!",
            color=discord.Color.yellow()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="untimeout", description="Remove timeout from a member.")
@app_commands.describe(
    member="The member to untimeout",
    reason="Reason for removal"
)
async def slash_untimeout(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided."):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
    try:
        await member.timeout(None, reason=reason)
        embed = discord.Embed(
            title="✅ Timeout Removed",
            description=f"{member.mention} has been untimed out.",
            color=discord.Color.green()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)
        log_channel = discord.utils.get(interaction.guild.text_channels, name="logs")
        if log_channel:
            log_embed = discord.Embed(
                title="✅ Timeout Removed",
                description=f"{member.mention} was untimed out by {interaction.user.mention}",
                color=discord.Color.green()
            )
            log_embed.add_field(name="Reason", value=reason, inline=False)
            await log_channel.send(embed=log_embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="unban", description="Unban a user by their ID.")
@app_commands.describe(
    user_id="The ID of the user to unban",
    reason="Reason for unban"
)
async def slash_unban(interaction: discord.Interaction, user_id: str, reason: str = "No reason provided."):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user, reason=reason)
        embed = discord.Embed(
            title="✅ Unban",
            description=f"{user.mention} has been unbanned.",
            color=discord.Color.green()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)
        log_channel = discord.utils.get(interaction.guild.text_channels, name="logs")
        if log_channel:
            log_embed = discord.Embed(
                title="✅ Unban",
                description=f"{user.mention} was unbanned by {interaction.user.mention}",
                color=discord.Color.green()
            )
            log_embed.add_field(name="Reason", value=reason, inline=False)
            await log_channel.send(embed=log_embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

# ----- المعلومات -----

@bot.tree.command(name="avatar", description="Display a user's avatar.")
@app_commands.describe(member="User to show avatar (leave blank for yourself)")
async def slash_avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"🖼️ {member.display_name}'s Avatar", color=discord.Color.blue())
    embed.set_image(url=member.display_avatar.url)
    embed.set_footer(text=f"Requested by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Show server information.")
async def slash_serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    humans = len([m for m in guild.members if not m.bot])
    embed = discord.Embed(title=f"📊 Server Info - {guild.name}", color=discord.Color.blue())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="👑 Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="🆔 ID", value=guild.id, inline=True)
    embed.add_field(name="📅 Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="👥 Members", value=f"{guild.member_count} (👤{humans} 🤖{guild.member_count-humans})", inline=True)
    embed.add_field(name="💬 Channels", value=f"📝{len(guild.text_channels)} 🔊{len(guild.voice_channels)} 📁{len(guild.categories)}", inline=True)
    embed.add_field(name="🎭 Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="🔗 Boost Level", value=guild.premium_tier, inline=True)
    embed.add_field(name="⭐ Boost Count", value=guild.premium_subscription_count, inline=True)
    if guild.vanity_url:
        embed.add_field(name="🔗 Vanity URL", value=guild.vanity_url, inline=False)
    embed.set_footer(text=f"Requested by: {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Show user information.")
@app_commands.describe(member="User to show info (leave blank for yourself)")
async def slash_userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    roles = [r.mention for r in member.roles if r != interaction.guild.default_role]
    embed = discord.Embed(title=f"👤 User Info - {member.display_name}", color=member.color if member.color != discord.Color.default() else discord.Color.blue())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🆔 ID", value=member.id, inline=True)
    embed.add_field(name="📛 Name", value=member.name, inline=True)
    embed.add_field(name="🎭 Nickname", value=member.nick if member.nick else "None", inline=True)
    embed.add_field(name="📅 Joined", value=member.joined_at.strftime("%Y-%m-%d %H:%M"), inline=True)
    embed.add_field(name="📅 Created", value=member.created_at.strftime("%Y-%m-%d %H:%M"), inline=True)
    embed.add_field(name="🎭 Roles", value=", ".join(roles) if roles else "No roles", inline=False)
    embed.add_field(name="🤖 Bot", value="Yes" if member.bot else "No", inline=True)
    embed.add_field(name="🔊 In Voice", value="Yes" if member.voice else "No", inline=True)
    embed.set_footer(text=f"Requested by: {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ping", description="Check bot latency.")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

# ----- المستويات -----

@bot.tree.command(name="level", description="Check your or someone else's level.")
@app_commands.describe(member="User to check (leave blank for yourself)")
async def slash_level(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    user = get_user(member.id)
    needed = (user["level"] + 1) * 100
    embed = discord.Embed(title=f"📊 Level - {member.display_name}", color=discord.Color.blue())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🎯 Level", value=f"**{user['level']}**", inline=True)
    embed.add_field(name="⭐ XP", value=f"**{user['xp']}** / {needed}", inline=True)
    embed.add_field(name="📊 Progress", value=f"**{int((user['xp'] / needed) * 100)}%**", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard_level", description="Show the level leaderboard.")
async def slash_leaderboard_level(interaction: discord.Interaction):
    if not user_data:
        return await interaction.response.send_message("📊 No data yet!")
    sorted_users = sorted(user_data.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)[:10]
    embed = discord.Embed(title="🏆 Level Leaderboard", color=discord.Color.gold())
    desc = ""
    for i, (uid, data) in enumerate(sorted_users, 1):
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name
        except:
            name = "Unknown"
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
        desc += f"{medal} **{name}** → Level **{data['level']}** (XP: {data['xp']})\n"
    embed.description = desc
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="level_roles", description="Show available level roles.")
async def slash_level_roles(interaction: discord.Interaction):
    if not level_rewards:
        return await interaction.response.send_message("📊 No roles set! Use `/set_role`.")
    embed = discord.Embed(title="🎖️ Level Roles", color=discord.Color.blue())
    desc = ""
    for role_name, level in sorted(level_rewards.items(), key=lambda x: x[1]):
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        desc += f"{role.mention if role else role_name} → Level **{level}**\n"
    embed.description = desc
    await interaction.response.send_message(embed=embed)

# ----- الدعوات -----

@bot.tree.command(name="invites", description="Check a user's invite count.")
@app_commands.describe(member="User to check (leave blank for yourself)")
async def slash_invites(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    count = invite_data.get(str(member.id), 0)
    embed = discord.Embed(title="📊 Invites", description=f"{member.mention} has **{count}** invites!", color=discord.Color.blue())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Requested by: {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard_invites", description="Show the top 10 inviters.")
async def slash_leaderboard_invites(interaction: discord.Interaction):
    if not invite_data:
        return await interaction.response.send_message("📊 No invites yet!")
    sorted_invites = sorted(invite_data.items(), key=lambda x: x[1], reverse=True)[:10]
    embed = discord.Embed(title="🏆 Leaderboard - Invites", description="Top 10 Members", color=discord.Color.gold())
    desc = ""
    for i, (uid, count) in enumerate(sorted_invites, 1):
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name
        except:
            name = "Unknown"
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
        desc += f"{medal} **{name}** → `{count}` invites\n"
    embed.description = desc
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"Requested by: {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed)

# ----- الإدارة (قفل/فتح) -----

@bot.tree.command(name="lock", description="Lock the current channel.")
async def slash_lock(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    try:
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(f"🔒 **{interaction.channel.mention} locked!**")
    except:
        await interaction.response.send_message("❌ Failed to lock channel.", ephemeral=True)

@bot.tree.command(name="unlock", description="Unlock the current channel.")
async def slash_unlock(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        return await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = None
    try:
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message(f"🔓 **{interaction.channel.mention} unlocked!**")
    except:
        await interaction.response.send_message("❌ Failed to unlock channel.", ephemeral=True)

# ==========================
# RUN BOT
# ==========================
TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN is None:
    print("❌ Error: DISCORD_TOKEN not found!")
    sys.exit(1)

print("🚀 Starting bot...")
keep_alive()
print("🤖 Bot is starting...")
try:
    bot.run(TOKEN)
except Exception as e:
    print(f"❌ Bot error: {e}")
    sys.exit(1)
