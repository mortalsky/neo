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
import string
import random
import io
import asyncio
from html import unescape as us
from typing import Union

import discord
from fuzzywuzzy import process
from PIL import Image
from discord.ext import commands
import uwuify
from async_timeout import timeout

from utils.config import conf
from utils.paginator import BareBonesMenu, CSMenu

CODE = {'A': '.-', 'B': '-...', 'C': '-.-.',
        'D': '-..', 'E': '.', 'F': '..-.',
        'G': '--.', 'H': '....', 'I': '..',
        'J': '.---', 'K': '-.-', 'L': '.-..',
        'M': '--', 'N': '-.', 'O': '---',
        'P': '.--.', 'Q': '--.-', 'R': '.-.',
        'S': '...', 'T': '-', 'U': '..-',
        'V': '...-', 'W': '.--', 'X': '-..-',
        'Y': '-.--', 'Z': '--..',

        '0': '-----', '1': '.----', '2': '..---',
        '3': '...--', '4': '....-', '5': '.....',
        '6': '-....', '7': '--...', '8': '---..',
        '9': '----.'
        }

CODE_REVERSED = {value: key for key, value in CODE.items()}


def to_morse(s):
    return ' '.join(CODE.get(i.upper(), i) for i in s)


def from_morse(s):
    return ''.join(CODE_REVERSED.get(i, i) for i in s.split())


def upscale(inp):
    img = Image.open(io.BytesIO(inp))
    h, w = img.size
    newsize = (h*2, w*2)
    img = img.resize(newsize)
    with io.BytesIO() as out:
        img.save(out, format='PNG')
        bf = out.getvalue()
    return bf


async def fetch_one(self, ctx, thing: str):
    converter = commands.EmojiConverter()
    # TODO: Cache this
    indexed_guilds = [self.bot.get_guild(rec['guild_id'])
                      for rec in await self.bot.conn.fetch('SELECT guild_id FROM guild_prefs WHERE index_emojis=TRUE')]
    available_emojis = list()
    for guild in indexed_guilds:
        available_emojis.extend(guild.emojis)
    choice = process.extractOne(thing, [e.name for e in available_emojis])[0]
    return await converter.convert(ctx, choice)


class Fun(commands.Cog):
    """Collection of fun commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['bin'])
    async def binary(self, ctx, *, content):
        """Convert stuff to and from binary"""
        try:
            n = int(content, 2)
            await ctx.safe_send(
                '**Converted from binary: **'
                + n.to_bytes((n.bit_length() + 7) // 8, 'big').decode())
        except Exception:
            await ctx.safe_send(str(bin(int.from_bytes(content.encode(), 'big'))))

    @commands.command()
    async def morse(self, ctx, *, message):
        """Convert a message to morse code"""
        await ctx.send(to_morse(message))

    @commands.command()
    async def demorse(self, ctx, *, morse):
        """Convert a message from morse code"""
        await ctx.send(from_morse(morse))

    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def emojify(self, ctx, *, message):
        """Returns the inputted message, converted to emojis"""
        out = []
        for letter in list(message):
            if letter in string.digits:
                out.append(conf['number_emojis'][str(letter)])
            elif letter in string.ascii_letters:
                out.append(f":regional_indicator_{letter.lower()}:")
            else:
                out.append(letter)
        await ctx.send(f'**{ctx.author.name} says: **' + ' '.join(out) + '_ _')

    @commands.command()
    async def vote(self, ctx, *, poll):
        """Create an easy poll"""
        # TODO: Make the message edit itself when the reactions are updated so that it's easier to tell what the actual votes are
        embed = discord.Embed(
            title=' ',
            description=f'**Cast your vote:**\n{poll}',
            color=discord.Color.main)
        embed.set_footer(
            text=f'Vote created by {ctx.author.name}',
            icon_url=ctx.author.avatar_url_as(static_format='png'))
        embed.timestamp = ctx.message.created_at
        vote = await ctx.send(embed=embed)
        await vote.add_reaction('<:upvote:655880245047459853>')
        await vote.add_reaction('<:downvote:655880259358687252>')

    @commands.command()
    async def quiz(self, ctx, difficulty=None):
        """Start a quick trivia"""
        if not difficulty:
            difficulty = random.choice(['easy', 'medium', 'hard'])
        async with self.bot.session.get(
                'https://opentdb.com/api.php',
                params={'amount': 1, 'difficulty': difficulty}
                ) as r:
            dat = await r.json()
        data = dat['results'][0]
        final_display = []
        anwrs = [us(a) for a in data['incorrect_answers']]
        anwrs.append(us(data['correct_answer']))
        random.shuffle(anwrs)
        for index, value in enumerate(anwrs, 1):
            final_display.append(f'{index}. `{value}`')
        final_display = '\n'.join(final_display)
        embed = discord.Embed(
            title='',
            description=f'**{us(data["question"])}**\n{final_display}',
            color=discord.Color.main
            )
        embed.add_field(
            name='Category',
            value=f'`{us(data["category"])}`',
            inline=True
            )
        embed.add_field(
            name='Difficulty',
            value=f'`{us(data["difficulty"]).title()}`'
            )
        triv = await ctx.send(embed=embed)
        for index, value in enumerate(anwrs):
            await triv.add_reaction(conf['number_emojis'][str(index+1)])
        await triv.add_reaction(ctx.tick(False))
        react, user = await self.bot.wait_for(
            'reaction_add',
            check=lambda r, u:
                r.message.id == triv.id and u.id == ctx.author.id)
        try:
            ind = int(conf['emoji_numbers'][react.emoji])
            if anwrs[ind-1] == us(data['correct_answer']):
                await triv.edit(embed=discord.Embed(
                    title='',
                    description=f'Correct! **{us(data["correct_answer"])}**'
                    ' was the correct answer!',
                    color=discord.Color.main
                    ))
            else:
                await triv.edit(embed=discord.Embed(
                    title='',
                    description=f'Sorry, **{us(data["correct_answer"])}**'
                    ' was the correct answer',
                    color=discord.Color.main
                    ))
        except Exception:
            await triv.edit(embed=discord.Embed(
                title='',
                description=f'Quiz cancelled. The answer was '
                f'**{us(data["correct_answer"])}**',
                color=discord.Color.main
                ))

    @commands.command()
    @commands.is_nsfw()
    async def urban(self, ctx, *, term):
        """Search urban dictionary"""
        async with self.bot.session.get(
                'http://api.urbandictionary.com/v0/define',
                params={'term': term}) as resp:
            js = await resp.json()
        defs = js['list']
        menu_list = []
        for item in defs:
            menu_list.append(
                f"[Link]({item['permalink']})"
                + f"\n\n{item['definition']}\n\n**Example:**\n {item['example']}"
                .replace('[', '').replace(']', ''))
        entries = sorted(menu_list)
        source = BareBonesMenu(entries, per_page=1)
        menu = CSMenu(source, delete_message_after=True)
        await menu.start(ctx)

    @commands.group(name='emoji', aliases=['em'], invoke_without_command=True)
    async def get_emoji(self, ctx, *, emoji):
        """
        Don't have nitro? Not a problem! Use this to get some custom emoji!
        """
        await ctx.send(await fetch_one(self, ctx, emoji))

    @get_emoji.command(aliases=['r'])
    async def react(self, ctx, *, emoji):
        """
        React with emoji from other guilds without nitro!
        Use the command with an emoji name, and then add your reaction
        within 15 seconds, and the bot will remove its own.
        """
        to_react = await fetch_one(self, ctx, emoji)
        async for m in ctx.channel.history(limit=2).filter(lambda m: m.id != ctx.message.id):
            await m.add_reaction(to_react)
            important_msg = m
        try:
            react, user = await self.bot.wait_for(
                'reaction_add',
                timeout=15.0,
                check=lambda r, u:
                    r.message.id == important_msg.id and r.emoji == to_react and u.id == ctx.author.id
                    )
        except asyncio.TimeoutError:
            await important_msg.remove_reaction(to_react, self.bot.user)
        else:
            await important_msg.remove_reaction(to_react, self.bot.user)
            if ctx.channel.permissions_for(ctx.guild.me).manage_messages:
                await ctx.message.delete()

    @get_emoji.command()
    async def big(
            self, ctx,
            emoji: Union[discord.Emoji, discord.PartialEmoji, str]):
        i = await fetch_one(self, ctx, emoji) if \
            isinstance(emoji, str) else emoji
        out = await self.bot.loop.run_in_executor(None, upscale, (await i.url.read()))
        await ctx.send(file=discord.File(io.BytesIO(out), filename='largeemoji.png'))

    @get_emoji.command()
    async def view(self, ctx):
        """
        View all emoji the bot has access to
        """
        emoji_list = [e for e in self.bot.emojis]
        sorted_em = sorted(emoji_list, key=lambda e: e.name)
        entries = [f"{e} - " + e.name.replace('_', r'\_') for e in sorted_em]
        menu = CSMenu(
            BareBonesMenu(entries, per_page=25), delete_message_after=True)
        await menu.start(ctx)

    @commands.command()
    async def owoify(self, ctx, *, message):
        """
        Do you hate yourself with a passion? This is the command for you!
        """
        flags = uwuify.SMILEY
        await ctx.safe_send(uwuify.uwu(message, flags=flags))

    @commands.command(aliases=['WorldHealthOrganization'])
    async def who(self, ctx):
        """Quick minigame to try to guess who someone is from their avatar"""
        if ctx.guild.large:
            choose_from = [
                m.author for m in self.bot._connection._messages if m.guild == ctx.guild and m.author != self.bot.user
            ]
            user = random.choice(choose_from)
        else:
            user = random.choice(ctx.guild.members)
        await ctx.send(
            embed=discord.Embed(color=discord.Color.main)
            .set_image(url=user.avatar_url_as(static_format='png', size=128)))
        try:
            async with timeout(10):
                while True:
                    try:
                        message = await self.bot.wait_for(
                            'message',
                            timeout=10.0,
                            check=lambda m: m.author.bot is False)
                        if user.name.lower() in message.content.lower() or user.display_name.lower() in message.content.lower():
                            return await ctx.send(f'{message.author.mention} got it!')
                    except asyncio.TimeoutError:
                        continue
        except (asyncio.TimeoutError, asyncio.CancelledError):
            return await ctx.send(f"Time's up! It was {user}")

    @commands.command(aliases=['comp'])
    async def compliment(self, ctx, victim: Union[discord.Member, discord.User] = None):
        """Want to hear something nice about you or someone else?"""
        victim = victim or ctx.author
        async with self.bot.session.get('https://complimentr.com/api') as resp:
            js = await resp.json()
        await ctx.safe_send(victim.display_name + f', {js["compliment"].lower()}')

    @commands.command(aliases=['ins'])
    async def insult(self, ctx, victim: Union[discord.Member, discord.Member] = None):
        """What, you egg?"""
        victim = victim or ctx.author
        async with self.bot.session.get('http://quandyfactory.com/insult/json') as resp:
            js = await resp.json()
        await ctx.safe_send(victim.display_name + f', {js["insult"].lower()}')

    @commands.command()
    async def dongsize(self, ctx, *, victim: discord.Member = None):
        """Go ahead. You know you want to."""
        victim = victim or ctx.author
        ran = 25 if victim.id in (self.bot.owner_id, self.bot.user.id) else random.Random(victim.id).randint(1, 15)
        dong = '8' + '='*ran + 'D'
        await ctx.safe_send(dong)


def setup(bot):
    bot.add_cog(Fun(bot))
