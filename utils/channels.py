import discord
from discord import PermissionOverwrite
from discord.utils import get

user_channel_count = {}  # Global dictionary to track user channel counts

async def create_personal_channel(guild, channel_name, user):
    # Existing logic for channel creation
    overwrites = {
        guild.default_role: PermissionOverwrite(read_messages=False),
        user: PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        guild.me: PermissionOverwrite(read_messages=True)
    }

    category = get(guild.categories, name="╭━━━🖥 Connections 🖥━━━╮")

    if category is None:
        category = await guild.create_category("╭━━━🖥 Connections 🖥━━━╮")

    channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites, category=category)

    # Update channel count
    user_channel_count[user.id] = user_channel_count.get(user.id, 0) + 1

    return channel

async def close_personal_channel(user, channel):
    # Logic to close the channel
    await channel.delete()

    # Update channel count
    if user.id in user_channel_count:
        user_channel_count[user.id] = max(0, user_channel_count[user.id] - 1)

async def create_private_channel(guild, channel_name, user1, user2):
    # Function enhanced for buddy system
    overwrites = {
        guild.default_role: PermissionOverwrite(read_messages=False),
        user1: PermissionOverwrite(read_messages=True, send_messages=True),
        user2: PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: PermissionOverwrite(read_messages=True, send_messages=True)  # bot permissions
    }

    category = get(guild.categories, name="╭━━━🫂 Buddy 🫂━━━╮")
    if category is None:
        category = await guild.create_category("╭━━━🫂 Buddy 🫂━━━╮")

    channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites, category=category)
    return channel

async def delete_private_channel(channel):
    await channel.delete()

async def find_channel_by_name(guild, channel_name):
    for channel in guild.channels:
        if channel.name == channel_name:
            return channel
    return None

async def setup_buddy_channel(guild, channel_name, newbie, buddy):
    # Check roles and create a private channel for buddy and newbie
    newbie_role = get(guild.roles, name="Newbie")
    buddy_role = get(guild.roles, name="Buddy")
    member_role = get(guild.roles, name="Community")
    
    if newbie_role in newbie.roles and buddy_role in buddy.roles:
        # Setup permissions
        overwrites = {
            guild.default_role: PermissionOverwrite(read_messages=False),
            newbie: PermissionOverwrite(read_messages=True, send_messages=True),
            buddy: PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: PermissionOverwrite(read_messages=True, send_messages=True)  # bot permissions
        }
        
        category = get(guild.categories, name="╭━━━🫂 Buddy 🫂━━━╮")
        if category is None:
            category = await guild.create_category("╭━━━🫂 Buddy 🫂━━━╮")
        
        channel_name = f"buddy-{newbie.display_name}-{buddy.display_name}"
        channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites, category=category)
        
        # Update newbie's role to 'member'
        await newbie.add_roles(member_role)
        await newbie.remove_roles(newbie_role)
        
        # Send a confirmation message in the newly created channel
        await channel.send(f"Welcome, {newbie.mention}! We have paired you with {buddy.mention} to help introduce you to the community. This is your temporary private channel to communicate.")

        return channel
    else:
        return None
