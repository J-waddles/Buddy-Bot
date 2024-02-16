import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal
import json
import os
from discord import Embed
import re  # Regular expressions module
from utils import channels
import functions
from pymongo import MongoClient, ReturnDocument
from pymongo.server_api import ServerApi
from bson import ObjectId


from utils.queue import (enqueue_user, dequeue_user, is_pair_available, get_next_pair, 
                         add_request, is_request_pending, get_requester, remove_request)
from utils.roles import add_role_to_user, remove_role_from_user
from utils.channels import create_private_channel, delete_private_channel, find_channel_by_name, user_channel_count, create_personal_channel, close_personal_channel, setup_buddy_channel



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
    MONGO_URI = os.getenv('MONGO_URI')
    
    client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)
        # Initialize the Test Bot
    bot = commands.Bot(command_prefix=PREFIX, intents=intents)  
    db = client['BuddyBotDB']  # Database name
    requests_col = db['requests']

else:
    # Load the config file for Test Bot
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    MONGO_URI = config.get('mongo_uri')
    client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)
        # Initialize the Test Bot
    bot = commands.Bot(command_prefix=config['prefix'], intents=intents)
    db = client['BuddyBotDB']  # Database name
    requests_col = db['requests']
    # Send a ping to confirm a successful connection

# The view for users to request buddy
class BuddyRequestView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Buddy", style=discord.ButtonStyle.green, custom_id="request_buddy")
    async def request_buddy(self, button: discord.ui.Button,  interaction: discord.Interaction):
        user= interaction.user
        # Check for existing request
        if requests_col.find_one({"user_id": user.id}):
            embed = Embed(
                        title="NO double dipping!",
                        description="You have already requested, Thank you for waiting!",
                        color=0xdeffee  
                    )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        # Insert new buddy request
        requests_col.insert_one({"user_id": user.id, "status": "open"})
        print(user.id)
        embed = Embed(
                        title="Success!",
                        description="Please wait while we accept your request!",
                        color=0xdeffee  
                    )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        settings = db['settings'].find_one()
        acceptance_channel_id = settings.get('acceptance_channel_id', None)
        
        if acceptance_channel_id:
            channel = bot.get_channel(int(acceptance_channel_id))
            if channel:
                view = BuddyAcceptView(user.id)  # Assuming this view handles accepting the buddy request
                # Post a message in the designated channel for a trusted member to accept the request
                await channel.send(f"New buddy request from <@{user.id}>. Click to accept.", view=view)
               
            else:
                await interaction.response.send_message("The buddy acceptance channel has not been set correctly. Please contact an admin.", ephemeral=True)
        else:
            await interaction.response.send_message("The buddy acceptance channel has not been set. Please contact an admin.", ephemeral=True)
    
    @discord.ui.button(label="Leave Request", style=discord.ButtonStyle.danger, custom_id="leave_request")
    async def leave_request(self, button: discord.ui.Button, interaction: discord.Interaction):
        user= interaction.user
        # Attempt to remove the buddy request from the database
        result = requests_col.delete_one({"user_id": user.id, "status": "open"})
        if result.deleted_count > 0:
            await interaction.response.send_message("Your buddy request has been successfully canceled.", ephemeral=True)
            # Optionally, disable the request button if the leave request was successful
            # self.children[0].disabled = True  # Assuming the Request Buddy button is the first child
            await interaction.message.edit(view=self)
        else:
            await interaction.response.send_message("You don't have an open buddy request to cancel.", ephemeral=True)


@bot.slash_command(name="request_buddy", description="Request to be paired with a buddy.")
@commands.has_permissions(administrator=True)
async def request_buddy(ctx):
    embed = Embed(
        title="Request Buddy",
        description="Welcome to our community! \nWe hope to accommodate you with a personal buddy to help you out. \nPlease request a buddy and someone will join you shortly.",
        color=0xdeffee
    )
    view = BuddyRequestView()
    await ctx.respond(embed=embed, view=view)   

async def handle_buddy_request(user_id: str):
    # Insert the buddy request into the database
    request_id = requests_col.insert_one({"user_id": user_id, "status": "open"}).inserted_id
    
    # Fetch the designated channel ID for buddy requests
    settings = db['settings'].find_one()
    acceptance_channel_id = settings.get('buddy_acceptance_channel_id')
    
    if acceptance_channel_id:
        channel = bot.get_channel(int(acceptance_channel_id))
        if channel:
            view = BuddyAcceptView(request_id=str(request_id))
            await channel.send(f"New buddy request from <@{user_id}>. Click to accept.", view=view)

class BuddyAcceptView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__()
        self.request_id = user_id

    async def disable_buttons(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    @discord.ui.button(label="Accept Buddy", style=discord.ButtonStyle.green, custom_id="accept_buddy")
    async def accept_buddy(self, button: discord.ui.Button,interaction: discord.Interaction):
        # Convert request_id to ObjectId
        request_id = self.request_id
        
        # Step 1: Manually verify the request status
        request = requests_col.find_one({"user_id": request_id})
        if not request:
            await interaction.response.send_message("This buddy request does not exist.", ephemeral=True)
            return
        
        if request.get("status") == "accepted":
            await interaction.response.send_message("This buddy request has already been accepted.", ephemeral=True)
            return

        # Step 2: Attempt to update the buddy request status if it's open
        update_result = requests_col.update_one(
            {"user_id": request_id, "status": "open"},
            {"$set": {"status": "accepted"}}
        )

        if update_result.modified_count == 1:
            await self.disable_buttons()
            await interaction.response.edit_message(content="You have successfully accepted the buddy request.", view=self)
            # Fetch the Member objects for both the requester and the accepter
            guild = interaction.guild
            requester = guild.get_member(int(request['user_id']))
            accepter = interaction.user  # The user who clicked the accept button

            # Create a private channel for them to communicate
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                requester: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                accepter: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            channel_name = f"buddy-{requester.display_name}-{accepter.display_name}"

            await setup_buddy_channel(guild, channel_name, requester, accepter)
            
        else:
            await interaction.response.send_message("Failed to accept the buddy request. It might have already been accepted.", ephemeral=True)
    
@bot.command(name='sac')
@commands.has_permissions(administrator=True)
async def set_acceptance_channel(ctx):
    # Update the settings collection with the new acceptance channel ID
    settings_col = db['settings']
    settings_col.update_one({}, {'$set': {'acceptance_channel_id': ctx.channel.id}}, upsert=True)
    await ctx.send(f"Channel {ctx.channel.mention} is now set as the buddy acceptance channel.")

    # Fetch all unaccepted buddy requests from the database
    unaccepted_requests = requests_col.find({"status": "open"})

    # Post a BuddyAcceptView for each unaccepted request in the newly set channel
    for user in unaccepted_requests:
        view = BuddyAcceptView(user_id=str(user['_id']))
        await ctx.channel.send(f"New buddy request from <@{user['user_id']}>. Click to accept.", view=view)

@bot.command(name="disconnect")
async def disconnect(ctx):
    channel = ctx.channel
    await delete_private_channel(channel)

@bot.event
async def on_request_buddy(interaction: discord.Interaction, user_id: str):
    # This needs to be triggered when a buddy request is made
    settings = db['settings'].find_one()
    acceptance_channel_id = settings.get('acceptance_channel_id') if settings else None

    if acceptance_channel_id:
        channel = bot.get_channel(int(acceptance_channel_id))
        request_id = requests_col.insert_one({"user_id": user_id, "status": "open"}).inserted_id
        view = BuddyAcceptView(request_id=str(request_id))
        await channel.send(f"New buddy request from <@{user_id}>.", view=view)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}!')

# Run the bot
if os.getenv("token"):
    bot.run(TOKEN)

# a seperate token to test without needing to upload
else:
    bot.run(config['testToken'])