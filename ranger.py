#!/usr/bin/env python3

import discord

from deepbluesky import DeepBlueSky

# Launch a default Deep Blue Sky bot

client = DeepBlueSky(bot_name='ranger')

client.default_properties['command_prefix'] = '-'
client.extra_wikis.append('https://azurlane.koumakan.jp/w/index.php')

@client.event
async def on_message(message):
    await client.handle_message(message)

client.run()
