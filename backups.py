import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime
import aiohttp

from cogs.premium import is_premium
from cogs.logs import UltraLogs

# ============================================================
# CONSTANTES
# ============================================================

BACKUP_FILE = "backups.json"
COOLDOWN_FILE = "cooldowns.json"
COLOR = discord.Color(0x0A3D62)

# ============================================================
# FUNCIONES UTILITARIAS (JSON)
# ============================================================

def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f)
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

backups = load_json(BACKUP_FILE, {})
cooldowns = load_json(COOLDOWN_FILE, {})

# ============================================================
# COOLDOWN
# ============================================================

def can_create_backup(user_id: int):
    user_id = str(user_id)
    ahora = int(datetime.datetime.utcnow().timestamp())

    if user_id not in cooldowns:
        return True, None

    ultimo = cooldowns[user_id].get("last_backup", 0)

    # PREMIUM → 5 minutos
    if is_premium(int(user_id)):
        if ahora - ultimo < 300:
            faltan = 300 - (ahora - ultimo)
            minutos = int(faltan / 60) + 1
            return False, f"🛠️ Podrás crear otro backup en **{minutos} minutos**."
        return True, None

    # FREE → 3 días
    if ahora - ultimo < 259200:
        faltan = 259200 - (ahora - ultimo)
        dias = int(faltan / 86400)
        horas = int((faltan % 86400) / 3600)
        return False, f"⏳ Te faltan **{dias} días y {horas} horas** para crear otro backup."

    return True, None

def register_backup(user_id: int):
    cooldowns[str(user_id)] = {"last_backup": int(datetime.datetime.utcnow().timestamp())}
    save_json(COOLDOWN_FILE, cooldowns)

# ============================================================
# AUTO-LIMPIEZA
# ============================================================

async def auto_cleanup(interaction, logs_cog: UltraLogs):
    MAX_BACKUPS = 15
    user_id = str(interaction.user.id)

    user_backups = [name for name, data in backups.items() if data["created_by"] == interaction.user.id]

    if len(user_backups) <= MAX_BACKUPS:
        return

    user_backups.sort(key=lambda n: backups[n]["created_at"])
    eliminar = len(user_backups) - MAX_BACKUPS

    for i in range(eliminar):
        nombre = user_backups[i]
        data = backups[nombre]

        embed = discord.Embed(
            title="🗑️ Backup eliminado automáticamente",
            description=(
                f"📦 **{nombre}**\n"
                f"👤 Creador: <@{data['created_by']}>\n"
                f"📅 Fecha: <t:{data['created_at']}:F>"
            ),
            color=COLOR
        )

        try:
            await logs_cog.send_log(interaction.guild, embed, "server_update")
        except:
            pass

        del backups[nombre]

    save_json(BACKUP_FILE, backups)

# ============================================================
# UI SELECT
# ============================================================

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

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================================================
# UI VIEW
# ============================================================

class BackupView(discord.ui.View):
    def __init__(self, nombre):
        super().__init__(timeout=120)
        self.nombre = nombre
        self.seleccion = []
        self.add_item(BackupSelect())

    @discord.ui.button(label="Crear Backup", style=discord.ButtonStyle.green, emoji="📦")
    async def crear(self, interaction: discord.Interaction, button: discord.ui.Button):

        print("[BACKUPS] Ejecutando botón Crear Backup...")

        if not self.seleccion:
            return await interaction.response.send_message("❌ Selecciona al menos un componente.", ephemeral=True)

        puede, razon = can_create_backup(interaction.user.id)
        if not puede:
            return await interaction.response.send_message(razon, ephemeral=True)

        guild = interaction.guild

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
            data["data"]["roles"] = [
                {
                    "name": r.name,
                    "color": r.color.value,
                    "hoist": r.hoist,
                    "mentionable": r.mentionable,
                    "position": r.position
                }
                for r in guild.roles
            ]

        # CATEGORÍAS
        if "categorias" in self.seleccion:
            data["data"]["categorias"] = [
                {"name": c.name, "position": c.position}
                for c in guild.categories
            ]

        # CANALES
        if "canales" in self.seleccion:
            canales = []
            for ch in guild.channels:
                if isinstance(ch, discord.CategoryChannel):
                    continue

                tipo = (
                    "texto" if isinstance(ch, discord.TextChannel) else
                    "voz" if isinstance(ch, discord.VoiceChannel) else
                    "foro" if isinstance(ch, discord.ForumChannel) else
                    "stage" if isinstance(ch, discord.StageChannel) else
                    "otro"
                )

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
            data["data"]["emojis"] = [{"name": e.name, "url": str(e.url)} for e in guild.emojis]

        # STICKERS
        if "stickers" in self.seleccion:
            data["data"]["stickers"] = [
                {"name": s.name, "description": s.description, "format": s.format.name, "url": str(s.url)}
                for s in guild.stickers
            ]

        backups[self.nombre] = data
        save_json(BACKUP_FILE, backups)

        register_backup(interaction.user.id)

        logs_cog = interaction.client.get_cog("UltraLogs")
        await auto_cleanup(interaction, logs_cog)

        embed = discord.Embed(
            title="🎉 Backup creado",
            description=f"El backup **{self.nombre}** ha sido guardado.",
            color=COLOR
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================================================
# FUNCIÓN RESTAURAR
# ============================================================

async def restore_backup(interaction, nombre, data):

    guild = interaction.guild
    canal_log = interaction.channel
    no_restaurado = []

    await canal_log.send("🛠️ **Iniciando restauración...**\nEste canal no será borrado.")

    # BORRAR CANALES
    await canal_log.send("🧹 **Eliminando canales...**")
    for ch in guild.channels:
        if ch.id == canal_log.id:
            continue
        try:
            await ch.delete()
        except:
            no_restaurado.append(f"Canal: {ch.name}")

    # BORRAR CATEGORÍAS
    await canal_log.send("🗂️ **Eliminando categorías...**")
    for c in guild.categories:
        try:
            await c.delete()
        except:
            no_restaurado.append(f"Categoría: {c.name}")

    # BORRAR ROLES
    await canal_log.send("🎭 **Eliminando roles...**")
    bot_role = guild.me.top_role.position
    for r in guild.roles:
        if r.position < bot_role:
            try:
                await r.delete()
            except:
                no_restaurado.append(f"Rol: {r.name}")

    # RESTAURAR CATEGORÍAS
    categorias_creadas = {}
    if "categorias" in data["components"]:
        for c in data["data"]["categorias"]:
            try:
                nueva = await guild.create_category(name=c["name"])
                categorias_creadas[c["name"]] = nueva
            except:
                no_restaurado.append(f"Categoría: {c['name']}")

    # RESTAURAR CANALES
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
                    await guild.create_forum_channel(name=ch["name"], category=categoria)

                elif ch["type"] == "stage":
                    await guild.create_stage_channel(name=ch["name"], category=categoria)

            except:
                no_restaurado.append(f"Canal: {ch['name']}")

    # RESTAURAR EMOJIS
    if "emojis" in data["components"]:
        async with aiohttp.ClientSession() as session:
            for e in data["data"]["emojis"]:
                try:
                    async with session.get(e["url"]) as resp:
                        img = await resp.read()
                    await guild.create_custom_emoji(name=e["name"], image=img)
                except:
                    no_restaurado.append(f"Emoji: {e['name']}")

    # STICKERS NO SOPORTADOS
    if "stickers" in data["components"]:
        for s in data["data"]["stickers"]:
            no_restaurado.append(f"Sticker: {s['name']} (no soportado)")

    # REPORTE FINAL
    reporte = "```\n"
    for x in no_restaurado:
        reporte += f"- {x}\n"
    reporte += "```"

    embed = discord.Embed(
        title="🔧 Backup restaurado",
        description=f"Backup **{nombre}** restaurado.",
        color=COLOR
    )
    embed.add_field(name="No restaurado:", value=reporte if no_restaurado else "Todo restaurado correctamente.")

    await interaction.followup.send(embed=embed, ephemeral=True)

# ============================================================
# CONFIRM RESTORE VIEW
# ============================================================

class ConfirmRestore(discord.ui.View):
    def __init__(self, nombre, data):
        super().__init__(timeout=60)
        self.nombre = nombre
        self.data = data

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.red, emoji="⚠️")
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("❌ Solo el dueño del servidor puede restaurar.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        await restore_backup(interaction, self.nombre, self.data)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.gray, emoji="❌")
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Restauración cancelada.", ephemeral=True)

# ============================================================
# COG PRINCIPAL
# ============================================================

class Backups(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # DETECTOR DE ERRORES
        print("\n[BACKUPS] Verificando comandos registrados...")
        for cmd in bot.tree.walk_commands():
            if cmd.name.startswith("backup"):
                print(f"[BACKUPS] Detectado: /{cmd.name}")
        print("[BACKUPS] Verificación completada.\n")

    # ============================================================
    # /backup_crear
    # ============================================================

    @app_commands.command(name="backup_crear", description="Crear un backup del servidor.")
    async def backup_crear(self, interaction: discord.Interaction, nombre: str):

        print("[BACKUPS] Ejecutando /backup_crear...")

        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("❌ Solo el dueño puede crear backups.", ephemeral=True)

        if nombre in backups:
            return await interaction.response.send_message("❌ Ya existe un backup con ese nombre.", ephemeral=True)

        puede, razon = can_create_backup(interaction.user.id)
        if not puede:
            return await interaction.response.send_message(razon, ephemeral=True)

        embed = discord.Embed(
            title="📦 Crear Backup",
            description=f"Nombre: **{nombre}**\nSelecciona qué guardar.",
            color=COLOR
        )

        await interaction.response.send_message(embed=embed, view=BackupView(nombre), ephemeral=True)

    # ============================================================
    # /backup_restaurar
    # ============================================================

    @app_commands.command(name="backup_restaurar", description="Restaurar un backup.")
    async def backup_restaurar(self, interaction: discord.Interaction, nombre: str):

        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("❌ Solo el dueño puede restaurar.", ephemeral=True)

        if nombre not in backups:
            return await interaction.response.send_message("❌ Ese backup no existe.", ephemeral=True)

        data = backups[nombre]

        embed = discord.Embed(
            title="⚠️ Advertencia",
            description=(
                "Restaurar este backup **borrará todo el servidor**.\n"
                "El canal actual NO será borrado.\n\n"
                "¿Deseas continuar?"
            ),
            color=COLOR
        )

        await interaction.response.send_message(embed=embed, view=ConfirmRestore(nombre, data), ephemeral=True)

    # ============================================================
    # /backup_borrar
    # ============================================================

    @app_commands.command(name="backup_borrar", description="Borrar un backup.")
    async def backup_borrar(self, interaction: discord.Interaction, nombre: str):

        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("❌ Solo el dueño puede borrar backups.", ephemeral=True)

        if nombre not in backups:
            return await interaction.response.send_message("❌ Ese backup no existe.", ephemeral=True)

        del backups[nombre]
        save_json(BACKUP_FILE, backups)

        await interaction.response.send_message(f"🗑️ Backup **{nombre}** eliminado.", ephemeral=True)

    # ============================================================
    # /backup_listar
    # ============================================================

    @app_commands.command(name="backup_listar", description="Listar tus backups.")
    async def backup_listar(self, interaction: discord.Interaction):

        lista = [(name, data) for name, data in backups.items() if data["created_by"] == interaction.user.id]

        if not lista:
            return await interaction.response.send_message("📭 No tienes backups.", ephemeral=True)

        embed = discord.Embed(title="📚 Tus Backups", color=COLOR)

        for name, data in lista:
            embed.add_field(
                name=f"📦 {name}",
                value=f"Servidor: **{data['guild_name']}**\nFecha: <t:{data['created_at']}:F>",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ============================================================
    # /backup_info
    # ============================================================

    @app_commands.command(name="backup_info", description="Información de un backup.")
    async def backup_info(self, interaction: discord.Interaction, nombre: str):

        print("[BACKUPS] Ejecutando /backup_info...")

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

        componentes = "\n".join([f"• {c}" for c in data["components"]])
        embed.add_field(name="Componentes guardados", value=componentes, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================================================
# SETUP
# ============================================================

async def setup(bot):
    print("[BACKUPS] Cargando COG Backups...")
    await bot.add_cog(Backups(bot))
    print("[BACKUPS] COG Backups cargado correctamente.") 
