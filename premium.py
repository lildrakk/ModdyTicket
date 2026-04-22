import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import datetime

from cogs.version import OWNER_ID

PREMIUM_FILE = "premium.json"

# ============================
# CARGAR / GUARDAR JSON
# ============================

def load_premium():
    if not os.path.exists(PREMIUM_FILE):
        with open(PREMIUM_FILE, "w") as f:
            json.dump({}, f)
    with open(PREMIUM_FILE, "r") as f:
        return json.load(f)

def save_premium(data):
    with open(PREMIUM_FILE, "w") as f:
        json.dump(data, f, indent=4)

premium_data = load_premium()

# ============================
# PARSEADOR DE TIEMPO
# ============================

def parse_time(texto: str):
    texto = texto.lower().replace(" ", "")

    if texto in ["perm", "perma", "permanente"]:
        return None

    unidades = {
        "d": 86400,
        "h": 3600,
        "m": 2592000,
        "a": 31536000
    }

    numero = ""
    unidad = ""

    for c in texto:
        if c.isdigit():
            numero += c
        else:
            unidad += c

    if not numero or unidad not in unidades:
        return None

    return int(numero) * unidades[unidad]

# ============================
# FUNCIÓN GLOBAL PREMIUM
# ============================

def is_premium(user_id: int):
    user_id = str(user_id)
    if user_id not in premium_data:
        return False

    expira = premium_data[user_id]["expira"]
    if expira is None:
        return True

    ahora = int(datetime.datetime.utcnow().timestamp())
    return ahora < expira

# ============================
# LISTA DE COMANDOS PREMIUM
# ============================

PREMIUM_COMMANDS = [
    # EJEMPLO:
    # "ver_warns",
    # "verificacion_crear"
]

# ============================
# COG PREMIUM
# ============================

class Premium(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_expirations.start()

    # ============================
    # INTERCEPTAR TODOS LOS COMANDOS
    # ============================

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):

        if not interaction.type == discord.InteractionType.application_command:
            return

        comando = interaction.command.name

        if comando in PREMIUM_COMMANDS:
            if not is_premium(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Este comando es exclusivo para usuarios **Premium**.",
                    ephemeral=True
                )
                return

    # ============================
    # TAREA AUTOMÁTICA EXPIRACIONES
    # ============================

    @tasks.loop(minutes=1)
    async def check_expirations(self):
        ahora = int(datetime.datetime.utcnow().timestamp())
        expirados = []

        for user_id, info in premium_data.items():
            expira = info["expira"]
            if expira is not None and ahora >= expira:
                expirados.append(user_id)

        for user_id in expirados:
            usuario = self.bot.get_user(int(user_id))
            owner = self.bot.get_user(OWNER_ID)

            if usuario:
                try:
                    await usuario.send("⚠️ Tu **Premium** ha expirado.")
                except:
                    pass

            if owner:
                try:
                    await owner.send(f"⚠️ El Premium de **{usuario}** ha expirado.")
                except:
                    pass

            del premium_data[user_id]
            save_premium(premium_data)

    # ============================
    # /premium añadir
    # ============================

    @app_commands.command(name="premium_añadir", description="Añadir premium a un usuario.")
    async def premium_add(self, interaction: discord.Interaction, usuario: discord.User, tiempo: str):

        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ No tienes permiso.", ephemeral=True)

        segundos = parse_time(tiempo)
        ahora = int(datetime.datetime.utcnow().timestamp())
        expira = None if segundos is None else ahora + segundos

        premium_data[str(usuario.id)] = {"expira": expira}
        save_premium(premium_data)

        try:
            await usuario.send(f"🎉 ¡Has recibido **Premium**!\n⏳ Expira: {('Nunca' if expira is None else datetime.datetime.utcfromtimestamp(expira))}")
        except:
            pass

        try:
            await interaction.user.send(f"✔ Premium añadido a {usuario}.")
        except:
            pass

        await interaction.response.send_message(f"✔ Premium añadido a **{usuario}**.", ephemeral=True)

    # ============================
    # /premium quitar
    # ============================

    @app_commands.command(name="premium_quitar", description="Quitar premium a un usuario.")
    async def premium_remove(self, interaction: discord.Interaction, usuario: discord.User):

        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ No tienes permiso.", ephemeral=True)

        if str(usuario.id) in premium_data:
            del premium_data[str(usuario.id)]
            save_premium(premium_data)

            try:
                await usuario.send("⚠️ Tu Premium ha sido retirado.")
            except:
                pass

            await interaction.response.send_message(f"✔ Premium retirado a **{usuario}**.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ese usuario no tiene premium.", ephemeral=True)

    # ============================
    # /premium listar
    # ============================

    @app_commands.command(name="premium_listar", description="Lista todos los usuarios premium.")
    async def premium_list(self, interaction: discord.Interaction):

        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ No tienes permiso.", ephemeral=True)

        if not premium_data:
            return await interaction.response.send_message("No hay usuarios premium.", ephemeral=True)

        texto = "**Usuarios Premium:**\n\n"

        for user_id, info in premium_data.items():
            expira = info["expira"]
            usuario = self.bot.get_user(int(user_id))

            texto += f"👤 **{usuario}** — ID: `{user_id}`\n"
            texto += f"⏳ Expira: {'Nunca (Permanente)' if expira is None else datetime.datetime.utcfromtimestamp(expira)}\n\n"

        await interaction.response.send_message(texto, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Premium(bot))
