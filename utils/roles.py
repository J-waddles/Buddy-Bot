from discord.utils import get

async def add_role_to_user(user, role_name, guild):
    role = get(guild.roles, name=role_name)
    if role:
        await user.add_roles(role)

async def remove_role_from_user(user, role_name, guild):
    role = get(guild.roles, name=role_name)
    if role:
        await user.remove_roles(role)
