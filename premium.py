import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import datetime

from cogs.version import OWNER_ID

PREMIUM_FILE = "premium.json"
COLOR = discord.Color(0x0A3D62)

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
    "botinfo",
    # "verificacion",
    # "backup_restaurar",
]

# ============================
# EMBEDS PREMIUM
# ============================

def embed_premium_required():
    embed = discord.Embed(
        title="⭐ Acceso Premium Requerido",
        description=(
            "Este comando forma parte de las **funciones avanzadas** de ModdyBot.\n\n"
            "Para utilizarlo necesitas tener **Premium activo**.\n"
            "Obtén acceso a:\n"
            "• Backups avanzados\n"
            "• Restauración completa\n"
            "• Comandos exclusivos\n"
            "• Cooldowns reducidos\n"
            "• Funciones especiales del sistema\n\n"
            "Si deseas más información, contacta con el propietario del bot."
        ),
        color=COLOR
    )
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/1828/1828884.png")
    embed.set_footer(text="ModdyBot • Sistema Premium")
    return embed

def embed_premium_granted(usuario, expira):
    embed = discord.Embed(
        title="🎉 ¡Has recibido Premium!",
        description=(
            f"{usuario.mention}, ahora formas parte de los **usuarios Premium**.\n\n"
            "Disfruta de:\n"
            "• Backups ilimitados\n"
            "• Restauración avanzada\n"
            "• Cooldowns reducidos\n"
            "• Funciones exclusivas\n"
            "• Prioridad en el sistema\n\n"
            f"⏳ **Expira:** {'Nunca (Permanente)' if expira is None else f'<t:{expira}:F>'}"
        ),
        color=COLOR
    )
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/1828/1828884.png")
    embed.set_footer(text="ModdyBot • Sistema Premium")
    return embed

def embed_premium_removed(usuario):
    embed = discord.Embed(
        title="⚠️ Premium retirado",
        description=(
            f"{usuario.mention}, tu acceso **Premium** ha sido retirado.\n\n"
            "Si crees que esto es un error, contacta con el propietario del bot."
        ),
        color=discord.Color.red()
    )
    embed.set_footer(text="ModdyBot • Sistema Premium")
    return embed

def embed_premium_expired(usuario):
    embed = discord.Embed(
        title="⏳ Premium expirado",
        description=(
            f"{usuario.mention}, tu suscripción **Premium** ha expirado.\n\n"
            "Puedes renovarla para seguir disfrutando de las funciones avanzadas."
        ),
        color=discord.Color.orange()
    )
    embed.set_footer(text="ModdyBot • Sistema Premium")
    return embed

# ============================
# COG PREMIUM
# ============================

class Premium(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_expirations.start()

    # ============================
    # BLOQUEAR COMANDOS PREMIUM ANTES DE EJECUTARSE
    # ============================

    async def interaction_check(self, interaction: discord.Interaction) -> bool:

        # Solo slash commands
        if interaction.type != discord.InteractionType.application_command:
            return True

        comando = interaction.command.name

        # Si NO es premium → permitir
        if comando not in PREMIUM_COMMANDS:
            return True

        # Si es premium → permitir
        if is_premium(interaction.user.id):
            return True

        # Si NO es premium → bloquear
        if not interaction.response.is_done():
            await interaction.response.send_message(
                embed=embed_premium_required(),
                ephemeral=True
            )

        return False  # BLOQUEA EL COMANDO

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
                    await usuario.send(embed=embed_premium_expired(usuario))
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
    # /premium_añadir
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
            await usuario.send(embed=embed_premium_granted(usuario, expira))
        except:
            pass

        await interaction.response.send_message(
            f"✔ Premium añadido a **{usuario}**.",
            ephemeral=True
        )

    # ============================
    # /premium_quitar
    # ============================

    @app_commands.command(name="premium_quitar", description="Quitar premium a un usuario.")
    async def premium_remove(self, interaction: discord.Interaction, usuario: discord.User):

        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ No tienes permiso.", ephemeral=True)

        if str(usuario.id) in premium_data:
            del premium_data[str(usuario.id)]
            save_premium(premium_data)

            try:
                await usuario.send(embed=embed_premium_removed(usuario))
            except:
                pass

            await interaction.response.send_message(
                f"✔ Premium retirado a **{usuario}**.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Ese usuario no tiene premium.", ephemeral=True)

    # ============================
    # /premium_listar
    # ============================

    @app_commands.command(name="premium_listar", description="Lista todos los usuarios premium.")
    async def premium_list(self, interaction: discord.Interaction):

        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ No tienes permiso.", ephemeral=True)

        if not premium_data:
            return await interaction.response.send_message("No hay usuarios premium.", ephemeral=True)

        embed = discord.Embed(
            title="⭐ Usuarios Premium",
            color=COLOR
        )

        for user_id, info in premium_data.items():
            expira = info["expira"]
            usuario = self.bot.get_user(int(user_id))

            embed.add_field(
                name=f"👤 {usuario}",
                value=f"🆔 `{user_id}`\n⏳ Expira: {'Nunca (Permanente)' if expira is None else f'<t:{expira}:F>'}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Premium(bot)) 
