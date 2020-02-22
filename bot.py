import json
from discord.ext import commands
description = '''An example bot to showcase the discord.ext.commands extension
module.

There are a number of utility commands being showcased here.'''
def load_settings():
    with open("config/bot_settings.json", "r") as f:
        return json.load(f)

settings = load_settings()
credentials = settings.get("credentials")
bot = commands.Bot(command_prefix=settings.get("prefixes"), description=description, owner_id=credentials.get("owner"))

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')

@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f"{type(error).__name__}: {error}")

@commands.is_owner()
@bot.command(name="shutdown")
async def shutdown(ctx):
    await ctx.send("shutting down..")
    await bot.logout()

@commands.is_owner()
@bot.command(name="reload", hidden=True)
async def reload(ctx):
    try:
        bot.reload_extension("cogs.panda_moe")
        await ctx.send('\N{THUMBS UP SIGN}')
    except Exception as e:
        await ctx.send('\N{THUMBS DOWN SIGN}')
        await ctx.send('{}: {}'.format(type(e).__name__, e))

bot.load_extension("cogs.panda_moe")
bot.run(credentials.get("token"))
