import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# IMPORTANTE: importar la View persistente
from cogs.giveaways import GiveawayView

# -----------------------------
# SISTEMA DE VERSIONES
# -----------------------------
from cogs.version import load_versions, OWNER_ID

BOT_VERSION = "v1.1.2"  # Versión real del código


def version_permitida(user_id: int):
    versions = load_versions()
    if user_id == OWNER_ID:
        return versions["dev"]
    return versions["public"]


# -----------------------------
# SISTEMA DE MÓDULOS POR VERSIÓN
# -----------------------------
VERSION_NEW = {
    "v1.0": [
        "antibots",
        "antiflood",
        "antilinks",
        "antiraid",
        "info",
        "logs",
        "moderacion",
        "securityscan",
        "utilidad",
        "verification",
        "version",
        "welcome_dm"
    ],

    "v1.1": ["antialts",
             "blacklistglobal",
             "blacklistserver"
    ],
    "v1.1.2": ["antiping",
               "statuspanel",
               "giveaways",
               "premium",
               "backups",
    ]
}

VERSION_REMOVED = {}

def get_modules_for_version(version):
    versions = list(VERSION_NEW.keys())
    index = versions.index(version)

    modules = []

    for i in range(index + 1):
        modules.extend(VERSION_NEW[versions[i]])

    for i in range(index + 1):
        removed = VERSION_REMOVED.get(versions[i], [])
        for r in removed:
            if r in modules:
                modules.remove(r)

    return modules


# -----------------------------
# Cargar variables del .env
# -----------------------------
load_dotenv()


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=";",
            intents=discord.Intents.all()
        )

    async def setup_hook(self):

        versions = load_versions()
        owner_version = versions["dev"]

        print(f"\n🔧 Cargando módulos para versión {owner_version}...\n")

        modules = get_modules_for_version(owner_version)

        for module in modules:
            try:
                await self.load_extension(f"cogs.{module}")
                print(f"✔ Cargado: {module}.py")
            except Exception as e:
                print(f"❌ Error cargando {module}: {e}")

        print("\n✅ Módulos cargados correctamente.\n")

        print("==============================")
        print(f"📦 Versión del código: {BOT_VERSION}")
        print(f"🌍 Versión pública: {versions['public']}")
        print(f"🛠️ Versión dev: {versions['dev']}")
        print("==============================\n")

        # -----------------------------------------
        # NUEVO: DETECTOR DE ERRORES EN SLASH COMMANDS
        # -----------------------------------------
        print("\n🔍 Verificando comandos slash...\n")

        try:
            synced = await self.tree.sync()
            print(f"🌐 Comandos sincronizados: {len(synced)}")
        except Exception as e:
            print("❌ ERROR SINCRONIZANDO COMANDOS:")
            print(e)

        print("\n🔍 Revisando errores internos de comandos...\n")

        for cmd in self.tree.walk_commands():
            try:
                _ = cmd.name  # fuerza evaluación
            except Exception as e:
                print(f"❌ ERROR en el comando {cmd.name}: {e}")


    # -----------------------------------------
    # FUNCIÓN NUEVA: RECARGAR MÓDULOS EN CALIENTE
    # -----------------------------------------
    async def load_modules_for_version(self):
        versions = load_versions()
        owner_version = versions["dev"]

        print(f"\n🔥 Recargando módulos para versión {owner_version}...\n")

        # Descargar módulos actuales
        for ext in list(self.extensions.keys()):
            try:
                await self.unload_extension(ext)
                print(f"⏏️ Descargado: {ext}")
            except Exception as e:
                print(f"❌ Error descargando {ext}: {e}")

        # Cargar módulos nuevos
        modules = get_modules_for_version(owner_version)

        for module in modules:
            try:
                await self.load_extension(f"cogs.{module}")
                print(f"✔ Cargado: {module}.py")
            except Exception as e:
                print(f"❌ Error cargando {module}: {e}")

        try:
            synced = await self.tree.sync()
            print(f"🌐 Comandos sincronizados: {len(synced)}")
        except Exception as e:
            print(f"❌ Error al sincronizar comandos: {e}")

        print("\n✅ Módulos recargados correctamente.\n")


bot = Bot()


@bot.event
async def on_ready():
    print(f"🤖 Bot conectado como {bot.user}")

    # 🔄 Registrar botón persistente
    bot.add_view(GiveawayView(giveaway_id=None))

    try:
        synced = await bot.tree.sync()
        print(f"📘 Slash commands sincronizados: {len(synced)}")
    except Exception as e:
        print(f"❌ Error al sincronizar comandos: {e}")


TOKEN = os.getenv("TOKEN")

if not TOKEN:
    print("❌ ERROR: No se encontró la variable TOKEN en el .env")
else:
    print("✔ TOKEN encontrado, iniciando bot...")

bot.run(TOKEN)
