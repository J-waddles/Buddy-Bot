import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal
import json
import os
from discord import Embed, app_commands
import mysql.connector


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
if os.getenv("TOKEN"):
    # Load configuration from environment variables
    TOKEN = os.environ.get("TOKEN")
    PREFIX = os.environ.get("PREFIX", "!")  # The "!" is a default value in case PREFIX is not set
    try:
        mydb = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DB"),
            port=os.getenv("PORT")
        )
        print("You successfully connected to MySQL!")
    except mysql.connector.Error as e:
        print(f"Error connecting to MySQL: {e}")
    
    bot = commands.Bot(command_prefix=PREFIX, intents=intents)

else:
    # Load the config file for Test Bot
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    try:
        mydb = mysql.connector.connect(
            host=config["MYSQL_HOST"],
            user=config["MYSQL_USER"],
            password=config["MYSQL_PASSWORD"],
            database=config["MYSQL_DB"],
            port=config["PORT"]
        )
        print("You successfully connected to MySQL!")
    except mysql.connector.Error as e:
        print(f"Error connecting to MySQL: {e}")
    
    bot = commands.Bot(command_prefix=config['prefix'], intents=intents)

mycursor = mydb.cursor(buffered=True)

# The view for users to request buddy
class BuddyRequestView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.custom_id = 'buddy_request_view'  # Assign a custom ID to the view

    @discord.ui.button(label="Request Buddy", style=discord.ButtonStyle.green, custom_id="request_buddy")
    async def request_buddy(self,  interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)  # Assuming guild-specific buddy requests

        # Check for existing request
        mycursor.execute("SELECT * FROM BuddyRequests WHERE user_id = %s AND guild_id = %s AND (status = 'open' OR status = 'accepted')", (user_id, guild_id))
        existing_request = mycursor.fetchone()
        if existing_request:
            embed = Embed(
                        title="NO double dipping!",
                        description="You have already requested, Thank you for waiting!",
                        color=0xdeffee  
                    )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        # Insert new buddy request
        mycursor.execute("INSERT INTO BuddyRequests (user_id, guild_id, status) VALUES (%s, %s, 'open')", (user_id, guild_id))
        mydb.commit()
        #Debugging
        print(user_id)

        embed = Embed(
                        title="Success!",
                        description="Please wait while we accept your request!",
                        color=0xdeffee  
                    )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Fetch acceptance channel ID from settings
        mycursor.execute("SELECT acceptance_channel_id FROM GuildSettings WHERE guild_id = %s", (guild_id,))
        settings = mycursor.fetchone()
        acceptance_channel_id = settings[0] if settings else None
        
        if acceptance_channel_id:
            channel = interaction.guild.get_channel(int(acceptance_channel_id))
            if channel:
                view = BuddyAcceptView(user_id)  # Assuming this view handles accepting the buddy request
                # Post a message in the designated channel for a trusted member to accept the request
                await channel.send(f"New buddy request from <@{user_id}>. Click to accept.", view=view)
               
            else:
                await interaction.response.send_message("The buddy acceptance channel has not been set correctly. Please contact an admin.", ephemeral=True)
        else:
            await interaction.response.send_message("The buddy acceptance channel has not been set. Please contact an admin.", ephemeral=True)
    
    @discord.ui.button(label="Leave Request", style=discord.ButtonStyle.danger, custom_id="leave_request")
    async def leave_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id
        )

        # Attempt to remove the buddy request from the database
        mycursor.execute("DELETE FROM BuddyRequests WHERE user_id = %s AND guild_id = %s AND (status = 'open' OR status = 'accepted')", (user_id, guild_id))
        deleted_count = mycursor.rowcount
        mydb.commit()
        if deleted_count > 0:
            await interaction.response.send_message("Your buddy request has been successfully cancelled.", ephemeral=True)
            
            await interaction.message.edit(view=self)
        else:
            await interaction.response.send_message("You don't have an open buddy request to cancel.", ephemeral=True)


@bot.tree.command(name="request_buddy", description="Request to be paired with a buddy.")
@commands.has_permissions(administrator=True)
async def request_buddy(interaction: discord.Interaction):
    embed = Embed(
        title="Request Buddy",
        description="Welcome to our community! \nWe hope to accommodate you with a personal buddy to help you out. \nPlease request a buddy and someone will join you shortly.",
        color=0xdeffee
    )
    view = BuddyRequestView()
    await interaction.response.send_message(embed=embed, view=view)
    store_view_info(interaction.guild.id, interaction.channel.id, view.custom_id)   

async def handle_buddy_request(guild_id: str, user_id: str):
    # Convert IDs to strings for consistency
    guild_id_str = str(guild_id)
    user_id_str = str(user_id)

    # Insert the buddy request into the MySQL database
    sql_insert = "INSERT INTO BuddyRequests (guild_id, user_id, status) VALUES (%s, %s, 'open')"
    val_insert = (guild_id_str, user_id_str)
    mycursor.execute(sql_insert, val_insert)
    mydb.commit()
    user_id = mycursor.lastrowid  # Get the last inserted ID
    
    # Fetch the designated channel ID for buddy requests for the specific guild
    sql_select = "SELECT buddy_acceptance_channel_id FROM GuildSettings WHERE guild_id = %s"
    val_select = (guild_id_str,)
    mycursor.execute(sql_select, val_select)
    settings = mycursor.fetchone()

    if settings and settings[0]:
        acceptance_channel_id = settings[0]
        channel = bot.get_channel(int(acceptance_channel_id))
        if channel:
            view = BuddyAcceptView(user_id=str(user_id))  # Ensure BuddyAcceptView is adjusted for MySQL
            await channel.send(f"New buddy request from <@{user_id_str}>. Click to accept.", view=view)

def store_view_info(guild_id, channel_id, view_custom_id):
    mycursor.execute("""
        INSERT INTO GuildSettings (guild_id, channel_id, view_custom_id)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE 
        channel_id=VALUES(channel_id), 
        view_custom_id=VALUES(view_custom_id)
    """, (guild_id, channel_id, view_custom_id))
    mydb.commit()



class BuddyAcceptView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__()
        self.user_id = user_id

    async def disable_buttons(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    @discord.ui.button(label="Accept Buddy", style=discord.ButtonStyle.green, custom_id="accept_buddy")
    async def accept_buddy(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Convert user_id to ObjectId
        user_id = self.user_id
        user_id_int = int(user_id)
        print(f"Attempting to fetch buddy user with ID: {user_id}")
        # Prepare SQL query to verify user status
        sql = "SELECT user_id, guild_id, status FROM BuddyRequests WHERE user_id = %s AND status = 'open'"
        val = (user_id_int,)
        mycursor.execute(sql, val)
        user = mycursor.fetchone()
        print(f"Query result: {user}")

        if not user:
            await interaction.response.send_message("This buddy request does not exist.", ephemeral=True)
            return
        
        status = user[2]
        if status == "accepted":
            await interaction.response.send_message("This buddy request has already been accepted.", ephemeral=True)
            return

        # Step 2: Attempt to update the buddy request status if it's open
        # Update the buddy request status to 'accepted'
        sql_update = "UPDATE BuddyRequests SET status = 'accepted' WHERE user_id = %s AND status = 'open'"
        mycursor.execute(sql_update, val)
        mydb.commit()

        # Check if the update was successful
        if mycursor.rowcount == 1:
            await self.disable_buttons()
            await interaction.response.edit_message(content="You have successfully accepted the buddy request.", view=self)
            # Fetch the Member objects for both the requester and the accepter
            guild = interaction.guild
            requester_id = user[0]
            requester = await guild.fetch_member(str(requester_id))
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
    

@bot.command(name='sac', description='Set acceptance channel and list open buddy requests.')
@commands.has_permissions(administrator=True)
async def set_acceptance_channel(ctx):
    guild_id = str(ctx.guild.id)
    acceptance_channel_id = str(ctx.channel.id)

    # Update the guild-specific settings with the new acceptance channel ID
    sql = "REPLACE INTO GuildSettings (guild_id, acceptance_channel_id) VALUES (%s, %s)"
    val = (guild_id, acceptance_channel_id)
    mycursor.execute(sql, val)
    mydb.commit()
    await ctx.send(f"Channel {ctx.channel.mention} is now set as the buddy acceptance channel for this guild.")

    # Fetch all unaccepted buddy requests from the database for this guild
    sql = "SELECT user_id FROM BuddyRequests WHERE guild_id = %s AND status = 'open'"
    val = (guild_id,)
    mycursor.execute(sql, val)
    unaccepted_requests = mycursor.fetchall()

    # Post a BuddyAcceptView for each unaccepted request in the newly set channel
    for request in unaccepted_requests:
        user_id = request[0]
        view = BuddyAcceptView(user_id)  # Ensure BuddyAcceptView is adjusted for MySQL
        await ctx.channel.send(f"New buddy request from <@{user_id}>. Click to accept.", view=view)

@bot.command(name="disconnect")
async def disconnect(ctx):
    channel = ctx.channel
    await delete_private_channel(channel)

@bot.event
async def on_request_buddy(interaction: discord.Interaction, user_id: str):
    guild_id = str(interaction.guild.id)
    
    # Insert the buddy request into MySQL database
    sql_insert = "INSERT INTO BuddyRequests (guild_id, user_id, status) VALUES (%s, %s, 'open')"
    val_insert = (guild_id, user_id)
    mycursor.execute(sql_insert, val_insert)
    user_id = mycursor.lastrowid  # Get the last inserted ID
    mydb.commit()

    # Fetch the designated channel ID for buddy requests for this guild
    sql_select = "SELECT acceptance_channel_id FROM GuildSettings WHERE guild_id = %s"
    val_select = (guild_id,)
    mycursor.execute(sql_select, val_select)
    settings = mycursor.fetchone()
    
    if settings and settings[0]:
        acceptance_channel_id = settings[0]
        channel = interaction.guild.get_channel(int(acceptance_channel_id))
        if channel:
            view = BuddyAcceptView(user_id=user_id)  # Adjusted for user_id as a string
            await channel.send(f"New buddy request from <@{user_id}>. Click to accept.", view=view)


def initialise_database(mycursor):

    # Create or update the GuildSettings table to include acceptance_channel_id
    mycursor.execute("""
        CREATE TABLE IF NOT EXISTS GuildSettings (
            guild_id BIGINT NOT NULL PRIMARY KEY,
            buddy_request_channel_id BIGINT,
            channel_id BIGINT,
            view_custom_id VARCHAR(255),
            acceptance_channel_id BIGINT
        )
    """)

    # Create the BuddyRequests table as per your specifications
    mycursor.execute("""
        CREATE TABLE IF NOT EXISTS BuddyRequests (
            request_id INT AUTO_INCREMENT PRIMARY KEY,
            guild_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            status ENUM('open', 'accepted', 'closed') NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Commit the changes and close the connection
    mydb.commit()

def check_database_initialised(mycursor):
    """Check if the database has been initialized."""
    # Attempt to select a table that should exist after initialization
    mycursor.execute("SHOW TABLES LIKE 'GuildSettings'")
    result = mycursor.fetchone()
    return result is not None

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}!')
    bot.add_view(BuddyRequestView())

    if not check_database_initialised(mycursor):
        print("Initialising database...")
        initialise_database(mycursor)
    else:
        print("Database already initialised.") 

    # mycursor.execute("SELECT guild_id, channel_id, view_custom_id FROM GuildSettings WHERE view_custom_id IS NOT NULL")
    
    # for (guild_id, channel_id, view_custom_id) in mycursor:
    #     guild = bot.get_guild(guild_id)
    #     if guild:
    #         channel = guild.get_channel(channel_id)
    #         if channel:
    #             embed = Embed(
    #             title="Request Buddy",
    #             description="Welcome to our community! \nWe hope to accommodate you with a personal buddy to help you out. \nPlease request a buddy and someone will join you shortly.",
    #             color=0xdeffee
    #             )
    #             view = BuddyRequestView()
    #             await channel.send(embed=embed, view=view)

# Run the bot
if os.getenv("TOKEN"):
    print("Running in production mode.")
    bot.run(TOKEN)

# a seperate token to test without needing to upload
else:
    print("Running in test mode.")
    bot.run(config['TESTTOKEN'])

