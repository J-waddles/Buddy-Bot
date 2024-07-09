import discord
from discord import PermissionOverwrite
from discord.utils import get

user_channel_count = {}  # Global dictionary to track user channel counts

async def setup_buddy_channel(guild, channel_name, newbie, buddy):
    # Check roles and create a private channel for buddy and newbie
    newbie_role = get(guild.roles, name="Newbie")
    buddy_role = get(guild.roles, name="Buddy")
    member_role = get(guild.roles, name="Member")

    existing_category = channel.category
    if not existing_category:
        print("No category found for the channel.")
        return
    
    category_name = existing_category.name

    
    if newbie_role in newbie.roles and buddy_role in buddy.roles:
        # Setup permissions
        overwrites = {
            guild.default_role: PermissionOverwrite(read_messages=False),
            newbie: PermissionOverwrite(read_messages=True, send_messages=True),
            buddy: PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: PermissionOverwrite(read_messages=True, send_messages=True)  # bot permissions
        }
        
        category = get(guild.categories, name=category_name)
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
