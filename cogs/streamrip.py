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
import logging
import os
import subprocess
from dataclasses import dataclass

from discord import Interaction, Embed, Message, SelectOption
from discord.ext import commands
from discord.ext.commands import Context
from discord.ui import Select, View

from streamrip.client import DeezerClient
from streamrip.config import Config
from streamrip.media import PendingSingle, PendingAlbum, PendingPlaylist, PendingArtist
from streamrip.db import Database,Dummy

EMOJI_LIST = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
LOGGER = logging.getLogger("discord_bot")

DOWNLOADS_PATH = os.getenv("DOWNLOADS_PATH")
CONFIG_PATH = os.getenv("CONFIG_PATH")
QUALITY = int(os.getenv("QUALITY"))
ARL = os.getenv("ARL")

@dataclass
class SearchResult:
    id: int
    title: str
    link: str
    artist: str

class StreamripInterface():
   def __init__(self) -> None:
      config = Config.defaults()
      config.session.database.downloads_enabled = False
      config.session.downloads.folder = DOWNLOADS_PATH
      config.session.deezer.quality = QUALITY
      config.session.deezer.arl = ARL # loading it all here because i can't be bothered to properly load the config lol
      self.config = config
      self.client = DeezerClient(config)
      self.database = Database(Dummy(),Dummy())

   async def search(self, context: Context, mediaType: str, query: str) -> list[SearchResult]:
      if not self.client.logged_in:
         await self.client.login()

      rawResults = await self.client.search(mediaType, query, limit=9)

      if len(rawResults) == 0:
         embed = Embed(
            title="Search Error",
            description=f"Unable to get any results for query: {query}",
            color=0xE02B2B,
         )
         await context.send(embed=embed)
      else:
         flatResults = []
         for result in rawResults:
            flatResults.extend(result["data"])

         return [SearchResult(result["id"],
                              result.get("title") or result.get("name") or "Unknown",
                              result["link"],
                              result.get("performer", {}).get("name") or result.get("artist", {}).get("name") or result.get("artist") or "") for result in flatResults]

   async def download(self, id: int, mediaType: str,msg: Message) -> None:
      """
      :param context: The application command context.
      """
      if not self.client.logged_in:
         await self.client.login()

      LOGGER.info(mediaType)

      if mediaType == "track":
         p = PendingSingle(id, self.client, self.config, self.database)
      elif mediaType == "album":
         p = PendingAlbum(id, self.client, self.config, self.database)
      elif mediaType == "playlist":
         p = PendingPlaylist(id, self.client, self.config, self.database)
      elif mediaType == "artist":
         p = PendingArtist(id, self.client, self.config, self.database)
      else:
         raise Exception(mediaType)

      resolved_media = await p.resolve()
      if mediaType == "track":
         title = resolved_media.meta.title
      elif mediaType == "album":
         title = resolved_media.meta.album
      elif mediaType == "playlist":
         title = resolved_media.meta.name
      elif mediaType == "artist":
         title = resolved_media.meta.name
      else:
         raise Exception(mediaType)

      await msg.edit(embed=Embed(
         description=f"Requested {mediaType} is: {title}",
         color=0xBEBEFE,
      ))

      await resolved_media.rip() #rip it...

      await msg.edit(embed=Embed(
         description=f"Finished downloading '{title}'. Waiting for Import...",
         color=0xBEBEFE,
      ))

      # tbqh since we don't really need to know the inner workings the same way as streamrip,
      # fuck it... maybe just run a subroutine...?

      subprocess.run(["beet", "-c", CONFIG_PATH, "import", DOWNLOADS_PATH], check=True)

      await msg.edit(embed=Embed(
         description=f"Import of '{title}' finished!",
         color=0x9C84EF,
      ))

class Choices(Select):
   def __init__(self, titles: list[SearchResult], mediaType: str, interface: StreamripInterface):
      self.titles = titles
      self.mediaType = mediaType
      self.interface = interface
      options = [SelectOption(label=result.title, value=result.id, description=f"{result.artist}", emoji=EMOJI_LIST[index]) for index,result in enumerate(titles)]
      super().__init__(
         placeholder="Choose which option to download",
         min_values=1,
         max_values=1,
         options=options
      )

   async def callback(self, interaction: Interaction):
      id = self.values[0]
      await interaction.response.defer()
      msg = await interaction.followup.send(embed=Embed(
         description=f"Awaiting getting media with the id: {id}",
         color=0xBEBEFE
      ))
      await self.interface.download(id=id,mediaType=self.mediaType, msg=msg)

class StreamripCog(commands.Cog, name="streamrip"):
   def __init__(self, bot) -> None:
      self.bot = bot
      self.interface = StreamripInterface()

   @commands.hybrid_command(
      name="track",
      description="searches and downloads tracks",
   )
   async def track(self, context: Context, *, query: str) -> None:
      mediaType = "track"
      results = await self.interface.search(context=context, mediaType=mediaType, query=query)
      await self.printSearchResults(query=query, results=results, mediaType=mediaType, context=context)

   @commands.hybrid_command(
      name="album",
      description="searches and downloads albums",
   )
   async def album(self, context: Context, *, query: str) -> None:
      mediaType = "album"
      results = await self.interface.search(context=context, mediaType=mediaType, query=query)
      await self.printSearchResults(query=query, results=results, mediaType=mediaType, context=context)

   @commands.hybrid_command(
      name="playlist",
      description="searches and downloads playlists",
   )
   async def playlist(self, context: Context, *, query: str) -> None:
      mediaType = "playlist"
      results = await self.interface.search(context=context, mediaType=mediaType, query=query)
      await self.printSearchResults(query=query, results=results, mediaType=mediaType, context=context)

   @commands.hybrid_command(
      name="artist",
      description="searches and downloads artists",
   )
   async def artist(self, context: Context, *, query: str) -> None:
      mediaType = "artist"
      results = await self.interface.search(context=context, mediaType=mediaType, query=query)
      await self.printSearchResults(query=query, results=results, mediaType=mediaType, context=context)
   
   async def printSearchResults(self, query: str, results: list[SearchResult], mediaType: str, context: Context) -> None:
      embed = Embed(
         title=f"Search Results for '{query}'",
         description=f"Returned {len(results)} results:",
         color=0xBEBEFE
      )
      for index,result in enumerate(results):
         embed.add_field(name=f"{EMOJI_LIST[index]} {result.title}", value=f"{result.artist} (URL: {result.link})", inline=False)

      view = View()
      view.add_item(Choices(titles=results, mediaType=mediaType, interface=self.interface))
   
      await context.send(embed=embed, view=view)

# And then we finally add the cog to the bot so that it can load, unload, reload and use it's content.
async def setup(bot) -> None:
   await bot.add_cog(StreamripCog(bot))
