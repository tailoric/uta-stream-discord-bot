from discord.ext import commands, tasks
from discord import opus, FFmpegPCMAudio, Embed, colour
from aiohttp import ClientSession
import discord.utils
import lavalink
import os
import json


class PandaMoe(commands.Cog):
    """
    A cog for playing music from https://vivalapanda.moe
    """
    def __init__(self, bot, settings):
        self.bot = bot
        self.use_lavalink = settings.get("use_lavalink")
        self.api_key = settings.get("api_key")
        self.dj_role_name = settings.get("dj_role_name")
        self.use_dj_role = settings.get("use_dj_role")
        self.lavalink_settings = settings.get("lavalink_settings")
        self.panda_moe_url = "https://vivalapanda.moe"

        if not hasattr(bot, "client_session"):
            self.client_session = ClientSession()
        else:
            self.client_session = bot.client_session
        if self.use_lavalink:
            if not hasattr(bot, 'lavalink'):  # This ensures the client isn't overwritten during cog reloads.
                bot.lavalink = lavalink.Client(bot.user.id)
                bot.lavalink.add_node('127.0.0.1', 2333, 'youshallnotpass', 'eu',
                                      'default-node')  # Host, Port, Password, Region, Name
                bot.add_listener(bot.lavalink.voice_update_handler, 'on_socket_response')

    def cog_unload(self):
        if not hasattr(self.bot, "client_session"):
            self.bot.loop.create_task(self.client_session.close())
        if self.use_lavalink:
            self.bot.lavalink._event_hooks.clear()

    async def cog_before_invoke(self, ctx):
        """list of checks that have to be done before invoking a command"""
        if ctx.command.name in ["enqueue", "skip"] and not self.api_key:
            raise commands.CommandError("api key is not loaded I am not able to execute this command")
        if ctx.command.name in ["enqueue", "skip"] and self.use_dj_role:
            user_roles_ids = [role.id for role in ctx.author.roles]
            dj_role = discord.utils.get(ctx.guild.roles, name=self.dj_role_name)
            if dj_role.id not in user_roles_ids:
                raise commands.CommandError(f"Not allowed to use this because "
                                            f"you are missing the following role {dj_role.name}")
        if self.use_lavalink:
            self.bot.lavalink.players.create(ctx.guild.id, endpoint=str(ctx.guild.region))


    async def get_current_voice_channel(self, ctx):
        """get the current voice channel the bot is connected to"""
        if self.use_lavalink:
            if ctx.guild and ctx.guild.me.voice:
                return ctx.guild.me.voice.channel
            return None
        return next(iter(vc for vc in ctx.bot.voice_clients if vc.guild.id == ctx.guild.id), None)

    @commands.command(name="play")
    async def panda_play(self, ctx):
        """
        start playing music from the bot
        """
        connected_guilds = [vc.guild.id for vc in ctx.bot.voice_clients]
        voice = None
        if ctx.guild.id not in connected_guilds:
            voice = await self.connect_to_voice(ctx)
        if not voice:
            return
        if self.use_lavalink:
            await self.play_from_lavalink(ctx)
        else:
            await self.play_from_ffmpeg(ctx)

    @commands.command(name="stop")
    async def panda_stop(self, ctx):
        """
        stop the bot from playing and disconnect
        """
        current_voice = await self.get_current_voice_channel(ctx)
        if not current_voice:
            await ctx.send("I am currently not connected to any voice channel")
            return
        if self.use_lavalink:
            player = self.bot.lavalink.players.get(ctx.guild.id)
            if player.is_connected:
                player.queue.clear()
                await player.stop()
                self.bot.lavalink.players.remove(ctx.guild)
                await self.connect_to(ctx.guild.id, None)
                return
        current_voice.stop()
        await current_voice.disconnect()

    @commands.command(name="playing", aliases=["current"])
    async def panda_current_song(self, ctx):
        """
        get the song that is currently playing
        """
        current_voice = await self.get_current_voice_channel(ctx)
        if not current_voice:
            await ctx.send("I am currently not connected to any voice channel")
            return
        current_song = await self.get_current_song()
        if current_song:
            await ctx.send(embed=self.embed_for_current_song(current_song))
            return
        await ctx.send("Could not fetch current song.")
    @commands.command(name="enqueue")
    async def panda_enqueue(self, ctx, url):
        """
        queue a new song, currently only supports direct urls
        """
        params = {"song", url}
        headers = {"Authorization", f"Bearer {self.api_key}"}
        async with self.client_session.post(f"{self.panda_moe_url}/api/enqueue",
                                            params=params,
                                            headers=headers) as response:
            if response.status == 200:
                await ctx.send("Song enqueued successfully")
            else:
                error_message = await response.read()
                await ctx.send(f"Server replied with the following error message\n{error_message}")

    @commands.command(name="skip")
    async def panda_skip(self, ctx):
        """
        skip the current song.
        """
        headers = {"Authorization", f"Bearer {self.api_key}"}
        async with self.client_session.post(f"{self.panda_moe_url}/api/skip",
                                            headers=headers) as response:
            if response.status == 200:
                await ctx.send("Song skipped.")
            else:
                error_message = await response.read()
                await ctx.send(f"Server replied with the following error message\n{error_message}")

    def embed_for_current_song(self, current_song):
        """
        helper function for creating an embed of the current song
        """
        return Embed(title=current_song.get("title"), url=current_song.get("url"),
                     colour=colour.Color.blurple())

    async def connect_to_voice(self, ctx):
        """
        connect to the voice client of the user who used the play command
        """
        author_in_voice = bool(ctx.author.voice)

        if author_in_voice:
            if self.use_lavalink:
                await self.connect_to(ctx.guild.id, str(ctx.author.voice.channel.id))
                return ctx.author.voice.channel
            else:
                return await ctx.author.voice.channel.connect()
        else:
            await ctx.send("you are not in a voice channel!")

    async def play_from_lavalink(self, ctx):
        """use lavalink for playing the music see:
        https://github.com/Frederikam/Lavalink
        and
        https://github.com/Devoxin/Lavalink.py
         """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        if not player.is_playing:
            results = await player.node.get_tracks(f"{self.panda_moe_url}/stream.mp3")
            player.add(requester=ctx.author.id, track=results["tracks"][0])
            await player.play()
            current_song = await self.get_current_song()
            if current_song:
                await ctx.send(f"Now playing {self.panda_moe_url} with the song **{current_song.get('title')}**")

    async def play_from_ffmpeg(self, ctx):
        """
        default way of playing music in voice using the FfmpegAudioSource
        """
        current_voice = await self.get_current_voice_channel(ctx)
        if not current_voice:
            await ctx.send("couldn't get the current voice channel for playing")
            return
        if not current_voice.is_playing():
            source = FFmpegPCMAudio(f"{self.panda_moe_url}/stream.mp3")
            current_voice.play(source)
            current_song = await self.get_current_song()
            if current_song:
                await ctx.send(f"Now playing {self.panda_moe_url} with the song **{current_song.get('title')}**")

    async def get_current_song(self):
        """
        check for the currently playing song
        """
        async with self.client_session.get(f"{self.panda_moe_url}/api/playing") as response:
            if response.status == 200:
                data = await response.json()
                return data.get("currentSong", None)
            else:
                return None

    async def connect_to(self, guild_id: int, channel_id: str):
        """ Connects to the given voicechannel ID. A channel_id of `None` means disconnect. """
        ws = self.bot._connection._get_websocket(guild_id)
        await ws.voice_state(str(guild_id), channel_id)
        # The above looks dirty, we could alternatively use `bot.shards[shard_id].ws` but that assumes
        # the bot instance is an AutoShardedBot.

def setup(bot):
    if not os.path.exists("config/panda_moe.json"):
        settings = {
            "use_lavalink": False,
            "api_key": None,
            "dj_role_name": None,
            "use_dj_role": False,
            # using the default settings from
            # https://github.com/Frederikam/Lavalink/blob/master/LavalinkServer/application.yml.example
            "lavalink_settings": {
                "host": "127.0.0.1",
                "port": 2333,
                "password": "youshallnotpass",
                "region": "eu",
                "node-name": "default-node"
            }
        }
        if not os.path.exists("config"):
            print("no config found creating directory...")
            os.mkdir("config")
        print("initializing config with default values to config/panda_moe.json")
        with open("config/panda_moe.json", "w") as f:
            json.dump(settings, f, indent=2)
    else:
        with open("config/panda_moe.json", "r") as f:
            settings = json.load(f)
    bot.add_cog(PandaMoe(bot, settings=settings))
