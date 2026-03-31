from dotenv import load_dotenv
import os
import discord
from discord.ext import commands
import json
import asyncio
import traceback

# IMPORTAR LOS BOTONES PARA LA VIEW PERSISTENTE
from cogs.tickets import BotonReclamar, BotonCerrarTicket, BotonNotificar

load_dotenv()
TOKEN = os.getenv("TOKEN")

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

intents = discord.Intents.all()

# ============================================================
#   VISTA PERSISTENTE PARA QUE LOS BOTONES NO MUERAN
# ============================================================

class VistaTicketPersistente(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BotonReclamar())
        self.add_item(BotonCerrarTicket())
        self.add_item(BotonNotificar())

# ============================================================
#   BOT PRINCIPAL
# ============================================================

class TicketBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=";",
            intents=intents
        )
        self.remove_command("help")

    async def setup_hook(self):

        # Cargar COGS
        cogs = [
            "cogs.tickets",
            "cogs.panels",
            "cogs.logs",
            "cogs.config"
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f"📦 COG cargado: {cog}")
            except Exception:
                print(f"\n❌ ERROR cargando {cog}:")
                traceback.print_exc()

        # Registrar vistas persistentes de paneles
        try:
            from cogs.panels import cargar_paneles, VistaPanel, VistaPanelMenu
            data = cargar_paneles()

            for guild_id, guild_panels in data.items():
                for panel_id, panel in guild_panels.items():

                    self.add_view(VistaPanel(panel_id, panel))

                    if "menu" in panel and panel["menu"]:
                        self.add_view(VistaPanelMenu(panel_id, panel["menu"]))

            print("🛠️ Vistas persistentes de paneles registradas.")
        except Exception:
            print("❌ Error registrando vistas de paneles:")
            traceback.print_exc()

        # REGISTRAR LA VISTA PERSISTENTE DE TICKETS
        try:
            self.add_view(VistaTicketPersistente())
            print("🛠️ VistaTicket persistente registrada.")
        except Exception:
            print("❌ Error registrando VistaTicket persistente:")
            traceback.print_exc()

        # Sincronizar comandos
        try:
            synced = await self.tree.sync()
            print(f"🪄 {len(synced)} comandos sincronizados.")
        except Exception:
            print("❌ Error sincronizando comandos:")
            traceback.print_exc()


bot = TicketBot()

# ============================================================
#   EVENTOS
# ============================================================

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

@bot.event
async def on_command_error(ctx, error):
    print("\n❌ ERROR EN COMANDO:")
    traceback.print_exc()
    try:
        await ctx.reply("❌ Ocurrió un error ejecutando este comando.")
    except:
        pass

@bot.tree.error
async def on_app_command_error(interaction, error):
    print("\n❌ ERROR EN SLASH COMMAND:")
    traceback.print_exc()
    try:
        await interaction.response.send_message(
            "❌ Ocurrió un error ejecutando este comando.",
            ephemeral=True
        )
    except:
        pass

@bot.event
async def on_error(event, *args, **kwargs):
    print(f"\n❌ ERROR EN EVENTO: {event}")
    traceback.print_exc()

# ============================================================
#   MAIN
# ============================================================

async def main():
    try:
        await bot.start(TOKEN)
    except Exception:
        print("\n❌ ERROR AL INICIAR EL BOT:")
        traceback.print_exc()

asyncio.run(main())
