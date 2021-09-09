#!/usr/bin/env python3

import asyncio
import json
import os
import time

import discord
import watchdog.events as wevents
import watchdog.observers as wobservers

from deepbluesky import DeepBlueSky

client = DeepBlueSky(bot_name='ranger')

client.default_properties['command_prefix'] = '-'
client.extra_wikis.append('https://azurlane.koumakan.jp/w/index.php')

@client.event
async def on_ready():
    for filename in os.listdir(pr_data_dir):
        if filename.endswith('.meta.post'):
            post_file_created(filename, prefix=f'{pr_data_dir}/')

@client.event
async def on_message(message):
    await client.handle_message(message)

client.run()
