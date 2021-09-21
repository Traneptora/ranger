#!/usr/bin/env python3

import asyncio
import json
import os
import time

import discord

from deepbluesky import DeepBlueSky

client = DeepBlueSky(bot_name='ranger')

client.default_properties['command_prefix'] = '-'
client.extra_wikis.append('https://azurlane.koumakan.jp/w/index.php')

@client.event
async def on_ready():
    client.logger.info(f'Logged in as {client.user}')
    game = discord.Game('-help')
    await client.change_presence(status=discord.Status.online, activity=game)

@client.event
async def on_message(message):
    await client.handle_message(message)

client.run()
