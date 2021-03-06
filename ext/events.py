"""
neo Discord bot
Copyright (C) 2020 nickofolas

neo is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

neo is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with neo.  If not, see <https://www.gnu.org/licenses/>.
"""
import asyncio
import collections
from contextlib import suppress
import re
from datetime import datetime

import discord
from discord.ext import commands, tasks

from utils.config import conf

ignored_cmds = re.compile(r'\.+')


# noinspection PyCallingNonCallable
class Events(commands.Cog):
    """Contains the listeners for the bot"""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, (commands.CommandNotFound, commands.NotOwner)):
            return  # Ignores CommandNotFound and NotOwner because they're unnecessary
        elif isinstance(error, commands.CommandOnCooldown):
            return await ctx.message.add_reaction(conf['emoji_suite']['alarm'])  # Handles Cooldowns uniquely
        do_emojis = True
        if settings := self.bot.user_cache.get(ctx.author.id):
            if settings.get('repr_errors'):
                error = repr(error)
            do_emojis = settings.get('error_emojis', True)
        await ctx.propagate_to_eh(self.bot, ctx, error, do_emojis=do_emojis)  # Anything else is propagated to the
        # reaction handler

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.content == before.content:
            return
        if not self.bot.snipes.get(after.channel.id):  # Creates the snipes cache
            self.bot.snipes[after.channel.id] = {'deleted': collections.deque(list(), 100),
                                                 'edited': collections.deque(list(), 100)}
        if usr := self.bot.user_cache.get(after.author.id):
            if usr['can_snipe']:
                if after.content and not after.author.bot:  # Updates the snipes edit cache
                    self.bot.snipes[after.channel.id]['edited'].append((before, after, datetime.utcnow()))

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not self.bot.snipes.get(message.channel.id):  # Creates the snipes cache
            self.bot.snipes[message.channel.id] = {'deleted': collections.deque(list(), 100),
                                                   'edited': collections.deque(list(), 100)}
        if usr := self.bot.user_cache.get(message.author.id):
            if usr['can_snipe']:
                if message.content and not message.author.bot:  # Updates the snipes deleted cache
                    self.bot.snipes[message.channel.id]['deleted'].append((message, datetime.utcnow()))

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        embed = discord.Embed(
            description=f'Joined guild {guild.name} [{guild.id}]',
            color=discord.Color.main)
        embed.set_thumbnail(url=guild.icon_url_as(static_format='png'))
        embed.add_field(
            name='**Members**',  # Basic stats about the guild
            value=f'**Total:** {len(guild.members)}\n'
                  + f'**Admins:** {len([m for m in guild.members if m.guild_permissions.administrator])}\n'
                  + f'**Owner: ** {guild.owner}\n',
            inline=False)
        with suppress(Exception):
            async for a in guild.audit_logs(limit=5):  # Tries to disclose who added the bot
                if a.action == discord.AuditLogAction.bot_add:
                    action = a
                    break
            embed.add_field(
                name='**Added By**',
                value=action.user
            )

        await self.bot.conn.execute(  # Adds/updates this guild in the db using upsert syntax
            'INSERT INTO guild_prefs (guild_id, prefix) VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET prefix=$2',
            guild.id, 'n/')
        await self.bot.logging_channels.get('guild_io').send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.bot.conn.execute('DELETE FROM guild_prefs WHERE guild_id=$1', guild.id)
        # Removes guild from database
        embed = discord.Embed(
            description=f'Removed from guild {guild.name} [{guild.id}]',
            color=discord.Color.pornhub)  # Don't ask
        embed.set_thumbnail(url=guild.icon_url_as(static_format='png'))
        await self.bot.logging_channels.get('guild_io').send(embed=embed)


def setup(bot):
    bot.add_cog(Events(bot))
