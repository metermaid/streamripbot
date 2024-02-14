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

import discord
from discord.ext import commands
from discord.ext.commands import Context

from streamrip.client import DeezerClient
from streamrip.config import Config
from streamrip.media import PendingAlbum
from streamrip.db import Database,Dummy

import subprocess

# Here we name the cog and create a new class for the cog.
class Streamrip(commands.Cog, name="streamrip"):
   def __init__(self, bot) -> None:
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
      name="url",
      description="download from the given url",
   )
   async def url(self, context: Context, *, albumid: str) -> None:
      """
      :param context: The application command context.
      """

      if not self.client.logged_in:
         await self.client.login()

      embed = discord.Embed(
         description=f"awaiting getting album {albumid}",
         color=0xBEBEFE,
      )

      await context.send(embed=embed)

      p = PendingAlbum(albumid, self.client, self.config, self.database)
      resolved_album = await p.resolve()

      album_name = resolved_album.meta.album

      embed = discord.Embed(
         description=f"Requested album is: {album_name}",
         color=0xBEBEFE,
      )
      await context.send(embed=embed)

      await resolved_album.rip()

      embed = discord.Embed(
         description=f"Finished downloading {album_name}. Waiting for Import...",
         color=0xBEBEFE,
      )
      await context.send(embed=embed)

      await self.client.session.close()


      # tbqh since we don't really need to know the inner workings the same way as streamrip,
      # fuck it... maybe just run a subroutine...?

      subprocess.run(["beet", "import", self.download_path, "-q"], check=True)

      embed = discord.Embed(
         description=f"import of {album_name} finished!",
         color=0xBEBEFE,
      )
      await context.send(embed=embed)

# And then we finally add the cog to the bot so that it can load, unload, reload and use it's content.
async def setup(bot) -> None:
   await bot.add_cog(Streamrip(bot))
