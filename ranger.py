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

async def upload(channel, content, metadata):
    image_filename = f'{pr_data_dir}/{metadata["filename"]}'
    if not os.path.exists(image_filename):
        return await channel.send(content=content)
    with open(image_filename, 'rb') as fd:
        file = discord.File(fd)
        message = await channel.send(content=content, file=file)
    os.unlink(image_filename)
    return message

def get_content_string(metadata):
    lines = [
        f'Original: `{metadata["original"]}`',
        f'Checksum: `{metadata["checksum"]}`',
    ]
    if 'time' in metadata:
        metadata['crtime'] = metadata['time']
        del metadata['time']
    lines += [f'Upload Timestamp: <t:{metadata["crtime"]}>']
    if int(metadata["crtime"]) != int(metadata["mtime"]):
        lines += [f'Edit Timestamp: <t:{metadata["mtime"]}>']
    lines += [
        f'Project Type: `{metadata["project-type"]}`',
        f'Project Series: `{metadata["project-series"]}`',
        f'Project Name: `{metadata["project-name"]}`',
    ]
    return '\n'.join(lines)

async def post_file_created0(src, prefix):
    suffix = '.meta.post'
    name = prefix + src[:-len(suffix)]
    if src == '':
        return
    channel = await client.get_or_fetch_channel(875062872277930004)
    with open(f'{name}.meta.json') as jsonfile:
        metadata = json.load(jsonfile)
    disc_file = f'{name}.meta.disc'
    if os.path.exists(disc_file):
        with open(disc_file) as jsonfile:
            cached_metadata = json.load(jsonfile)
        if 'time' in cached_metadata:
            cached_metadata['crtime'] = cached_metadata['time']
        metadata['crtime'] = cached_metadata['crtime']
        content = get_content_string(metadata)
        try:
            message = await channel.fetch_message(cached_metadata["message-id"])
            await message.edit(content=(f'**Metadata Edited <t:{int(time.time())}>**\n' + content))
            await channel.send(f'Uploaded image edited: {message.jump_url}')
        except discord.errors.NotFound:
            message = await upload(channel, f'**Metadata Change For Deleted Upload**\n{cached_metadata["message-id"]}\n{content}', metadata)
    else:
        content = get_content_string(metadata)
        message = await upload(channel, content, metadata)
    metadata["message-id"] = message.id
    with open(disc_file, 'w') as jsonfile:
        json.dump(metadata, jsonfile)
    os.unlink(f'{prefix}{src}')

def post_file_created(src, prefix=''):
    client.loop.create_task(post_file_created0(src, prefix))

pr_data_event_handler = wevents.PatternMatchingEventHandler(['*.meta.post'], ignore_directories=True, case_sensitive=True)

def on_created(event):
    post_file_created(event.src_path)

pr_data_event_handler.on_created = on_created
pr_data_dir = 'pr-data'

observer = wobservers.Observer()
observer.schedule(pr_data_event_handler, pr_data_dir, recursive=False)

observer.start()

@client.event
async def on_ready():
    for filename in os.listdir(pr_data_dir):
        if filename.endswith('.meta.post'):
            post_file_created(filename, prefix=f'{pr_data_dir}/')

@client.event
async def on_message(message):
    await client.handle_message(message)

client.run()
