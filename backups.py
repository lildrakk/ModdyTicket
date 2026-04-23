import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime
import aiohttp

from cogs.premium import is_premium
from cogs.logs import UltraLogs

BACKUP_FILE = "backups.json"
COLOR = discord.Color(0x0A3D62)

# ============================
# CARGAR / GUARDAR JSON
# ============================

def load_backups():
    if not os.path.exists(BACKUP_FILE):
        with open(BACKUP_FILE, "w") as f:
            json.dump({}, f)
    with open(BACKUP_FILE, "r") as f:
        return json.load(f)

def save_backups(data):
    with open(BACKUP_FILE, "w") as f:
        json.dump(data, f, indent=4)

backups = load_backups()

# ============================
# COOLDOWN INTEGRADO
# ============================

COOLDOWN_FILE = "cooldowns.json"

def load_cooldowns():
    if not os.path.exists(COOLDOWN_FILE):
        with open(COOLDOWN_FILE, "w") as f:
            json.dump({}, f)
    with open(COOLDOWN_FILE, "r") as f:
        return json.load(f)

def save_cooldowns(data):
    with open(COOLDOWN_FILE, "w") as f:
        json.dump(data, f, indent=4)

cooldowns = load_cooldowns()

def can_create_backup(user_id: int):
    user_id = str(user_id)
    ahora = int(datetime.datetime.utcnow().timestamp())

    # Si no tiene registros → puede crear
    if user_id not in cooldowns:
        return True, None

    data = cooldowns[user_id]
    ultimo = data.get("last_backup", 0)

    # ============================
    # PREMIUM
    # ============================

    if is_premium(int(user_id)):
        # Cooldown de 5 minutos
        if ahora - ultimo < 300:
            faltan = 300 - (ahora - ultimo)
            minutos = int(faltan / 60) + 1
            return False, (
                f"🛠️ El sistema está procesando tareas internas.\n"
                f"Podrás crear otro backup en **{minutos} minutos**."
            )
        return True, None

    # ============================
    # FREE
    # ============================

    # Cooldown de 3 días
    if ahora - ultimo < 259200:
        faltan = 259200 - (ahora - ultimo)
        dias = int(faltan / 86400)
        horas = int((faltan % 86400) / 3600)

        return False, (
            "⏳ Como usuario **Free**, solo puedes crear **1 backup cada 3 días**.\n"
            f"Te faltan **{dias} días y {horas} horas**."
        )

    return True, None

def register_backup(user_id: int):
    user_id = str(user_id)
    ahora = int(datetime.datetime.utcnow().timestamp())

    if user_id not in cooldowns:
        cooldowns[user_id] = {
            "last_backup": ahora
        }
    else:
        cooldowns[user_id]["last_backup"] = ahora

    save_cooldowns(cooldowns)

# ============================
# AUTO-LIMPIEZA DE BACKUPS
# ============================

async def auto_cleanup(interaction, logs_cog: UltraLogs):
    """
    Borra backups antiguos si hay demasiados.
    Envía log al canal configurado.
    """

    MAX_BACKUPS = 15  # límite por usuario

    user_id = str(interaction.user.id)
    user_backups = [name for name, data in backups.items() if data["created_by"] == interaction.user.id]

    if len(user_backups) <= MAX_BACKUPS:
        return

    # Ordenar por fecha (más antiguos primero)
    user_backups.sort(key=lambda n: backups[n]["created_at"])

    eliminar = len(user_backups) - MAX_BACKUPS

    for i in range(eliminar):
        nombre = user_backups[i]
        data = backups[nombre]

        # Enviar log
        guild = interaction.guild
        embed = discord.Embed(
            title="🗑️ Backup eliminado automáticamente",
            description=(
                "Para mantener el sistema estable, ModdyBot ha eliminado un backup antiguo.\n\n"
                f"📦 **Nombre:** `{nombre}`\n"
                f"👤 **Creador:** <@{data['created_by']}>\n"
                f"📅 **Fecha:** <t:{data['created_at']}:F>\n\n"
                "Esta acción se realizó automáticamente para optimizar el rendimiento."
            ),
            color=COLOR
        )

        try:
            await logs_cog.send_log(guild, embed, "server_update")
        except:
            pass

        del backups[nombre]

    save_backups(backups)

# ============================
# SELECT PARA CREAR BACKUP
# ============================

class BackupSelect(discord.ui.Select):
    def __init__(self):
        opciones = [
            discord.SelectOption(label="Roles", value="roles", emoji="🧩"),
            discord.SelectOption(label="Canales", value="canales", emoji="📁"),
            discord.SelectOption(label="Categorías", value="categorias", emoji="🗂️"),
            discord.SelectOption(label="Emojis", value="emojis", emoji="🎨"),
            discord.SelectOption(label="Stickers", value="stickers", emoji="🪅"),
        ]

        super().__init__(
            placeholder="Selecciona qué quieres guardar...",
            min_values=1,
            max_values=5,
            options=opciones
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.seleccion = self.values

        embed = discord.Embed(
            title="📦 Componentes seleccionados",
            description="Pulsa **Crear Backup** para continuar.",
            color=COLOR
        )
        embed.add_field(name="Seleccionado:", value="\n".join([f"• {v}" for v in self.values]))
        embed.set_footer(text="ModdyBot • Sistema de Backups")

        await interaction.response.send_message(embed=embed, ephemeral=True)

class BackupView(discord.ui.View):
    def __init__(self, nombre):
        super().__init__(timeout=120)
        self.nombre = nombre
        self.seleccion = []
        self.add_item(BackupSelect())

    @discord.ui.button(label="Crear Backup", style=discord.ButtonStyle.green, emoji="📦")
    async def crear(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not self.seleccion:
            return await interaction.response.send_message(
                "❌ Debes seleccionar al menos un componente.",
                ephemeral=True
            )

        puede, razon = can_create_backup(interaction.user.id)
        if not puede:
            return await interaction.response.send_message(razon, ephemeral=True)

        guild = interaction.guild

        # ============================
        # GUARDAR BACKUP
        # ============================

        data = {
            "guild_id": guild.id,
            "guild_name": guild.name,
            "created_by": interaction.user.id,
            "created_at": int(datetime.datetime.utcnow().timestamp()),
            "components": self.seleccion,
            "data": {}
        }

        # ROLES
        if "roles" in self.seleccion:
            roles_data = []
            for r in guild.roles:
                roles_data.append({
                    "name": r.name,
                    "color": r.color.value,
                    "hoist": r.hoist,
                    "mentionable": r.mentionable,
                    "position": r.position
                })
            data["data"]["roles"] = roles_data

        # CATEGORÍAS
        if "categorias" in self.seleccion:
            categorias = []
            for c in guild.categories:
                categorias.append({
                    "name": c.name,
                    "position": c.position
                })
            data["data"]["categorias"] = categorias

        # CANALES
        if "canales" in self.seleccion:
            canales = []
            for ch in guild.channels:
                if isinstance(ch, discord.TextChannel):
                    tipo = "texto"
                elif isinstance(ch, discord.VoiceChannel):
                    tipo = "voz"
                elif isinstance(ch, discord.ForumChannel):
                    tipo = "foro"
                elif isinstance(ch, discord.StageChannel):
                    tipo = "stage"
                elif isinstance(ch, discord.CategoryChannel):
                    continue
                else:
                    tipo = "otro"

                canales.append({
                    "name": ch.name,
                    "type": tipo,
                    "topic": getattr(ch, "topic", None),
                    "nsfw": getattr(ch, "nsfw", False),
                    "slowmode": getattr(ch, "slowmode_delay", 0),
                    "bitrate": getattr(ch, "bitrate", None),
                    "user_limit": getattr(ch, "user_limit", None),
                    "category": ch.category.name if ch.category else None
                })

            data["data"]["canales"] = canales

        # EMOJIS
        if "emojis" in self.seleccion:
            emojis = []
            for e in guild.emojis:
                emojis.append({
                    "name": e.name,
                    "url": str(e.url)
                })
            data["data"]["emojis"] = emojis

        # STICKERS
        if "stickers" in self.seleccion:
            stickers = []
            for s in guild.stickers:
                stickers.append({
                    "name": s.name,
                    "description": s.description,
                    "format": s.format.name,
                    "url": str(s.url)
                })
            data["data"]["stickers"] = stickers

        backups[self.nombre] = data
        save_backups(backups)

        register_backup(interaction.user.id)

        # AUTO-LIMPIEZA
        logs_cog = interaction.client.get_cog("UltraLogs")
        await auto_cleanup(interaction, logs_cog)

        embed = discord.Embed(
            title="🎉 Backup creado con éxito",
            description=f"El backup **{self.nombre}** ha sido guardado correctamente.",
            color=COLOR
        )
        embed.add_field(name="Componentes:", value="\n".join([f"• {v}" for v in self.seleccion]))
        embed.set_footer(text="ModdyBot • Sistema de Backups")

        await interaction.response.send_message(embed=embed, ephemeral=True)



# ============================
# FUNCIÓN DE RESTAURACIÓN
# ============================

async def restore_backup(interaction, nombre, data):

    guild = interaction.guild
    canal_log = interaction.channel  # Canal donde se ejecuta el comando
    no_restaurado = []

    await canal_log.send("🛠️ **Iniciando restauración del backup...**\nEste canal no será borrado.")

    # ============================
    # BORRAR CANALES (excepto este)
    # ============================

    await canal_log.send("🧹 **Eliminando canales...**")

    for ch in guild.channels:
        if ch.id == canal_log.id:
            continue
        try:
            await ch.delete()
            await canal_log.send(f"• Canal eliminado: `{ch.name}`")
        except:
            await canal_log.send(f"• ❌ No se pudo eliminar: `{ch.name}`")

    # ============================
    # BORRAR CATEGORÍAS
    # ============================

    await canal_log.send("\n🧱 **Eliminando categorías...**")

    for c in guild.categories:
        try:
            await c.delete()
            await canal_log.send(f"• Categoría eliminada: `{c.name}`")
        except:
            await canal_log.send(f"• ❌ No se pudo eliminar: `{c.name}`")

    # ============================
    # BORRAR ROLES
    # ============================

    await canal_log.send("\n🎭 **Eliminando roles...**")

    bot_role = guild.me.top_role.position
    for r in guild.roles:
        if r.position < bot_role:
            try:
                await r.delete()
                await canal_log.send(f"• Rol eliminado: `{r.name}`")
            except:
                await canal_log.send(f"• ❌ No se pudo eliminar: `{r.name}`")

    # ============================
    # RESTAURAR CATEGORÍAS
    # ============================

    await canal_log.send("\n🗂️ **Restaurando categorías...**")

    categorias_creadas = {}

    if "categorias" in data["components"]:
        for c in data["data"]["categorias"]:
            try:
                nueva = await guild.create_category(name=c["name"])
                categorias_creadas[c["name"]] = nueva
                await canal_log.send(f"• Categoría creada: `{c['name']}`")
            except:
                no_restaurado.append(f"Categoría: {c['name']}")
                await canal_log.send(f"• ❌ No se pudo crear: `{c['name']}`")

    # ============================
    # RESTAURAR CANALES
    # ============================

    await canal_log.send("\n📁 **Restaurando canales...**")

    if "canales" in data["components"]:
        for ch in data["data"]["canales"]:
            try:
                categoria = categorias_creadas.get(ch["category"], None)

                if ch["type"] == "texto":
                    await guild.create_text_channel(
                        name=ch["name"],
                        topic=ch["topic"],
                        nsfw=ch["nsfw"],
                        slowmode_delay=ch["slowmode"],
                        category=categoria
                    )

                elif ch["type"] == "voz":
                    await guild.create_voice_channel(
                        name=ch["name"],
                        user_limit=ch["user_limit"],
                        bitrate=ch["bitrate"],
                        category=categoria
                    )

                elif ch["type"] == "foro":
                    await guild.create_forum_channel(
                        name=ch["name"],
                        category=categoria
                    )

                elif ch["type"] == "stage":
                    await guild.create_stage_channel(
                        name=ch["name"],
                        category=categoria
                    )

                await canal_log.send(f"• Canal creado: `{ch['name']}`")

            except:
                no_restaurado.append(f"Canal: {ch['name']}")
                await canal_log.send(f"• ❌ No se pudo crear: `{ch['name']}`")

    # ============================
    # EMOJIS
    # ============================

    await canal_log.send("\n🎨 **Restaurando emojis...**")

    if "emojis" in data["components"]:
        async with aiohttp.ClientSession() as session:
            for e in data["data"]["emojis"]:
                try:
                    async with session.get(e["url"]) as resp:
                        img = await resp.read()
                    await guild.create_custom_emoji(name=e["name"], image=img)
                    await canal_log.send(f"• Emoji creado: `{e['name']}`")
                except:
                    no_restaurado.append(f"Emoji: {e['name']}")
                    await canal_log.send(f"• ❌ No se pudo crear: `{e['name']}`")

    # ============================
    # STICKERS
    # ============================

    await canal_log.send("\n🪅 **Restaurando stickers...**")

    if "stickers" in data["components"]:
        for s in data["data"]["stickers"]:
            no_restaurado.append(f"Sticker: {s['name']} (no soportado)")
            await canal_log.send(f"• ❌ Sticker no soportado: `{s['name']}`")

    # ============================
    # EMBED FINAL
    # ============================

    reporte = "```\n"
    reporte += f"Canales: {len(data['data'].get('canales', []))}\n"
    reporte += f"Categorías: {len(data['data'].get('categorias', []))}\n"
    reporte += f"Roles: {len(data['data'].get('roles', []))}\n"
    reporte += f"Emojis: {len(data['data'].get('emojis', []))}\n"
    reporte += f"Stickers: {len(data['data'].get('stickers', []))}\n\n"

    if no_restaurado:
        reporte += "No restaurado:\n"
        for x in no_restaurado:
            reporte += f"- {x}\n"

    reporte += "```"

    embed = discord.Embed(
        title="🔧 Backup restaurado",
        description=f"El backup **{nombre}** ha sido restaurado correctamente.",
        color=COLOR
    )
    embed.add_field(name="Reporte:", value=reporte, inline=False)
    embed.set_footer(text="ModdyBot • Restauración completada")

    await interaction.followup.send(embed=embed, ephemeral=True)

# ============================
# COG PRINCIPAL
# ============================

class Backups(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ============================
    # /backup_restaurar
    # ============================

    @app_commands.command(name="backup_restaurar", description="Restaurar un backup.")
    async def backup_restaurar(self, interaction: discord.Interaction, nombre: str):

        if nombre not in backups:
            return await interaction.response.send_message("❌ Ese backup no existe.", ephemeral=True)

        data = backups[nombre]

        # Premium check
        if not is_premium(interaction.user.id):
            if interaction.guild.id != data["guild_id"]:
                return await interaction.response.send_message(
                    "❌ Solo los usuarios **Premium** pueden restaurar backups en otros servidores.",
                    ephemeral=True
                )

        embed = discord.Embed(
            title="⚠️ Advertencia de Restauración",
            description=(
                "Restaurar este backup **borrará TODOS los canales, categorías y roles actuales** del servidor.\n\n"
                "Esta acción es **irreversible**.\n\n"
                "ℹ️ **El canal donde estás ejecutando este comando NO será borrado.**\n"
                "Aquí se mostrará el progreso de la restauración.\n\n"
                "Selecciona una opción para continuar."
            ),
            color=COLOR
        )
        embed.set_footer(text="ModdyBot • Confirmación requerida")

        view = ConfirmRestore(nombre, data)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ============================
    # /backup_listar
    # ============================

    @app_commands.command(name="backup_listar", description="Lista tus backups creados.")
    async def backup_listar(self, interaction: discord.Interaction):

        lista = [
            (name, data)
            for name, data in backups.items()
            if data["created_by"] == interaction.user.id
        ]

        if not lista:
            return await interaction.response.send_message("📭 No tienes backups creados.", ephemeral=True)

        embed = discord.Embed(
            title="📚 Tus Backups",
            color=COLOR
        )

        for name, data in lista:
            fecha = f"<t:{data['created_at']}:F>"
            embed.add_field(
                name=f"📦 {name}",
                value=f"• Servidor: **{data['guild_name']}**\n• Fecha: {fecha}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ============================
    # /backup_borrar
    # ============================

    @app_commands.command(name="backup_borrar", description="Borra uno de tus backups.")
    async def backup_borrar(self, interaction: discord.Interaction, nombre: str):

        if nombre not in backups:
            return await interaction.response.send_message("❌ Ese backup no existe.", ephemeral=True)

        data = backups[nombre]

        if data["created_by"] != interaction.user.id and not is_premium(interaction.user.id):
            return await interaction.response.send_message(
                "❌ Solo el creador o un usuario Premium puede borrar este backup.",
                ephemeral=True
            )

        del backups[nombre]
        save_backups(backups)

        await interaction.response.send_message(
            f"🗑️ Backup **{nombre}** eliminado correctamente.",
            ephemeral=True
        )

    # ============================
    # /backup_info
    # ============================

    @app_commands.command(name="backup_info", description="Muestra información detallada de un backup.")
    async def backup_info(self, interaction: discord.Interaction, nombre: str):

        if nombre not in backups:
            return await interaction.response.send_message("❌ Ese backup no existe.", ephemeral=True)

        data = backups[nombre]

        embed = discord.Embed(
            title=f"ℹ️ Información del Backup: {nombre}",
            color=COLOR
        )

        embed.add_field(name="Servidor", value=data["guild_name"], inline=False)
        embed.add_field(name="Creador", value=f"<@{data['created_by']}>", inline=False)
        embed.add_field(name="Fecha", value=f"<t:{data['created_at']}:F>", inline=False)
        embed.add_field(
            name="Componentes",
            value="\n".join([f"• {c}" for c in data["components"]]),
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Backups(bot))
