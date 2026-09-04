import asyncio
import re
import os
os.system("pip install pynacl")
import sys
import discord
from datetime import timedelta
from discord.ext import commands
from flask import Flask
from threading import Thread
import json
from typing import Optional

# ==========================
# FLASK KEEP-ALIVE
# ==========================
app = Flask('')

@app.route('/')
def home():
    return "ðŸ¤– Bot is alive and running!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
    print(f"ðŸŒ Web server running on port {os.environ.get('PORT', 8080)}")

# ==========================
# BOT SETUP
# ==========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================
# OWNER ID
# ==========================
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

# ðŸ“Š Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø¯Ø¹ÙˆØ§Øª
invite_data = {}

INVITE_REGEX = re.compile(
    r"(https?://)?(www\.)?(discord\.gg|discord\.com/invite|discord\.app/invite)/\S+",
    re.I
)

# ==========================
# READY
# ==========================
@bot.event
async def on_ready():
    print(f"âœ… Logged in as {bot.user}")
    print(f"âœ… Bot is ready!")
    print(f"âœ… Connected to {len(bot.guilds)} guilds")
    print(f"ðŸ‘‘ Owner ID: {bot.owner_id}")
    
    # ðŸ“Š ØªØ­Ù…ÙŠÙ„ Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø¯Ø¹ÙˆØ§Øª
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            for invite in invites:
                if invite.inviter:
                    inviter_id = str(invite.inviter.id)
                    if inviter_id not in invite_data:
                        invite_data[inviter_id] = 0
                    invite_data[inviter_id] += invite.uses
        except:
            pass
    print("ðŸ“Š Invite data loaded!")

# ==========================
# HELLO COMMAND
# ==========================
@bot.command()
@commands.is_owner()
async def hello(ctx):
    await ctx.send(f'ðŸ‘‹ Hello {ctx.author.mention}!')

# ==========================
# WRITE COMMAND
# ==========================
@bot.command()
@commands.is_owner()
async def write(ctx, *, message):
    await ctx.message.delete()
    await ctx.send(message)

# ==========================
# ðŸŽµ Ø£ÙˆØ§Ù…Ø± Ø§Ù„ØµÙˆØª Ø§Ù„Ù…ØªÙƒØ§Ù…Ù„Ø©
# ==========================

# Ù…ØªØºÙŠØ±Ø§Øª Ù„ØªØªØ¨Ø¹ Ø­Ø§Ù„Ø© Ø§Ù„Ø¨ÙˆØª Ø§Ù„ØµÙˆØªÙŠ
last_voice_channel = {}  # {guild_id: channel_id}
manual_leave = set()  # {guild_id} Ù„Ù„ØºØ§Ø¯Ø±ÙŠÙ† ÙŠØ¯ÙˆÙŠØ§Ù‹

@bot.command()
@commands.is_owner()
async def join(ctx):
    """ÙŠØ¯Ø®Ù„ Ø§Ù„Ø¨ÙˆØª Ù„Ù„Ø±ÙˆÙ… Ø§Ù„ØµÙˆØªÙŠ Ø§Ù„Ù„ÙŠ Ø§Ù†Øª ÙÙŠÙ‡"""
    
    if not ctx.author.voice:
        return await ctx.send("âŒ You must be in a voice channel first!")
    
    channel = ctx.author.voice.channel
    
    permissions = channel.permissions_for(ctx.guild.me)
    if not permissions.connect:
        return await ctx.send("âŒ I don't have permission to join that voice channel!")
    if not permissions.speak:
        return await ctx.send("âŒ I don't have permission to speak in that voice channel!")
    
    try:
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
            await ctx.send(f"âœ… Moved to **{channel.name}**")
        else:
            await channel.connect()
            await ctx.send(f"âœ… Joined **{channel.name}**")
        
        last_voice_channel[ctx.guild.id] = channel.id
        
        if ctx.guild.id in manual_leave:
            manual_leave.remove(ctx.guild.id)
            
    except Exception as e:
        await ctx.send(f"âŒ Error: {str(e)}")

@bot.command()
@commands.is_owner()
async def leave(ctx):
    """ÙŠØ®Ø±Ø¬ Ø§Ù„Ø¨ÙˆØª Ù…Ù† Ø§Ù„Ø±ÙˆÙ… Ø§Ù„ØµÙˆØªÙŠ"""
    
    if not ctx.voice_client:
        return await ctx.send("âŒ I'm not in a voice channel!")
    
    manual_leave.add(ctx.guild.id)
    
    try:
        await ctx.voice_client.disconnect()
        await ctx.send("ðŸ‘‹ Left voice channel!")
        
        if ctx.guild.id in last_voice_channel:
            del last_voice_channel[ctx.guild.id]
            
    except Exception as e:
        await ctx.send(f"âŒ Error: {str(e)}")

# ==========================
# Ø¥Ø¹Ø§Ø¯Ø© Ø§Ù„Ø§ØªØµØ§Ù„ Ø§Ù„ØªÙ„Ù‚Ø§Ø¦ÙŠ
# ==========================

@bot.event
async def on_voice_state_update(member, before, after):
    """
    ÙŠØ±Ø§Ù‚Ø¨ Ø­Ø§Ù„Ø© Ø§Ù„Ø¨ÙˆØª Ø§Ù„ØµÙˆØªÙŠ:
    - Ø¥Ø°Ø§ Ø·Ù„Ø¹ Ø¨Ø§Ù„ØºÙ„Ø· (Disconnect) ÙŠØ±Ø¬Ø¹ ØªÙ„Ù‚Ø§Ø¦ÙŠØ§Ù‹
    - Ø¥Ø°Ø§ ØªØ­Ø±Ùƒ Ù„Ø±ÙˆÙ… Ø¢Ø®Ø± ÙŠØªØ§Ø¨Ø¹Ù‡
    """
    
    # Ù†ØªØ¬Ø§ÙˆØ² ÙƒÙ„ Ø§Ù„Ø£Ø¹Ø¶Ø§Ø¡ Ù…Ø§ Ø¹Ø¯Ø§ Ø§Ù„Ø¨ÙˆØª Ù†ÙØ³Ù‡
    if member.id != bot.user.id:
        return
    
    guild = member.guild
    
    # ===== Ø¥Ø°Ø§ Ø¯Ø®Ù„ Ø§Ù„Ø¨ÙˆØª Ù„Ø±ÙˆÙ… =====
    if after.channel:
        last_voice_channel[guild.id] = after.channel.id
        print(f"ðŸ”Š Bot moved to: {after.channel.name}")
        return
    
    # ===== Ø¥Ø°Ø§ Ø·Ù„Ø¹ Ø§Ù„Ø¨ÙˆØª =====
    # Ù†ØªØ­Ù‚Ù‚ Ø¥Ø°Ø§ ÙƒØ§Ù† Ø·Ù„Ø¹ ÙŠØ¯ÙˆÙŠØ§Ù‹ (Ø£Ù…Ø± !leave)
    if guild.id in manual_leave:
        manual_leave.remove(guild.id)
        print("ðŸ‘‹ Bot left manually (via !leave)")
        return
    
    # ===== Ø¥Ø°Ø§ Ø·Ù„Ø¹ Ø¨Ø§Ù„ØºÙ„Ø· (Disconnect) =====
    if before.channel and guild.id in last_voice_channel:
        await asyncio.sleep(3)  # Ù†Ø³ØªÙ†Ù‰ 3 Ø«ÙˆØ§Ù†ÙŠ
        
        try:
            # Ù†ØªØ­Ù‚Ù‚ Ø¥Ø°Ø§ Ø§Ù„Ø¨ÙˆØª Ù„Ø³Ø§ Ø®Ø§Ø±Ø¬
            if guild.voice_client is None:
                # Ù†Ø¬ÙŠØ¨ Ø§Ù„Ø±ÙˆÙ… Ø§Ù„Ù…Ø®Ø²Ù†
                channel = guild.get_channel(last_voice_channel[guild.id])
                
                if channel:
                    # Ù†Ø±Ø¬Ø¹ Ø§Ù„Ø¨ÙˆØª Ù„Ù„Ø±ÙˆÙ…
                    await channel.connect()
                    print(f"ðŸ”„ Bot reconnected to: {channel.name}")
                    
                    # Ù†Ø±Ø³Ù„ Ø±Ø³Ø§Ù„Ø© ÙÙŠ Ø§Ù„Ù€ logs
                    log_channel = discord.utils.get(guild.text_channels, name="logs")
                    if log_channel:
                        await log_channel.send("ðŸ”„ **Bot reconnected automatically!**")
                        
        except Exception as e:
            print(f"âŒ Reconnect error: {e}")

# ==========================
# WARNINGS
# ==========================
@bot.command()
@commands.is_owner()
async def reset_warnings(ctx, member: discord.Member):
    warnings[member.id] = 0
    if member.id in warn_reasons:
        warn_reasons[member.id] = []
    await ctx.send(f"âœ… Warnings reset for {member.mention}.")

@bot.command()
@commands.is_owner()
async def check_warnings(ctx, member: discord.Member):
    await ctx.send(
        f"{member.mention} has **{warnings.get(member.id,0)}/3** warnings."
    )

# ==========================
# BAD WORDS MANAGEMENT
# ==========================
@bot.command()
@commands.is_owner()
async def add_bad_word(ctx, word: str):
    word = word.lower()
    if word not in BAD_WORDS:
        BAD_WORDS.append(word)
    await ctx.send(f"âœ… Added `{word}`")

@bot.command()
@commands.is_owner()
async def remove_bad_word(ctx, word: str):
    word = word.lower()
    if word in BAD_WORDS:
        BAD_WORDS.remove(word)
        await ctx.send(f"âœ… Removed `{word}`")
    else:
        await ctx.send("âŒ Word not found.")

@bot.command()
@commands.is_owner()
async def show_bad_words(ctx):
    if not BAD_WORDS:
        return await ctx.send("No bad words.")
    await ctx.send("\n".join(BAD_WORDS))

# ==========================
# â­ Ø§Ù„Ø£ÙˆØ§Ù…Ø± Ø§Ù„Ø¬Ø¯ÙŠØ¯Ø© â­
# ==========================

# 1ï¸âƒ£ Ø£Ù…Ø± !avatar
@bot.command()
async def avatar(ctx, member: discord.Member = None):
    """ÙŠØ¹Ø±Ø¶ ØµÙˆØ±Ø© Ø§Ù„Ø¨Ø±ÙˆÙØ§ÙŠÙ„ Ù„Ø¹Ø¶Ùˆ"""
    if member is None:
        member = ctx.author
    
    embed = discord.Embed(
        title=f"ðŸ–¼ï¸ {member.display_name}'s Avatar",
        color=discord.Color.blue()
    )
    embed.set_image(url=member.display_avatar.url)
    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    
    await ctx.send(embed=embed)

# 2ï¸âƒ£ Ø£Ù…Ø± !clear
@bot.command()
@commands.is_owner()
async def clear(ctx, amount: int):
    """ÙŠØ­Ø°Ù Ø¹Ø¯Ø¯ Ù…Ø­Ø¯Ø¯ Ù…Ù† Ø§Ù„Ø±Ø³Ø§Ø¦Ù„"""
    if amount < 1:
        return await ctx.send("âŒ Please specify a number greater than 0.")
    
    if amount > 100:
        return await ctx.send("âŒ Cannot delete more than 100 messages at once.")
    
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"âœ… Deleted {len(deleted) - 1} messages.", delete_after=3)

# 3ï¸âƒ£ Ø£Ù…Ø± !warn
@bot.command()
@commands.is_owner()
async def warn(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """ÙŠØ­Ø°Ø± Ø¹Ø¶Ùˆ Ù…Ø¹ Ø³Ø¨Ø¨"""
    warnings[member.id] = warnings.get(member.id, 0) + 1
    
    if member.id not in warn_reasons:
        warn_reasons[member.id] = []
    warn_reasons[member.id].append({
        "reason": reason,
        "by": ctx.author.id,
        "time": ctx.message.created_at.strftime("%Y-%m-%d %H:%M")
    })
    
    try:
        await member.send(f"âš ï¸ You have been warned in **{ctx.guild.name}**\nReason: {reason}\nWarnings: {warnings[member.id]}/3")
    except:
        pass
    
    embed = discord.Embed(
        title="âš ï¸ Warning",
        description=f"{member.mention} has been warned!",
        color=discord.Color.orange()
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Warnings", value=f"{warnings[member.id]}/3", inline=True)
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.set_footer(text=f"ID: {member.id}")
    
    await ctx.send(embed=embed)
    
    if warnings[member.id] >= 3:
        await member.timeout(timedelta(minutes=10), reason="3 warnings")
        await ctx.send(f"ðŸ”‡ {member.mention} has been timed out for 10 minutes (3 warnings).")
        warnings[member.id] = 0

# 4ï¸âƒ£ Ø£Ù…Ø± !warnings
@bot.command()
@commands.is_owner()
async def warnings(ctx, member: discord.Member):
    """ÙŠØ¹Ø±Ø¶ ØªØ­Ø°ÙŠØ±Ø§Øª Ø¹Ø¶Ùˆ Ù…Ø¹ Ø§Ù„Ø£Ø³Ø¨Ø§Ø¨"""
    count = warnings.get(member.id, 0)
    
    embed = discord.Embed(
        title=f"âš ï¸ Warnings for {member.display_name}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Total Warnings", value=f"{count}/3", inline=False)
    
    if member.id in warn_reasons and warn_reasons[member.id]:
        reasons_text = ""
        for i, warn_data in enumerate(warn_reasons[member.id], 1):
            reasons_text += f"**{i}.** {warn_data['reason']} (by <@{warn_data['by']}> at {warn_data['time']})\n"
        embed.add_field(name="Reasons", value=reasons_text, inline=False)
    else:
        embed.add_field(name="Reasons", value="No warnings recorded.", inline=False)
    
    embed.set_footer(text=f"ID: {member.id}")
    
    await ctx.send(embed=embed)

# 5ï¸âƒ£ Ø£Ù…Ø± !clear (Ù†Ø³Ø®Ø© Ø¨Ø¯ÙˆÙ† Admin)
@bot.command()
@commands.is_owner()
async def clear_all(ctx, amount: int):
    """ÙŠØ­Ø°Ù Ø¹Ø¯Ø¯ Ù…Ø­Ø¯Ø¯ Ù…Ù† Ø§Ù„Ø±Ø³Ø§Ø¦Ù„ (Ù†Ø³Ø®Ø© Ø§Ø­ØªÙŠØ§Ø·ÙŠØ©)"""
    if amount < 1:
        return await ctx.send("âŒ Please specify a number greater than 0.")
    if amount > 100:
        return await ctx.send("âŒ Cannot delete more than 100 messages at once.")
    
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"âœ… Deleted {len(deleted)} messages.", delete_after=3)

# ==========================
# â­â­â­ Ø£ÙˆØ§Ù…Ø± DM â­â­â­
# ==========================

# 6ï¸âƒ£ Ø£Ù…Ø± !dm
@bot.command()
@commands.is_owner()
async def dm(ctx, member: discord.Member, *, message: str):
    """ÙŠØ¨Ø¹Ø« Ø±Ø³Ø§Ù„Ø© Ø®Ø§ØµØ© Ù„Ø¹Ø¶Ùˆ ÙˆØ§Ø­Ø¯"""
    try:
        embed = discord.Embed(
            title="ðŸ“© Message from ð™³ðšŽðšŠðšðš‘ ðš†ðš‘ðš’ðšœðš™ðšŽðš› ð™²ðš˜ðš–ðš–ðšžðš—ðš’ðšðš¢",
            description=message,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"from: {ctx.author.display_name} â€¢ {ctx.guild.name}")
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        
        await member.send(embed=embed)
        await ctx.send(f"âœ… The message was sent successfully! **{member.display_name}** ")
    except discord.Forbidden:
        await ctx.send(f"âŒ I can't send a message to**{member.display_name}** (DM locked )")
    except Exception as e:
        await ctx.send(f"âŒerror : {str(e)}")

# 7ï¸âƒ£ Ø£Ù…Ø± !dmrole
@bot.command()
@commands.is_owner()
async def dmrole(ctx, role: discord.Role, *, message: str):
    """ÙŠØ¨Ø¹Ø« Ø±Ø³Ø§Ù„Ø© Ø®Ø§ØµØ© Ù„Ø¬Ù…ÙŠØ¹ Ø£Ø¹Ø¶Ø§Ø¡ Ø¯ÙˆØ± Ù…Ø¹ÙŠÙ†"""
    confirm_msg = await ctx.send(f"âš ï¸ **You are about to send a DM to {len(role.members)} member ** In a role {role.mention}\nmessage : \"{message}\"\n\nReply with **yes** Confirmation or **no** to cancel  (30 S )")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['yes', 'no']
    
    try:
        response = await bot.wait_for('message', timeout=30.0, check=check)
        
        if response.content.lower() == 'no':
            return await ctx.send("âŒCancelled.")
        
        await ctx.send(f"â³Messages are being sent to {len(role.members)} member ...")
        
        success_count = 0
        fail_count = 0
        
        embed = discord.Embed(
            title="ðŸ“¢  Message from ð™³ðšŽðšŠðšðš‘ ðš†ðš‘ðš’ðšœðš™ðšŽðš› ð™²ðš˜ðš–ðš–ðšžðš—ðš’ðšðš¢",
            description=message,
            color=discord.Color.green()
        )
        embed.set_footer(text=f"from: {ctx.author.display_name} â€¢ {ctx.guild.name}")
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        
        for member in role.members:
            if member.bot:
                continue
            try:
                await member.send(embed=embed)
                success_count += 1
                await asyncio.sleep(0.3)
            except:
                fail_count += 1
        
        await ctx.send(f"âœ… **Sent successfully!**\nâœ…succeeded: {success_count}\nâŒ fail: {fail_count}")
        
    except asyncio.TimeoutError:
        await ctx.send("â°Time's up! Cancelled.")

# 8ï¸âƒ£ Ø£Ù…Ø± !dmall
@bot.command()
@commands.is_owner()
async def dmall(ctx, *, message: str):
    """ÙŠØ¨Ø¹Ø« Ø±Ø³Ø§Ù„Ø© Ø®Ø§ØµØ© Ù„Ø¬Ù…ÙŠØ¹ Ø§Ù„Ø£Ø¹Ø¶Ø§Ø¡ (Ø¨Ø§Ø³ØªØ«Ù†Ø§Ø¡ Ø§Ù„Ø¨ÙˆØªØ§Øª)"""
    members = [m for m in ctx.guild.members if not m.bot]
    
    confirm_msg = await ctx.send(f"âš ï¸ **You are about to send a DM to {len(members)} member **\nmessage: \"{message}\"\n\nReply with **yes** To confirm or **no** Cancel (30 S)")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['yes', 'no']
    
    try:
        response = await bot.wait_for('message', timeout=30.0, check=check)
        
        if response.content.lower() == 'no':
            return await ctx.send("âŒ Cancelled.")
        
        await ctx.send(f"â³ Messages are being sent to {len(members)} member ...")
        
        success_count = 0
        fail_count = 0
        
        embed = discord.Embed(
            title="ðŸ“¢  Message from ð™³ðšŽðšŠðšðš‘ ðš†ðš‘ðš’ðšœðš™ðšŽðš› ð™²ðš˜ðš–ðš–ðšžðš—ðš’ðšðš¢",
            description=message,
            color=discord.Color.green()
        )
        embed.set_footer(text=f"from: {ctx.author.display_name} â€¢ {ctx.guild.name}")
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        
        for member in members:
            try:
                await member.send(embed=embed)
                success_count += 1
                await asyncio.sleep(0.3)
            except:
                fail_count += 1
        
        await ctx.send(f"âœ… **Sent successfully!**\nâœ…  succeeded: {success_count}\nâŒfail: {fail_count}")
        
    except asyncio.TimeoutError:
        await ctx.send("â°ime's up! Cancelled.")


# ==========================
# MESSAGE FILTER
# ==========================
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if not message.guild:
        return await bot.process_commands(message)
    if not message.author.guild_permissions.administrator:
        content = message.content.lower()
        if INVITE_REGEX.search(content):
            await message.delete()
            await message.author.timeout(
                timedelta(minutes=1),
                reason="Discord Invite"
            )
            return
        for word in BAD_WORDS:
            if word in content:
                await message.delete()
                warnings[message.author.id] = warnings.get(
                    message.author.id, 0
                ) + 1
                log = discord.utils.get(
                    message.guild.text_channels,
                    name=LOG_CHANNEL_NAME
                )
                if log:
                    await log.send(
                        f"âš ï¸ {message.author.mention} used `{word}` "
                        f"({warnings[message.author.id]}/3)"
                    )
                if warnings[message.author.id] >= 3:
                    await message.author.timeout(
                        timedelta(minutes=10),
                        reason="3 Bad Words"
                    )
                    warnings[message.author.id] = 0
                return
    await bot.process_commands(message)

# ==========================
# ðŸ›ï¸ Ù†Ø¸Ø§Ù… AFK (Self-Deaf)
# ==========================

# Ù…ØªØºÙŠØ±Ø§Øª Ù„ØªØªØ¨Ø¹ Ø§Ù„Ù€ AFK
afk_tracker = {}  # {user_id: {"start_time": timestamp, "message_sent": False, "channel_id": channel_id}}

@bot.event
async def on_voice_state_update(member, before, after):
    """ÙŠÙƒØªØ´Ù Ø§Ù„Ù€ Self-Deaf ÙˆÙŠØ¯ÙŠØ± Ù†Ø¸Ø§Ù… AFK"""
    
    # Ù†ØªØ¬Ø§ÙˆØ² Ø§Ù„Ø¨ÙˆØªØ§Øª
    if member.bot:
        return
    
    # ===== ÙƒØ´Ù Self-Deaf =====
    if after.self_deaf and not before.self_deaf:
        # Ø§Ù„Ø¹Ø¶Ùˆ Ø¹Ù…Ù„ Self-Deaf
        afk_tracker[member.id] = {
            "start_time": discord.utils.utcnow(),
            "message_sent": False,
            "channel_id": after.channel.id if after.channel else None
        }
        print(f"ðŸ”‡ {member.display_name} Ø¹Ù…Ù„ Self-Deaf")
        
        # Ù†Ø¨Ø¯Ø§ Ø§Ù„Ù…Ù‡Ù…Ø© Ù„Ù…Ø±Ø§Ù‚Ø¨Ø© Ø§Ù„ÙˆÙ‚Øª
        asyncio.create_task(afk_monitor(member))
    
    # ===== ÙƒØ´Ù Ø¥Ù„ØºØ§Ø¡ Self-Deaf =====
    elif not after.self_deaf and before.self_deaf:
        # Ø§Ù„Ø¹Ø¶Ùˆ Ø£Ù„ØºÙ‰ Ø§Ù„Ù€ Self-Deaf
        if member.id in afk_tracker:
            del afk_tracker[member.id]
            print(f"ðŸ”Š {member.display_name} cancel Self-Deaf")


async def afk_monitor(member):
    """ØªØ±Ø§Ù‚Ø¨ Ø§Ù„Ø¹Ø¶Ùˆ Ø§Ù„Ù„ÙŠ Ø¹Ù…Ù„ Self-Deaf"""
    
    # Ù†Ø³ØªÙ†Ù‰ 5 Ø¯Ù‚Ø§Ø¦Ù‚ Ø¨Ø§Ø´ Ù†Ø¨Ø¹Ø« Ø§Ù„Ø±Ø³Ø§Ù„Ø©
    await asyncio.sleep(300)  # 5 Ø¯Ù‚Ø§Ø¦Ù‚ = 300 Ø«Ø§Ù†ÙŠØ©
    
    # Ù†ØªØ­Ù‚Ù‚ Ø¥Ø°Ø§ ÙƒØ§Ù† Ø§Ù„Ø¹Ø¶Ùˆ Ù„Ø³Ø§ ÙÙŠ Ø§Ù„Ù€ AFK
    if member.id not in afk_tracker:
        return
    
    # Ù†ØªØ­Ù‚Ù‚ Ø¥Ø°Ø§ ÙƒØ§Ù† Ù„Ø³Ø§ Self-Deaf
    if not member.voice or not member.voice.self_deaf:
        if member.id in afk_tracker:
            del afk_tracker[member.id]
        return
    
    # Ù†Ø¨Ø¹Ø« Ø§Ù„Ø±Ø³Ø§Ù„Ø© (Ù…Ø±Ø© ÙˆØ­Ø¯Ø©)
    if not afk_tracker[member.id]["message_sent"]:
        afk_tracker[member.id]["message_sent"] = True
        
        try:
            # Ù†Ø¨Ø¹Ø« Ø±Ø³Ø§Ù„Ø© Ø®Ø§ØµØ©
            embed = discord.Embed(
                title="ðŸ”‡ alert to AFK",
                description="You are currently **deafened** in **ð™³ðšŽðšŠðšðš‘ ðš†ðš‘ðš’ðšœðš™ðšŽðš› ð™²ðš˜ðš–ðš–ðšžðš—ðš’ðšðš¢**.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="â° alert",
                value="You will be moved to **AFK** after **1 hour** of being deaf.",
                inline=False
            )
            embed.set_footer(text="ðŸ”Š Unmute yourself to cancel AFK")
            
            await member.send(embed=embed)
            print(f"ðŸ“©AFK message sent to{member.display_name}")
            
        except:
            print(f"âŒ i cant send message to {member.display_name} (DM locked)")
    
    # Ù†Ø³ØªÙ†Ù‰ Ø³Ø§Ø¹Ø© ÙƒØ§Ù…Ù„Ø© (3600 Ø«Ø§Ù†ÙŠØ©) Ø¨Ø§Ø´ Ù†Ø­Ø±Ùƒ
    await asyncio.sleep(3600)  # Ø³Ø§Ø¹Ø© = 3600 Ø«Ø§Ù†ÙŠØ©
    
    # Ù†ØªØ­Ù‚Ù‚ Ù…Ø±Ø© Ø£Ø®Ø±Ù‰
    if member.id not in afk_tracker:
        return
    
    if not member.voice or not member.voice.self_deaf:
        if member.id in afk_tracker:
            del afk_tracker[member.id]
        return
    
    # ===== Ù†Ø­Ø±Ùƒ Ø§Ù„Ø¹Ø¶Ùˆ Ù„Ø±ÙˆÙ… AFK =====
    try:
        # Ù†Ø¬ÙŠØ¨ Ø§Ù„Ø±ÙˆÙ… AFK
        afk_channel = discord.utils.get(member.guild.voice_channels, name="â”œðŸ˜´ãƒ»ð™°ðšðš”")
        
        if afk_channel is None:
            print("âŒ Ø±ÙˆÙ… AFK Ù…Ø´ Ù…ÙˆØ¬ÙˆØ¯!")
            # Ù†Ø¹Ù…Ù„ Ø±ÙˆÙ… Ø¥Ø°Ø§ Ù…Ø´ Ù…ÙˆØ¬ÙˆØ¯
            afk_channel = await member.guild.create_voice_channel(
                name="â”œðŸ˜´ãƒ»ð™°ðšðš”",
                reason="ØªÙ… Ø¥Ù†Ø´Ø§Ø¡ Ø±ÙˆÙ… AFK ØªÙ„Ù‚Ø§Ø¦ÙŠØ§Ù‹"
            )
            print("âœ… ØªÙ… Ø¥Ù†Ø´Ø§Ø¡ Ø±ÙˆÙ… AFK")
        
        # Ù†Ø­Ø±Ùƒ Ø§Ù„Ø¹Ø¶Ùˆ
        await member.move_to(afk_channel, reason="Self-Deaf For one hour ")
        print(f"ðŸš€{member.display_name} has been moved to afk ")
        
        # Ù†Ø±Ø³Ù„ Ø±Ø³Ø§Ù„Ø© ÙÙŠ Ø§Ù„Ø´Ø§Øª
        channel = discord.utils.get(member.guild.text_channels, name="logs")
        if channel is None:
            channel = member.guild.system_channel
        
        if channel:
            await channel.send(f"ðŸ”‡ {member.mention} He was transferred to **AFK** one hour after the Self-Deaf.")
        
        # Ù†Ø­Ø°Ù Ù…Ù† Ø§Ù„ØªØ±Ø§ÙƒØ±
        if member.id in afk_tracker:
            del afk_tracker[member.id]
            
    except Exception as e:
        print(f"âŒ Organ transfer error: {e}")


# ==========================
# ðŸ“Š LEADERBOARD (Ù„Ù„ÙƒÙ„) - Ø§Ù„Ù†Ø³Ø®Ø© Ø§Ù„Ù…ØªØ·ÙˆØ±Ø©
# ==========================

# Ù…ØªØºÙŠØ±Ø§Øª Ù„ØªØªØ¨Ø¹ Ø§Ù„Ø¯Ø¹ÙˆØ§Øª
invite_data = {}  # {user_id: invites_count}
invite_cache = {}  # {guild_id: {invite_code: invite_object}}

@bot.event
async def on_ready():
    print(f"âœ… Logged in as {bot.user}")
    print(f"âœ… Bot is ready!")
    print(f"âœ… Connected to {len(bot.guilds)} guilds")
    print(f"ðŸ‘‘ Owner ID: {bot.owner_id}")
    
    # ðŸ“Š ØªØ­Ù…ÙŠÙ„ Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø¯Ø¹ÙˆØ§Øª
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            # Ù†Ø®Ø²Ù† Ø§Ù„Ø¯Ø¹ÙˆØ§Øª ÙÙŠ Ø§Ù„ÙƒØ§Ø´
            invite_cache[guild.id] = {}
            for invite in invites:
                invite_cache[guild.id][invite.code] = invite
                
                # Ù†Ø®Ø²Ù† Ø¹Ø¯Ø¯ Ø§Ù„Ø¯Ø¹ÙˆØ§Øª Ù„ÙƒÙ„ Ø¹Ø¶Ùˆ
                if invite.inviter:
                    inviter_id = str(invite.inviter.id)
                    if inviter_id not in invite_data:
                        invite_data[inviter_id] = 0
                    invite_data[inviter_id] += invite.uses
        except Exception as e:
            print(f"âŒ Error loading invitations: {e}")
    print("ðŸ“Š Invite data loaded!")

@bot.event
async def on_member_join(member):
    """ØªØ­Ø¯ÙŠØ« Ø§Ù„Ø¯Ø¹ÙˆØ§Øª Ø¹Ù†Ø¯ Ø¯Ø®ÙˆÙ„ Ø¹Ø¶Ùˆ Ø¬Ø¯ÙŠØ¯"""
    
    guild = member.guild
    
    # Ù†ØªØ¬Ø§ÙˆØ² Ø§Ù„Ø¨ÙˆØªØ§Øª
    if member.bot:
        return
    
    try:
        # Ù†Ø¬ÙŠØ¨ Ø§Ù„Ø¯Ø¹ÙˆØ§Øª Ø§Ù„Ø¬Ø¯ÙŠØ¯Ø©
        new_invites = await guild.invites()
        
        # Ù†Ù‚Ø§Ø±Ù† Ù…Ø¹ Ø§Ù„Ø¯Ø¹ÙˆØ§Øª Ø§Ù„Ù‚Ø¯ÙŠÙ…Ø©
        for invite in new_invites:
            # Ù†Ø¨Ø­Ø« Ø¹Ù† Ø§Ù„Ø¯Ø¹ÙˆØ© Ø§Ù„Ù„ÙŠ Ø²Ø§Ø¯ ÙÙŠÙ‡Ø§ Ø§Ù„Ø¹Ø¯Ø¯
            old_invite = invite_cache.get(guild.id, {}).get(invite.code)
            
            if old_invite:
                # Ø¥Ø°Ø§ Ø²Ø§Ø¯ Ø¹Ø¯Ø¯ Ø§Ù„Ø¯Ø¹ÙˆØ§Øª
                if invite.uses > old_invite.uses:
                    inviter = invite.inviter
                    if inviter and not inviter.bot:
                        # Ù†Ø²ÙŠØ¯ Ø¹Ø¯Ø¯ Ø§Ù„Ø¯Ø¹ÙˆØ§Øª Ù„Ù„Ø¯Ø§Ø¹ÙŠ
                        inviter_id = str(inviter.id)
                        invite_data[inviter_id] = invite_data.get(inviter_id, 0) + 1
                        print(f"âœ… {inviter.display_name} invite {member.display_name}")
                        
                        # Ù†Ø¨Ø¹Ø« Ø±Ø³Ø§Ù„Ø© Ù„Ù„Ø¯Ø§Ø¹ÙŠ
                        try:
                            await inviter.send(f"ðŸŽ‰ {member.display_name} You entered the server with your invitation! Your current number of invitations: {invite_data[inviter_id]}")
                        except:
                            pass
                        break
        
        # Ù†Ø­Ø¯Ø« Ø§Ù„ÙƒØ§Ø´
        for invite in new_invites:
            invite_cache[guild.id][invite.code] = invite
            
    except Exception as e:
        print(f"âŒ Ø®Ø·Ø£ ÙÙŠ ØªØ­Ø¯ÙŠØ« Ø§Ù„Ø¯Ø¹ÙˆØ§Øª: {e}")

@bot.command()  # Ù„Ù„ÙƒÙ„
async def leaderboard(ctx):
    """ÙŠØ¹Ø±Ø¶ ØªØ±ØªÙŠØ¨ Ø§Ù„Ø£Ø¹Ø¶Ø§Ø¡ Ø­Ø³Ø¨ Ø¹Ø¯Ø¯ Ø§Ù„Ø¯Ø¹ÙˆØ§Øª (Ù„Ù„Ø¬Ù…ÙŠØ¹)"""
    
    if not invite_data:
        return await ctx.send("ðŸ“Š No invites found! Start inviting people!")
    
    # Ù†Ø±ØªØ¨ Ø§Ù„Ø¯Ø¹ÙˆØ§Øª Ù…Ù† Ø§Ù„Ø£ÙƒØ¨Ø± Ù„Ù„Ø£ØµØºØ±
    sorted_invites = sorted(invite_data.items(), key=lambda x: x[1], reverse=True)
    
    # Ù†Ø§Ø®Ø° Ø§Ù„Ù€ Top 10
    top_10 = sorted_invites[:10]
    
    embed = discord.Embed(
        title="ðŸ† Leaderboard - Invites",
        description="Top 10 Invited Members",
        color=discord.Color.gold()
    )
    
    description = ""
    for i, (user_id, count) in enumerate(top_10, 1):
        try:
            user = await bot.fetch_user(int(user_id))
            name = user.display_name
        except:
            name = f"Unknown User"
        
        if i == 1:
            medal = "ðŸ¥‡"
        elif i == 2:
            medal = "ðŸ¥ˆ"
        elif i == 3:
            medal = "ðŸ¥‰"
        else:
            medal = f"#{i}"
        
        description += f"{medal} **{name}** â†’ `{count}` invites\n"
    
    embed.description = description
    embed.set_footer(text=f"Requested by: {ctx.author.display_name}")
    embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
    
    await ctx.send(embed=embed)

# ==========================
# Ø£ÙˆØ§Ù…Ø± Ø¥Ø¶Ø§ÙÙŠØ© Ù„Ù„Ø¯Ø¹ÙˆØ§Øª
# ==========================

@bot.command()
async def invites(ctx, member: discord.Member = None):
    """ÙŠØ¹Ø±Ø¶ Ø¹Ø¯Ø¯ Ø¯Ø¹ÙˆØ§Øª Ø¹Ø¶Ùˆ Ù…Ø¹ÙŠÙ†"""
    
    if member is None:
        member = ctx.author
    
    count = invite_data.get(str(member.id), 0)
    
    embed = discord.Embed(
        title="ðŸ“Š Invites",
        description=f"{member.mention} has **{count}** invites!",
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Requested by: {ctx.author.display_name}")
    embed.set_thumbnail(url=member.display_avatar.url)
    
    await ctx.send(embed=embed)

@bot.command()
@commands.is_owner()
async def reset_invites(ctx, member: discord.Member = None):
    """ÙŠØ¹ÙŠØ¯ Ø¶Ø¨Ø· Ø¯Ø¹ÙˆØ§Øª Ø¹Ø¶Ùˆ (Ù„Ù„Ù€ Owner ÙÙ‚Ø·)"""
    
    if member is None:
        return await ctx.send("âŒ identif the member: `!reset_invites @user`")
    
    invite_data[str(member.id)] = 0
    await ctx.send(f"âœ…The invitations have been reset {member.mention}")

@bot.command()
@commands.is_owner()
async def set_invites(ctx, member: discord.Member, count: int):
    """ÙŠØ­Ø¯Ø¯ Ø¹Ø¯Ø¯ Ø¯Ø¹ÙˆØ§Øª Ø¹Ø¶Ùˆ (Ù„Ù„Ù€ Owner ÙÙ‚Ø·)"""
    
    if count < 0:
        return await ctx.send("âŒ The number must be positive!")
    
    invite_data[str(member.id)] = count
    await ctx.send(f"âœ… The invitations have been {member.mention} to `{count}`")

# ==========================
# ðŸ“¦ Ø£Ù…Ø± !embed (Ø§Ù„Ù†Ø³Ø®Ø© Ø§Ù„ÙƒØ§Ù…Ù„Ø©)
# ==========================

@bot.command()
@commands.is_owner()
async def embed(ctx, *, message: str):
    """
    ÙŠØ¨Ø¹Ø« Ø±Ø³Ø§Ù„Ø© ÙÙŠ Embed Ù…Ø¹ Ø¥Ø·Ø§Ø± Ø¬Ù…ÙŠÙ„
    Ø§Ø³ØªØ¹Ù…Ù„: !embed Ù†Øµ Ø§Ù„Ø±Ø³Ø§Ù„Ø©
    """
    
    # Ù†Ù‚Ø³Ù… Ø§Ù„Ø±Ø³Ø§Ù„Ø© Ø¥Ù„Ù‰ Ø¹Ù†ÙˆØ§Ù† ÙˆÙˆØµÙ Ø¥Ø°Ø§ ÙƒØ§Ù†Øª ØªØ­ØªÙˆÙŠ Ø¹Ù„Ù‰ "|"
    if "|" in message:
        parts = message.split("|", 1)
        title = parts[0].strip()
        description = parts[1].strip()
    else:
        title = None
        description = message
    
    # Ù†Ø¹Ù…Ù„ Embed
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue()
    )
    
    # Ù†Ø¶ÙŠÙ Ù…Ø¹Ù„ÙˆÙ…Ø§Øª Ø¥Ø¶Ø§ÙÙŠØ©
    embed.set_footer(
        text=f"ðŸ“ from: {ctx.author.display_name}",
        icon_url=ctx.author.display_avatar.url
    )
    
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    
    embed.timestamp = discord.utils.utcnow()
    
    # Ù†Ø­Ø°Ù Ø±Ø³Ø§Ù„Ø© Ø§Ù„Ù…Ø³ØªØ®Ø¯Ù…
    await ctx.message.delete()
    
    # Ù†Ø¨Ø¹Ø« Ø§Ù„Ù€ Embed
    await ctx.send(embed=embed)
# ==========================
# 8ï¸âƒ£ Ø£Ù…Ø± !lock (ÙŠÙ‚ÙÙ„ Ø§Ù„Ø´Ø§Øª)
# ==========================
@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    """ÙŠÙ‚ÙÙ„ Ø§Ù„Ø´Ø§Øª (ÙŠÙ…Ù†Ø¹ Ø§Ù„Ø£Ø¹Ø¶Ø§Ø¡ Ù…Ù† Ø§Ù„ÙƒØªØ§Ø¨Ø©)"""
    
    channel = ctx.channel
    
    # Ù†Ø¬ÙŠØ¨ ØµÙ„Ø§Ø­ÙŠØ§Øª @everyone
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    
    try:
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"ðŸ”’ **{channel.mention} has been locked!**")
    except:
        await ctx.send("âŒ I don't have permission to lock this channel!")

# ==========================
# 9ï¸âƒ£ Ø£Ù…Ø± !unlock (ÙŠÙØªØ­ Ø§Ù„Ø´Ø§Øª)
# ==========================
@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    """ÙŠÙØªØ­ Ø§Ù„Ø´Ø§Øª (ÙŠØ³Ù…Ø­ Ù„Ù„Ø£Ø¹Ø¶Ø§Ø¡ Ø¨Ø§Ù„ÙƒØªØ§Ø¨Ø©)"""
    
    channel = ctx.channel
    
    # Ù†Ø¬ÙŠØ¨ ØµÙ„Ø§Ø­ÙŠØ§Øª @everyone
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None  # Ù†Ø±Ø¬Ø¹Ù‡Ø§ Ù„Ù„ÙˆØ¶Ø¹ Ø§Ù„Ø§ÙØªØ±Ø§Ø¶ÙŠ
    
    try:
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"ðŸ”“ **{channel.mention} has been unlocked!**")
    except:
        await ctx.send("âŒ I don't have permission to unlock this channel!")
# ==========================
# ðŸš€ Ø£ÙˆØ§Ù…Ø± Ø§Ù„Ù…Ø¹Ù„ÙˆÙ…Ø§Øª (Ù…Ø¶Ø§ÙØ©)
# ==========================

@bot.command()
async def serverinfo(ctx):
    """ÙŠØ¹Ø±Ø¶ Ù…Ø¹Ù„ÙˆÙ…Ø§Øª Ø¹Ù† Ø§Ù„Ø³ÙŠØ±ÙØ±"""
    
    guild = ctx.guild
    
    total_members = guild.member_count
    humans = len([m for m in guild.members if not m.bot])
    bots = total_members - humans
    
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    categories = len(guild.categories)
    total_roles = len(guild.roles)
    
    embed = discord.Embed(
        title=f"ðŸ“Š Server Info - {guild.name}",
        color=discord.Color.blue()
    )
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.add_field(name="ðŸ‘‘ Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="ðŸ†” ID", value=guild.id, inline=True)
    embed.add_field(name="ðŸ“… Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="ðŸ‘¥ Members", value=f"{total_members} (ðŸ‘¤{humans} ðŸ¤–{bots})", inline=True)
    embed.add_field(name="ðŸ’¬ Channels", value=f"ðŸ“{text_channels} ðŸ”Š{voice_channels} ðŸ“{categories}", inline=True)
    embed.add_field(name="ðŸŽ­ Roles", value=total_roles, inline=True)
    embed.add_field(name="ðŸ”— Boost Level", value=guild.premium_tier, inline=True)
    embed.add_field(name="â­ Boost Count", value=guild.premium_subscription_count, inline=True)
    
    if guild.vanity_url:
        embed.add_field(name="ðŸ”— Vanity URL", value=guild.vanity_url, inline=False)
    
    embed.set_footer(text=f"Requested by: {ctx.author.display_name}")
    
    await ctx.send(embed=embed)

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    """ÙŠØ¹Ø±Ø¶ Ù…Ø¹Ù„ÙˆÙ…Ø§Øª Ø¹Ù† Ø¹Ø¶Ùˆ"""
    
    if member is None:
        member = ctx.author
    
    roles = [r.mention for r in member.roles if r != ctx.guild.default_role]
    roles_text = ", ".join(roles) if roles else "No roles"
    
    embed = discord.Embed(
        title=f"ðŸ‘¤ User Info - {member.display_name}",
        color=member.color if member.color != discord.Color.default() else discord.Color.blue()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    
    embed.add_field(name="ðŸ†” ID", value=member.id, inline=True)
    embed.add_field(name="ðŸ“› Name", value=member.name, inline=True)
    embed.add_field(name="ðŸŽ­ Nickname", value=member.nick if member.nick else "None", inline=True)
    embed.add_field(name="ðŸ“… Joined", value=member.joined_at.strftime("%Y-%m-%d %H:%M"), inline=True)
    embed.add_field(name="ðŸ“… Created", value=member.created_at.strftime("%Y-%m-%d %H:%M"), inline=True)
    embed.add_field(name="ðŸŽ­ Roles", value=roles_text, inline=False)
    embed.add_field(name="ðŸ¤– Bot", value="Yes" if member.bot else "No", inline=True)
    embed.add_field(name="ðŸ”Š In Voice", value="Yes" if member.voice else "No", inline=True)
    
    embed.set_footer(text=f"Requested by: {ctx.author.display_name}")
    
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    """ÙŠØ¹Ø±Ø¶ Ø³Ø±Ø¹Ø© Ø§Ø³ØªØ¬Ø§Ø¨Ø© Ø§Ù„Ø¨ÙˆØª"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"ðŸ“ Pong! `{latency}ms`")
# ==========================
# RUN BOT
# ==========================
TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN is None:
    print("âŒ Error: DISCORD_TOKEN not found!")
    sys.exit(1)

print("ðŸš€ Starting bot...")
keep_alive()
print("ðŸ¤– Bot is starting...")
try:
    bot.run(TOKEN)
except Exception as e:
    print(f"âŒ Bot error: {e}")
    sys.exit(1)
