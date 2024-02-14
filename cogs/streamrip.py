""""
so i mostly care about deezer but i guess i can do the others eventually, as a poc let's just do deezer


at its most basic...
/streamrip url URL
should download and then beets it...
/streamrip search "SEARCH TERM"
should ... list out the results? with buttons?
/streamrip search "SEARCH TERM" 1-2-3-4-5
should ... download that one.

https://www.deezer.com/us/album/466106885

466106885

Version: 6.1.0
"""
import os
from dataclasses import dataclass
import logging

import discord
from discord.ext import commands
from discord.ext.commands import Context
from discord.ui import Select, View

from streamrip.client import DeezerClient
from streamrip.config import Config
from streamrip.media import PendingAlbum
from streamrip.db import Database,Dummy

import subprocess

emojiList = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]

@dataclass
class SearchResult:
    id: int
    title: str
    link: str
    artist: str

class Choices(Select):
   def __init__(self, titles: list[SearchResult]):
      self.titles = titles
      options = [discord.SelectOption(label=result.id, description=result.title, emoji=emojiList[index]) for index,result in enumerate(titles)]
      super().__init__(
         placeholder="Choose which option to download",
         min_values=1,
         max_values=1,
         options=options
      )

   async def callback(self, interaction: discord.Interaction):
      user_choice = self.values[0]

      result_embed = discord.Embed(
         title=f"Downloading '{user_choice}'",
         description=f"Returned {user_choice}....",
         color=0x9C84EF
      )

      await interaction.response.edit_message(embed=result_embed, content=None, view=None)

class ChoicesView(View):
   def __init__(self, titles: list[SearchResult]):
      super().__init__()
      self.add_item(Choices(titles))

# Here we name the cog and create a new class for the cog.
class StreamripCog(commands.Cog, name="streamrip"):
   def __init__(self, bot) -> None:
      self.logger = logging.getLogger("discord_bot")

      self.bot = bot
      config = Config.defaults()
      self.config = config
      config.session.database.downloads_enabled = False
      self.download_path = os.getenv("DOWNLOADS_PATH")
      config.session.downloads.folder = self.download_path
      config.session.deezer.quality = int(os.getenv("QUALITY"))
      config.session.deezer.arl = os.getenv("ARL") # loading it all here because i can't be bothered to properly load the config lol
      client = DeezerClient(config)
      self.client = client

      self.database = Database(Dummy(),Dummy())

   @commands.hybrid_command(
      name="album",
      description="searches and downloads albums",
   )
   async def album(self, context: Context, *, query: str) -> None:
      client = self.client
      if not client.logged_in:
         await client.login()
      rawResults = await client.search("album", query, limit=9)

      if len(rawResults) == 0:
         embed = discord.Embed(
            title="Search Error",
            description=f"Unable to get any results for query: {query}",
            color=0xE02B2B,
         )
         await context.send(embed=embed)
      else:
         flatResults = []
         for result in rawResults:
            flatResults.extend(result["data"])

         results = [SearchResult(result["id"],result["title"],result["link"],result["artist"]["name"]) for result in flatResults]

         embed = discord.Embed(
            title=f"Search Results for '{query}'",
            description=f"Returned {len(flatResults)} results:",
            color=0xBEBEFE
         )
         for index,result in enumerate(results):
            embed.add_field(name=f"{emojiList[index]} {result.title}", value=f"By {result.artist} (URL: {result.link})", inline=False)
      
         await context.send(embed=embed, view=ChoicesView(results))

   @commands.hybrid_command(
      name="url",
      description="download from the given url",
   )
   async def url(self, context: Context, *, albumid: str) -> None:
      """
      :param context: The application command context.
      """


      embed = discord.Embed(
         description=f"awaiting getting album {albumid}",
         color=0xBEBEFE,
      )

      msg = await context.send(embed=embed)

      p = PendingAlbum(albumid, self.client, self.config, self.database)
      resolved_album = await p.resolve()

      album_name = resolved_album.meta.album

      await msg.edit(embed=discord.Embed(
         description=f"Requested album is: {album_name}",
         color=0xBEBEFE,
      ))

      await resolved_album.rip()

      await msg.edit(embed=discord.Embed(
         description=f"Finished downloading {album_name}. Waiting for Import...",
         color=0xBEBEFE,
      ))

      # tbqh since we don't really need to know the inner workings the same way as streamrip,
      # fuck it... maybe just run a subroutine...?

      subprocess.run(["beet", "import", self.download_path, "-q"], check=True)

      await msg.edit(embed=discord.Embed(
         description=f"import of {album_name} finished!",
         color=0x9C84EF,
      ))
      await self.client.session.close()

# And then we finally add the cog to the bot so that it can load, unload, reload and use it's content.
async def setup(bot) -> None:
   await bot.add_cog(StreamripCog(bot))
