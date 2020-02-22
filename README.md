# Panda Bot
A bot for playing and streaming music from the website https://vivalapanda.moe which is using 
[uta-stream](https://github.com/VivaLaPanda/uta-stream)

## Setup
clone the repository and install the requirements via pip

if needed set up a virtual environment `python -m venv bot_env`, (this bot was set up for python version 3.7)

`python -m pip install -r requirements.txt`

go to the `config/bot_settings.json` and set all the necessary values for your bot
after that run the bot via `python bot.py`

## Lavalink

The cog is also set up in a way to allow the use of [lavalink](https://github.com/Frederikam/Lavalink)
if you want to use that then set the `use_lavalink` option in `config/panda_moe.json` to `true`
otherwise the bot will use the default `FfmpegAudioSource` for playing the music.




