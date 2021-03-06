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
import argparse
import re
import shlex
from typing import Union

import discord
from discord.ext import commands
from discord.ext.commands import has_permissions

from utils.checks import is_owner_or_administrator
from utils.converters import BoolConverter
from utils.formatters import prettify_text


class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(message)


ereg = re.compile(
    r'(<a?:\w*:\d*>)|([\U00002600-\U000027BF])|([\U0001f300-\U0001f64F])|([\U0001f680-\U0001f6FF])'
)


async def do_removal(ctx,
                     limit,
                     predicate,
                     *,
                     before=None,
                     after=None):
    if limit > 2000:
        return await ctx.send(
            f'Too many messages to search given ({limit}/2000)')

    if before is None:
        before = ctx.message
    else:
        before = discord.Object(id=before)

    if after is not None:
        after = discord.Object(id=after)
    await ctx.channel.purge(
        limit=limit, before=before, after=after, check=predicate)


class Guild(commands.Cog):
    """Everything to do with guild management can be found here"""

    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        if ctx.guild:
            return True
        else:
            return False

    # Bulk clear command
    @commands.group(aliases=['c', 'purge'], invoke_without_command=True)
    @has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int = 1):
        """Bulk clear a specified amount of messages"""
        if ctx.invoked_subcommand is None:
            await ctx.message.delete()
            await ctx.channel.purge(limit=amount)

    @clear.command(aliases=['-c', 'cu', 'adv'])  # TODO: Flags parse this?
    @has_permissions(manage_messages=True)
    async def custom(self, ctx, *, args: str):
        """
        Advanced clear command that takes any combination of args
        `--user|--contains|--starts|--ends|--search|--after|--before`
        Flag options (no arguments):
        `--bot|--embeds|--files|--emoji|--reactions|--or|--not|--nohide|--code`
        """
        parser = Arguments(add_help=False, allow_abbrev=False)
        parser.add_argument('--user', nargs='+')
        parser.add_argument('--contains', nargs='+')
        parser.add_argument('--regex')
        parser.add_argument('--starts', nargs='+')
        parser.add_argument('--ends', nargs='+')
        parser.add_argument('--or', action='store_true', dest='_or')
        parser.add_argument('--not', action='store_true', dest='_not')
        parser.add_argument('--emoji', action='store_true')
        parser.add_argument('--nohide', action='store_true')
        parser.add_argument(
            '--bot', action='store_const', const=lambda m: m.author.bot)
        parser.add_argument(
            '--embeds', action='store_const', const=lambda m: len(m.embeds))
        parser.add_argument(
            '--code', action='store_true')
        parser.add_argument(
            '--files',
            action='store_const',
            const=lambda m: len(m.attachments))
        parser.add_argument(
            '--reactions',
            action='store_const',
            const=lambda m: len(m.reactions))
        parser.add_argument('--search', type=int, default=5)
        parser.add_argument('--after', type=int)
        parser.add_argument('--before', type=int)

        try:
            args = parser.parse_args(shlex.split(args))
        except Exception as e:
            await ctx.send(str(e))
            return
        predicates = []
        if args.bot:
            predicates.append(args.bot)
        if args.embeds:
            predicates.append(args.embeds)
        if args.files:
            predicates.append(args.files)
        if args.reactions:
            predicates.append(args.reactions)
        if args.emoji:
            custom_emoji = re.compile(
                r'(<a?:\w*:\d*>)|([\U00002600-\U000027BF])|([\U0001f300-\U0001f64F])|([\U0001f680-\U0001f6FF])'
            )
            predicates.append(lambda m: custom_emoji.search(m.content))
        if args.regex:
            custom_regex = re.compile(args.regex)
            predicates.append(lambda m, x=custom_regex: x.search(m.content))
        if args.code:
            predicates.append(lambda m: '```' in m.content)
        if args.user:
            users = []
            converter = commands.MemberConverter()
            for u in args.user:
                try:
                    user = await converter.convert(ctx, u)
                    users.append(user)
                except Exception as e:
                    await ctx.send(str(e))
                    return
            predicates.append(lambda m: m.author in users)
        if args.contains:
            predicates.append(
                lambda m: any(sub in m.content for sub in args.contains))
        if args.starts:
            predicates.append(
                lambda m: any(m.content.startswith(s) for s in args.starts))
        if args.ends:
            predicates.append(
                lambda m: any(m.content.endswith(s) for s in args.ends))
        op = all if not args._or else any

        def predicate(m):
            r = op(p(m) for p in predicates)
            if args._not:
                return not r
            return r

        args.search = max(0, min(2000, args.search))  # clamp from 0-2000
        if not args.nohide:
            await ctx.message.delete()
        await do_removal(
            ctx, args.search, predicate, before=args.before, after=args.after)

    @commands.command()
    @has_permissions(ban_members=True)
    async def ban(self, ctx, member: Union[discord.Member, int], *, reason=None):
        """Issue a ban, can use the ID of a member outside the guild to hackban them"""
        to_ban = discord.Object(id=member) if isinstance(member, int) else member
        user_obj = await self.bot.fetch_user(member) if isinstance(member, int) else member
        await ctx.guild.ban(to_ban, reason=f'{ctx.author} ({ctx.author.id}) - {reason}')
        await ctx.send(f'Banned **{user_obj.name}**')

    @commands.command()
    @has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        """Kick a member - optional reason can be provided"""
        await member.send(
            f'You have been kicked from the {ctx.guild} server. Reason: **{reason}**'
        )
        await member.kick(reason=reason)
        await ctx.send(f'{member} was kicked - **{reason}**')
        await ctx.message.delete()

    @commands.group(name='config', aliases=['cfg'], invoke_without_command=True)
    @is_owner_or_administrator()
    async def guild_config(self, ctx):
        """
        View or modify the configuration for the current guild.
        """
        current_settings = dict(
            (await self.bot.conn.fetch('SELECT * FROM guild_prefs WHERE guild_id=$1', ctx.guild.id))[0])
        readable_settings = list()
        for k, v in current_settings.items():
            if isinstance(v, bool):
                readable_settings.append(f'**{discord.utils.escape_markdown(prettify_text(k))}** {ctx.tick(v)}')
            else:
                readable_settings.append(f'**{discord.utils.escape_markdown(prettify_text(k))}** `{v}`')
        await ctx.send(embed=discord.Embed(
            title='Current Guild Settings', description='\n'.join(readable_settings[1:]),
            color=discord.Color.main).set_thumbnail(url=ctx.guild.icon_url_as(static_format='png')))

    @guild_config.command(aliases=['pfx'])
    @is_owner_or_administrator()
    async def prefix(self, ctx, new_prefix=None):
        """Change the prefix for the current server"""
        if new_prefix is None:
            return await ctx.send(embed=discord.Embed(
                title='Prefixes for this guild',
                description='\n'.join(
                    sorted(set([p.replace('@!', '@') for p in await self.bot.get_prefix(ctx.message)]),
                           key=lambda p: len(p))),
                color=discord.Color.main))
        await self.bot.conn.execute(
            'INSERT INTO guild_prefs (guild_id, prefix) VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET prefix=$2',
            ctx.guild.id, new_prefix)
        await ctx.send(f'Prefix successfully changed to `{new_prefix}`')

    @guild_config.command(name='index')
    @is_owner_or_administrator()
    async def _index_emojis_toggle(self, ctx, on_off: BoolConverter):
        """
        Toggle whether or not emojis from the current guild will be indexed by emoji commands
        """
        await self.bot.conn.execute('UPDATE guild_prefs SET index_emojis=$1 WHERE guild_id=$2', on_off, ctx.guild.id)
        await ctx.message.add_reaction(ctx.tick(True))


def setup(bot):
    bot.add_cog(Guild(bot))
