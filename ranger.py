#!/usr/bin/env python3

import discord
from deepbluesky import DeepBlueSky

# Launch a default Deep Blue Sky bot

client = DeepBlueSky()

client.default_properties['command_prefix'] = '-'

@client.event
async def on_ready():
    client.logger.info(f'Logged in as {client.user}')
    game = discord.Game('-help')
    await client.change_presence(status=discord.Status.online, activity=game)

@client.event
async def on_message(message):
    await client.handle_message(message, extra_wikis=['https://azurlane.koumakan.jp/w/index.php'])

client.run()
