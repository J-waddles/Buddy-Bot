import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal
import json
import os
from discord import Embed
import re  # Regular expressions module
from utils import channels
import functions

CHANNEL_LIMIT = 7  # Maximum number of private channels a user can create
# import asyncio

from utils.queue import (enqueue_user, dequeue_user, is_pair_available, get_next_pair, 
                         add_request, is_request_pending, get_requester, remove_request)
from utils.roles import add_role_to_user, remove_role_from_user
from utils.channels import create_private_channel, delete_private_channel, find_channel_by_name, user_channel_count, create_personal_channel, close_personal_channel


# Define Intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

admin_channel_id = None
connection_channel_id = None 

# Load the env
if os.getenv("token"):
    # Load configuration from environment variables
    TOKEN = os.environ.get("token")
    PREFIX = os.environ.get("PREFIX", "/")  # The "!" is a default value in case PREFIX is not set
    
    # Initialize the bot
    bot = commands.Bot(command_prefix=PREFIX, intents=intents)

else:
    # Load the config file for Test Bot
    with open('config.json', 'r') as f:
        config = json.load(f)

    # Initialize the Test Bot
    bot = commands.Bot(command_prefix=config['prefix'], intents=intents)


@bot.command()
@commands.has_permissions(administrator=True)
async def startnetworking(ctx):
    global admin_channel_id
    admin_channel_id = ctx.channel.id
    await ctx.send(f"Networking bot initiated in this channel: {ctx.channel.name}")

@bot.command()
@commands.has_permissions(administrator=True)
async def viewconnections(ctx):
    global connection_channel_id
    connection_channel_id = ctx.channel.id
    await ctx.send(f"Set the connection view channel to {ctx.channel.mention}.")

##Close all ON channels at once

## Close channel of connect
@bot.command(name="disconnect")
async def disconnect(ctx):
    user = ctx.author
    guild = ctx.guild
    channel = ctx.channel


    # Check if command is invoked in the bot's designated channel or a networking channel
    # Change bot channel
    if ctx.channel.name != "on-" not in ctx.channel.name:
        await ctx.send("This command can only be used in the designated bot channel or your current networking channel.")
        return
    

    # Remove roles (if any)
    await remove_role_from_user(user, "Connected", guild)

    # Delete the private channel
    if "on-" in channel.name:
        await ctx.send("You've been disconnected.")
        await delete_private_channel(channel)
    
    else:
        await ctx.send("You're not in a networking channel.")

        
