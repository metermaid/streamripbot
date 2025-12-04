""""
a very silly cog to get things from streamrip. mostly quboz, but also soundcloud tracks in FLAC LOL
"""
import logging
import os
import subprocess
from dataclasses import dataclass

from discord import app_commands
from discord import Interaction, Embed, Message, SelectOption
from discord.ext import commands
from discord.ext.commands import Context
from discord.ui import Select, View

from streamrip.client import QobuzClient, SoundcloudClient
from streamrip.config import Config
from streamrip.media import PendingSingle, PendingAlbum, PendingPlaylist, PendingArtist
from streamrip.db import Database,Dummy

EMOJI_LIST = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
LOGGER = logging.getLogger("discord_bot")

DOWNLOADS_PATH = os.getenv("DOWNLOADS_PATH")
CONFIG_PATH = os.getenv("CONFIG_PATH")
STREAMRIP_CONFIG_PATH = os.getenv("STREAMRIP_CONFIG_PATH")
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
      config = Config(STREAMRIP_CONFIG_PATH)
      self.config = config
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
            flatResults.extend(result.get("data") or result.get("collection"))

         return [SearchResult(str(result['id'])[0:100], # lord wtf soundcloud...
                              result.get("title") or result.get("name") or "Unknown",
                              result.get("link") or result.get("permalink_url"),
                              result.get("performer", {}).get("name") or result.get("artist", {}).get("name") or result.get("artist") or "") for result in flatResults]

   async def download(self, id: int, mediaType: str, msg: Message) -> None:
      """
      :param context: The application command context.
      """
      if not self.client.logged_in:
         await self.client.login()

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
         title = resolved_media.name
      elif mediaType == "artist":
         title = resolved_media.name
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

      beets_cmd = ["beet", "-c", CONFIG_PATH, "import", DOWNLOADS_PATH]

      if mediaType == "track":
         beets_cmd.append("-s")

      subprocess.run(beets_cmd, check=True)

      await msg.edit(embed=Embed(
         description=f"Import of '{title}' finished!",
         color=0x9C84EF,
      ))

class QobuzInterface(StreamripInterface):
   def __init__(self) -> None:
      super().__init__()
      self.client = QobuzClient(self.config)

class SoundcloudInterface(StreamripInterface):
   def __init__(self) -> None:
      super().__init__()
      self.client = SoundcloudClient(self.config)

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
      self.qobuzinterface = QobuzInterface()
      self.soundcloudinterface = SoundcloudInterface()

   @commands.hybrid_command(
      name="track",
      description="searches and downloads tracks",
   )
   async def track(self, context: Context, *, query: str) -> None:
      mediaType = "track"
      results = await self.qobuzinterface.search(context=context, mediaType=mediaType, query=query)
      await self.printSearchResults(query=query, results=results, mediaType=mediaType, context=context, interface=self.qobuzinterface)

   @commands.hybrid_command(
      name="album",
      description="searches and downloads albums",
   )
   async def album(self, context: Context, *, query: str) -> None:
      mediaType = "album"
      results = await self.qobuzinterface.search(context=context, mediaType=mediaType, query=query)
      await self.printSearchResults(query=query, results=results, mediaType=mediaType, context=context, interface=self.qobuzinterface)

   @commands.hybrid_command(
      name="playlist",
      description="searches and downloads playlists",
   )
   async def playlist(self, context: Context, *, query: str) -> None:
      mediaType = "playlist"
      results = await self.qobuzinterface.search(context=context, mediaType=mediaType, query=query)
      await self.printSearchResults(query=query, results=results, mediaType=mediaType, context=context, interface=self.qobuzinterface)

   @commands.hybrid_command(
      name="artist",
      description="searches and downloads artists",
   )
   async def artist(self, context: Context, *, query: str) -> None:
      mediaType = "artist"
      results = await self.qobuzinterface.search(context=context, mediaType=mediaType, query=query)
      await self.printSearchResults(query=query, results=results, mediaType=mediaType, context=context, interface=self.qobuzinterface)

   @commands.hybrid_command(
      name="soundcloud_track",
      description="searches and downloads soundcloud tracks",
   )
   async def soundcloud_track(self, context: Context, *, query: str) -> None:
      mediaType = "track"
      results = await self.soundcloudinterface.search(context=context, mediaType=mediaType, query=query)
      await self.printSearchResults(query=query, results=results, mediaType=mediaType, context=context, interface=self.soundcloudinterface)

   @commands.hybrid_command(
      name="soundcloud_playlist",
      description="searches and downloads soundcloud playlist",
   )
   async def soundcloud_playlist(self, context: Context, *, query: str) -> None:
      mediaType = "playlist"
      results = await self.soundcloudinterface.search(context=context, mediaType=mediaType, query=query)
      await self.printSearchResults(query=query, results=results, mediaType=mediaType, context=context, interface=self.soundcloudinterface)

   @commands.hybrid_command(
      name="idlookup",
      description="when you know the specific id for quboz",
   )
   @app_commands.describe(id="The id of the media", mediatype="the type of media")
   async def idlookup(self, context: Context, id: int, mediatype: str) -> None:
      embed = Embed(
         title=f"Downloading {mediatype} with ID: {id}",
         description=f"Waiting...",
         color=0xBEBEFE
      )
      msg = await context.send(embed=embed)
      await self.qobuzinterface.download(id=id, mediaType=mediatype, msg=msg)

   async def printSearchResults(self, query: str, results: list[SearchResult], mediaType: str, context: Context, interface: StreamripInterface) -> None:
      embed = Embed(
         title=f"Search Results for '{query}'",
         description=f"Returned {len(results)} results:",
         color=0xBEBEFE
      )
      for index,result in enumerate(results):
         embed.add_field(name=f"{EMOJI_LIST[index]} {result.title}", value=f"{result.artist} (URL: {result.link})", inline=False)

      view = View()
      view.add_item(Choices(titles=results, mediaType=mediaType, interface=interface))

      await context.send(embed=embed, view=view)

# And then we finally add the cog to the bot so that it can load, unload, reload and use it's content.
async def setup(bot) -> None:
   await bot.add_cog(StreamripCog(bot))
