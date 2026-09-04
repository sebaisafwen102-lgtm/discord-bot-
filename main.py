import asyncio
import re
import os
os.system("pip install pynacl")
import sys
import discord
from datetime import datetime, timedelta
from discord.ext import commands, tasks
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

bot = commands.Bot(command_prefix="!", intents=intents)
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
    # إعادة الاتصال للبوت
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
    
    # AFK
    if after.channel == afk_channel:
        if str(member.id) in voice_time:
            del voice_time[str(member.id)]
        if member.id in afk_tracker:
            del afk_tracker[member.id]
        return
    
    # Self-Deaf
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
    
    # Voice XP
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
    
    # تحميل الدعوات مع تأخير
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
    
    # تحميل الكاش مع تأخير
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
    
    # تحميل المستويات
    load_levels()
    update_voice_xp_level.start()
    print("🎵 Voice XP tracker started!")

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
# 🎯 COMMANDS
# ==========================

# Hello
@bot.command()
@commands.is_owner()
async def hello(ctx):
    await ctx.send(f'👋 Hello {ctx.author.mention}!')

# Write
@bot.command()
@commands.is_owner()
async def write(ctx, *, message):
    await ctx.message.delete()
    await ctx.send(message)

# Voice
@bot.command()
@commands.is_owner()
async def join(ctx):
    if not ctx.author.voice:
        return await ctx.send("❌ You must be in a voice channel first!")
    channel = ctx.author.voice.channel
    if not channel.permissions_for(ctx.guild.me).connect:
        return await ctx.send("❌ No permission to join!")
    try:
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()
        last_voice_channel[ctx.guild.id] = channel.id
        if ctx.guild.id in manual_leave:
            manual_leave.remove(ctx.guild.id)
        await ctx.send(f"✅ Joined **{channel.name}**")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command()
@commands.is_owner()
async def leave(ctx):
    if not ctx.voice_client:
        return await ctx.send("❌ Not in a voice channel!")
    manual_leave.add(ctx.guild.id)
    try:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Left voice channel!")
        if ctx.guild.id in last_voice_channel:
            del last_voice_channel[ctx.guild.id]
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

# Warnings
@bot.command()
@commands.is_owner()
async def warn(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    warnings[member.id] = warnings.get(member.id, 0) + 1
    if member.id not in warn_reasons:
        warn_reasons[member.id] = []
    warn_reasons[member.id].append({
        "reason": reason,
        "by": ctx.author.id,
        "time": ctx.message.created_at.strftime("%Y-%m-%d %H:%M")
    })
    try:
        await member.send(f"⚠️ Warned in {ctx.guild.name}\nReason: {reason}\nWarnings: {warnings[member.id]}/3")
    except:
        pass
    embed = discord.Embed(title="⚠️ Warning", description=f"{member.mention} warned!", color=discord.Color.orange())
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Warnings", value=f"{warnings[member.id]}/3", inline=True)
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.set_footer(text=f"ID: {member.id}")
    await ctx.send(embed=embed)
    if warnings[member.id] >= 3:
        await member.timeout(timedelta(minutes=10), reason="3 warnings")
        await ctx.send(f"🔇 {member.mention} timed out for 10 minutes")
        warnings[member.id] = 0

@bot.command()
@commands.is_owner()
async def warnings(ctx, member: discord.Member):
    count = warnings.get(member.id, 0)
    embed = discord.Embed(title=f"⚠️ Warnings for {member.display_name}", color=discord.Color.blue())
    embed.add_field(name="Total Warnings", value=f"{count}/3", inline=False)
    if member.id in warn_reasons and warn_reasons[member.id]:
        text = ""
        for i, w in enumerate(warn_reasons[member.id], 1):
            text += f"**{i}.** {w['reason']} (by <@{w['by']}> at {w['time']})\n"
        embed.add_field(name="Reasons", value=text, inline=False)
    else:
        embed.add_field(name="Reasons", value="No warnings.", inline=False)
    embed.set_footer(text=f"ID: {member.id}")
    await ctx.send(embed=embed)

@bot.command()
@commands.is_owner()
async def reset_warnings(ctx, member: discord.Member):
    warnings[member.id] = 0
    if member.id in warn_reasons:
        warn_reasons[member.id] = []
    await ctx.send(f"✅ Warnings reset for {member.mention}")

@bot.command()
@commands.is_owner()
async def check_warnings(ctx, member: discord.Member):
    await ctx.send(f"{member.mention} has **{warnings.get(member.id,0)}/3** warnings")

# Bad Words
@bot.command()
@commands.is_owner()
async def add_bad_word(ctx, word: str):
    word = word.lower()
    if word not in BAD_WORDS:
        BAD_WORDS.append(word)
    await ctx.send(f"✅ Added `{word}`")

@bot.command()
@commands.is_owner()
async def remove_bad_word(ctx, word: str):
    word = word.lower()
    if word in BAD_WORDS:
        BAD_WORDS.remove(word)
        await ctx.send(f"✅ Removed `{word}`")
    else:
        await ctx.send("❌ Word not found")

@bot.command()
@commands.is_owner()
async def show_bad_words(ctx):
    if not BAD_WORDS:
        return await ctx.send("No bad words")
    await ctx.send("\n".join(BAD_WORDS))

# Info
@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"🖼️ {member.display_name}'s Avatar", color=discord.Color.blue())
    embed.set_image(url=member.display_avatar.url)
    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
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
    embed.set_footer(text=f"Requested by: {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    roles = [r.mention for r in member.roles if r != ctx.guild.default_role]
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
    embed.set_footer(text=f"Requested by: {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

# Clear
@bot.command()
@commands.is_owner()
async def clear(ctx, amount: int):
    if amount < 1 or amount > 100:
        return await ctx.send("❌ Enter a number between 1-100")
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"✅ Deleted {len(deleted)-1} messages", delete_after=3)

@bot.command()
@commands.is_owner()
async def clear_all(ctx, amount: int):
    if amount < 1 or amount > 100:
        return await ctx.send("❌ Enter a number between 1-100")
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"✅ Deleted {len(deleted)} messages", delete_after=3)

# Lock/Unlock
@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    try:
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"🔒 **{ctx.channel.mention} locked!**")
    except:
        await ctx.send("❌ No permission!")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None
    try:
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"🔓 **{ctx.channel.mention} unlocked!**")
    except:
        await ctx.send("❌ No permission!")

# DM
@bot.command()
@commands.is_owner()
async def dm(ctx, member: discord.Member, *, message: str):
    try:
        embed = discord.Embed(title="📩 Message from Death Whisper", description=message, color=discord.Color.blue())
        embed.set_footer(text=f"from: {ctx.author.display_name}")
        await member.send(embed=embed)
        await ctx.send(f"✅ Sent to {member.display_name}")
    except:
        await ctx.send(f"❌ Couldn't send DM to {member.display_name}")

@bot.command()
@commands.is_owner()
async def dmrole(ctx, role: discord.Role, *, message: str):
    msg = await ctx.send(f"⚠️ Send DM to {len(role.members)} members? Reply `yes` or `no` (30s)")
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['yes', 'no']
    try:
        resp = await bot.wait_for('message', timeout=30, check=check)
        if resp.content.lower() == 'no':
            return await ctx.send("❌ Cancelled")
        await ctx.send(f"⏳ Sending...")
        s, f = 0, 0
        embed = discord.Embed(title="📢 Message from Death Whisper", description=message, color=discord.Color.green())
        embed.set_footer(text=f"from: {ctx.author.display_name}")
        for m in role.members:
            if m.bot:
                continue
            try:
                await m.send(embed=embed)
                s += 1
                await asyncio.sleep(0.3)
            except:
                f += 1
        await ctx.send(f"✅ Sent!\n✅ Success: {s}\n❌ Failed: {f}")
    except asyncio.TimeoutError:
        await ctx.send("⏰ Timeout!")

@bot.command()
@commands.is_owner()
async def dmall(ctx, *, message: str):
    members = [m for m in ctx.guild.members if not m.bot]
    msg = await ctx.send(f"⚠️ Send DM to {len(members)} members? Reply `yes` or `no` (30s)")
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['yes', 'no']
    try:
        resp = await bot.wait_for('message', timeout=30, check=check)
        if resp.content.lower() == 'no':
            return await ctx.send("❌ Cancelled")
        await ctx.send(f"⏳ Sending...")
        s, f = 0, 0
        embed = discord.Embed(title="📢 Message from Death Whisper", description=message, color=discord.Color.green())
        embed.set_footer(text=f"from: {ctx.author.display_name}")
        for m in members:
            try:
                await m.send(embed=embed)
                s += 1
                await asyncio.sleep(0.3)
            except:
                f += 1
        await ctx.send(f"✅ Sent!\n✅ Success: {s}\n❌ Failed: {f}")
    except asyncio.TimeoutError:
        await ctx.send("⏰ Timeout!")

# Embed
@bot.command()
@commands.is_owner()
async def embed(ctx, *, message: str):
    if "|" in message:
        title, desc = message.split("|", 1)
        embed = discord.Embed(title=title.strip(), description=desc.strip(), color=discord.Color.blue())
    else:
        embed = discord.Embed(description=message, color=discord.Color.blue())
    embed.set_footer(text=f"from: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    embed.timestamp = datetime.utcnow()
    await ctx.message.delete()
    await ctx.send(embed=embed)

# Invites
@bot.command()
async def invites(ctx, member: discord.Member = None):
    member = member or ctx.author
    count = invite_data.get(str(member.id), 0)
    embed = discord.Embed(title="📊 Invites", description=f"{member.mention} has **{count}** invites!", color=discord.Color.blue())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Requested by: {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command()
async def leaderboard(ctx):
    if not invite_data:
        return await ctx.send("📊 No invites yet!")
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
    embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
    embed.set_footer(text=f"Requested by: {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command()
@commands.is_owner()
async def reset_invites(ctx, member: discord.Member):
    invite_data[str(member.id)] = 0
    await ctx.send(f"✅ Reset invites for {member.mention}")

@bot.command()
@commands.is_owner()
async def set_invites(ctx, member: discord.Member, count: int):
    if count < 0:
        return await ctx.send("❌ Count must be positive!")
    invite_data[str(member.id)] = count
    await ctx.send(f"✅ Set invites for {member.mention} to `{count}`")

# Level System
@bot.command()
@commands.has_permissions(administrator=True)
async def set_role(ctx, role: discord.Role, level: int):
    if level < 1:
        return await ctx.send("❌ Level must be > 0")
    level_rewards[role.name] = level
    save_levels()
    embed = discord.Embed(title="✅ Role Set!", description=f"{role.mention} → Level **{level}**", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def remove_role(ctx, role: discord.Role):
    if role.name not in level_rewards:
        return await ctx.send(f"❌ {role.mention} not found")
    del level_rewards[role.name]
    save_levels()
    embed = discord.Embed(title="✅ Role Removed!", description=f"{role.mention} removed", color=discord.Color.red())
    await ctx.send(embed=embed)

@bot.command()
async def level_roles(ctx):
    if not level_rewards:
        return await ctx.send("📊 No roles set! Use `!set_role @role level`")
    embed = discord.Embed(title="🎖️ Level Roles", color=discord.Color.blue())
    desc = ""
    for role_name, level in sorted(level_rewards.items(), key=lambda x: x[1]):
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        desc += f"{role.mention if role else role_name} → Level **{level}**\n"
    embed.description = desc
    await ctx.send(embed=embed)

@bot.command()
async def level(ctx, member: discord.Member = None):
    member = member or ctx.author
    user = get_user(member.id)
    needed = (user["level"] + 1) * 100
    embed = discord.Embed(title=f"📊 Level - {member.display_name}", color=discord.Color.blue())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🎯 Level", value=f"**{user['level']}**", inline=True)
    embed.add_field(name="⭐ XP", value=f"**{user['xp']}** / {needed}", inline=True)
    embed.add_field(name="📊 Progress", value=f"**{int((user['xp'] / needed) * 100)}%**", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def leaderboard_level(ctx):
    if not user_data:
        return await ctx.send("📊 No data yet!")
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
    await ctx.send(embed=embed)

@bot.command()
@commands.is_owner()
async def reset_levels(ctx, member: discord.Member = None):
    if member:
        if str(member.id) in user_data:
            user_data[str(member.id)] = {"xp": 0, "level": 0}
            save_levels()
            await ctx.send(f"✅ Reset levels for {member.mention}")
        else:
            await ctx.send(f"❌ {member.mention} has no data")
    else:
        user_data.clear()
        save_levels()
        await ctx.send("✅ Reset all levels")

# Level Up View
class LevelView(View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
    
    @discord.ui.button(label="📊 My Progress", style=discord.ButtonStyle.primary)
    async def progress_btn(self, interaction: discord.Interaction, button: Button):
        user = get_user(interaction.user.id)
        needed = (user["level"] + 1) * 100
        embed = discord.Embed(title=f"📊 {interaction.user.display_name}'s Progress", color=discord.Color.blue())
        embed.add_field(name="Level", value=f"**{user['level']}**", inline=True)
        embed.add_field(name="XP", value=f"**{user['xp']}** / {needed}", inline=True)
        embed.add_field(name="Progress", value=f"**{int((user['xp'] / needed) * 100)}%**", inline=True)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🎖️ Ranks", style=discord.ButtonStyle.success)
    async def ranks_btn(self, interaction: discord.Interaction, button: Button):
        if not level_rewards:
            return await interaction.response.send_message("❌ No ranks set!", ephemeral=True)
        user = get_user(interaction.user.id)
        embed = discord.Embed(title="🎖️ Available Ranks", color=discord.Color.gold())
        text = ""
        for role_name, req in sorted(level_rewards.items(), key=lambda x: x[1]):
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            mention = role.mention if role else f"**{role_name}**"
            status = "✅ Unlocked" if user["level"] >= req else f"🔒 Level {req}"
            text += f"{mention} → `Level {req}` ({status})\n"
        embed.description = text
        embed.set_footer(text=f"Your level: {user['level']}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="❓ How to Earn XP", style=discord.ButtonStyle.secondary)
    async def howto_btn(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="⭐ How to Earn XP",
            description="Here's how you can earn XP:",
            color=discord.Color.blue()
        )
        embed.add_field(name="💬 Chatting", value="Send messages → `1-3 XP`", inline=False)
        embed.add_field(name="🔊 Voice", value="Stay in voice → `5 XP` every 5 minutes", inline=False)
        embed.add_field(name="🚫 No XP", value="• AFK channel • Bots", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command()
async def lvl_up(ctx):
    user = get_user(ctx.author.id)
    needed = (user["level"] + 1) * 100
    progress = int((user["xp"] / needed) * 20)
    bar = "🟩" * progress + "⬛" * (20 - progress)
    
    embed = discord.Embed(
        title="📊 Level System",
        description=f"Welcome **{ctx.author.display_name}**!",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.add_field(
        name="📊 Your Progress",
        value=(
            f"**Level:** `{user['level']}`\n"
            f"**XP:** `{user['xp']}` / `{needed}`\n"
            f"**Progress:** `{int((user['xp'] / needed) * 100)}%`\n"
            f"{bar}"
        ),
        inline=False
    )
    unlocked = sum(1 for _, lvl in level_rewards.items() if user["level"] >= lvl)
    embed.add_field(
        name="🎖️ Ranks",
        value=f"**{unlocked}** / **{len(level_rewards)}** unlocked",
        inline=True
    )
    embed.add_field(
        name="📌 Commands",
        value="`!level` • `!leaderboard_level` • `!level_roles`",
        inline=True
    )
    embed.set_footer(text="Click the buttons below!")
    
    await ctx.send(embed=embed, view=LevelView(ctx))
# ==========================
# 🚀 نظام البوستات (Boost Tracker)
# ==========================

@bot.event
async def on_member_update(before, after):
    """عند تغيير حالة العضو - يكتشف البوستات الجديدة فقط"""
    
    # ===== كشف Boost جديد (فقط) =====
    if before.premium_since is None and after.premium_since is not None:
        # العضو عمل Boost
        guild = after.guild
        
        # نجيب روم البوستات
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
    """عند خروج عضو - يكتب في روم المغادرين"""
    
    if member.bot:
        return
    
    guild = member.guild
    
    # ===== نجيب روم المغادرين =====
    leave_channel = discord.utils.get(guild.text_channels, name="├👋・𝐋𝐞𝐚𝐯𝐞𝐬")
    
    # إذا مش موجود نعملو
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
        # ===== نرسل رسالة GODBYE =====
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
# ⚖️ PUNISHMENT SYSTEM (Timeout, Ban, Kick, Unban, Untimeout)
# ==========================

# ----- Helper Functions -----

def convert_time_to_seconds(time_str: str):
    """Convert time string (e.g., 10m, 1h, 1d) to seconds."""
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

async def send_punishment_dm(member: discord.Member, punishment_type: str, duration: str, reason: str, moderator: discord.Member):
    """Send a DM to the punished member with full details."""
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

async def send_to_punishment_channel(guild: discord.Guild, punishment_type: str, member: discord.Member, moderator: discord.Member, duration: str, reason: str):
    """Log the punishment in the dedicated punishment text channel."""
    try:
        # Get or create the punishment channel
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
        # Add duration if applicable
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

async def log_punishment(guild: discord.Guild, punishment_type: str, member: discord.Member, moderator: discord.Member, duration: str, reason: str):
    """Log the punishment in the logs channel."""
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

async def unban_after(guild: discord.Guild, user_id: int, delay: int):
    """Automatically unban a user after a specified time (for temporary bans)."""
    await asyncio.sleep(delay)
    try:
        user = await guild.fetch_member(user_id)
        if user:
            await guild.unban(user)
            print(f"✅ {user.display_name} has been unbanned automatically.")
            # Log the auto-unban
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

# ----- Punishment Commands -----

@bot.command()
@commands.is_owner()  # Change to @commands.has_permissions(moderate_members=True) for moderators
async def timeout(ctx, member: discord.Member, time: str, *, reason: str = "No reason provided."):
    """
    Timeout a member for a specified duration.
    Usage: !timeout @user 10m reason
    Valid time formats: 10s, 5m, 2h, 1d
    """
    time_seconds = convert_time_to_seconds(time)
    if time_seconds is None:
        return await ctx.send("❌ Invalid time format! Use: `10s`, `5m`, `2h`, `1d`", delete_after=5)
    if time_seconds > 2419200:  # 28 days max
        return await ctx.send("❌ Maximum timeout is 28 days!", delete_after=5)
    
    try:
        await member.timeout(timedelta(seconds=time_seconds), reason=reason)
        await send_punishment_dm(member, "Timeout", time, reason, ctx.author)
        await send_to_punishment_channel(ctx.guild, "Timeout", member, ctx.author, time, reason)
        await log_punishment(ctx.guild, "⏱️ Timeout", member, ctx.author, time, reason)
        
        embed = discord.Embed(
            title="⏱️ Timeout",
            description=f"{member.mention} has been timed out!",
            color=discord.Color.orange()
        )
        embed.add_field(name="Duration", value=time, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.set_footer(text=f"ID: {member.id}")
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}", delete_after=5)

@bot.command()
@commands.is_owner()  # Change to @commands.has_permissions(ban_members=True) for moderators
async def ban(ctx, member: discord.Member, time: str = None, *, reason: str = "No reason provided."):
    """
    Ban a member (permanently or temporarily).
    Usage: !ban @user reason (permanent)
           !ban @user 1d reason (temporary)
    """
    try:
        if time and time.lower() != "permanent":
            time_seconds = convert_time_to_seconds(time)
            if time_seconds is None:
                return await ctx.send("❌ Invalid time format! Use: `10m`, `1h`, `1d`", delete_after=5)
            
            # Temporary ban
            await send_punishment_dm(member, "Temporary Ban", time, reason, ctx.author)
            await member.ban(reason=f"{reason} (Temporary: {time})")
            await send_to_punishment_channel(ctx.guild, "Temporary Ban", member, ctx.author, time, reason)
            await log_punishment(ctx.guild, "🔨 Temporary Ban", member, ctx.author, time, reason)
            asyncio.create_task(unban_after(ctx.guild, member.id, time_seconds))
            
            embed = discord.Embed(
                title="🔨 Temporary Ban",
                description=f"{member.mention} has been banned for {time}!",
                color=discord.Color.red()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            await ctx.send(embed=embed)
        else:
            # Permanent ban
            await send_punishment_dm(member, "Permanent Ban", "Permanent", reason, ctx.author)
            await member.ban(reason=reason)
            await send_to_punishment_channel(ctx.guild, "Permanent Ban", member, ctx.author, "Permanent", reason)
            await log_punishment(ctx.guild, "🔨 Permanent Ban", member, ctx.author, "Permanent", reason)
            
            embed = discord.Embed(
                title="🔨 Permanent Ban",
                description=f"{member.mention} has been banned permanently!",
                color=discord.Color.dark_red()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}", delete_after=5)

@bot.command()
@commands.is_owner()  # Change to @commands.has_permissions(kick_members=True) for moderators
async def kick(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    """
    Kick a member from the server.
    Usage: !kick @user reason
    """
    try:
        await send_punishment_dm(member, "Kick", "N/A", reason, ctx.author)
        await member.kick(reason=reason)
        await send_to_punishment_channel(ctx.guild, "Kick", member, ctx.author, "N/A", reason)
        await log_punishment(ctx.guild, "👢 Kick", member, ctx.author, "N/A", reason)
        
        embed = discord.Embed(
            title="👢 Kick",
            description=f"{member.mention} has been kicked!",
            color=discord.Color.yellow()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}", delete_after=5)

@bot.command()
@commands.is_owner()  # Change to @commands.has_permissions(moderate_members=True) for moderators
async def untimeout(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    """
    Remove timeout from a member.
    Usage: !untimeout @user reason
    """
    try:
        await member.timeout(None, reason=reason)
        embed = discord.Embed(
            title="✅ Timeout Removed",
            description=f"{member.mention} has been untimed out.",
            color=discord.Color.green()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        await ctx.send(embed=embed)
        
        # Log to logs channel
        log_channel = discord.utils.get(ctx.guild.text_channels, name="logs")
        if log_channel:
            log_embed = discord.Embed(
                title="✅ Timeout Removed",
                description=f"{member.mention} was untimed out by {ctx.author.mention}",
                color=discord.Color.green()
            )
            log_embed.add_field(name="Reason", value=reason, inline=False)
            await log_channel.send(embed=log_embed)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}", delete_after=5)

@bot.command()
@commands.is_owner()  # Change to @commands.has_permissions(ban_members=True) for moderators
async def unban(ctx, user_id: int, *, reason: str = "No reason provided."):
    """
    Unban a user by their ID.
    Usage: !unban 123456789 reason
    """
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=reason)
        embed = discord.Embed(
            title="✅ Unban",
            description=f"{user.mention} has been unbanned.",
            color=discord.Color.green()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        await ctx.send(embed=embed)
        
        # Log to logs channel
        log_channel = discord.utils.get(ctx.guild.text_channels, name="logs")
        if log_channel:
            log_embed = discord.Embed(
                title="✅ Unban",
                description=f"{user.mention} was unbanned by {ctx.author.mention}",
                color=discord.Color.green()
            )
            log_embed.add_field(name="Reason", value=reason, inline=False)
            await log_channel.send(embed=log_embed)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}", delete_after=5)

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
