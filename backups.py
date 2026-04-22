import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime

from cogs.premium import is_premium
from cogs.cooldowns import can_create_backup, register_backup

BACKUP_FILE = "backups.json"


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
# SELECT MENU PARA CREAR BACKUP
# ============================

class BackupSelect(discord.ui.Select):
    def __init__(self):
        opciones = [
            discord.SelectOption(label="Roles", value="roles"),
            discord.SelectOption(label="Canales", value="canales"),
            discord.SelectOption(label="Categorías", value="categorias"),
            discord.SelectOption(label="Emojis", value="emojis"),
            discord.SelectOption(label="Stickers", value="stickers"),
        ]

        super().__init__(
            placeholder="Selecciona qué quieres guardar...",
            min_values=1,
            max_values=5,
            options=opciones
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.seleccion = self.values
        await interaction.response.send_message(
            "✔ Componentes seleccionados. Pulsa **Crear Backup**.",
            ephemeral=True
        )


class BackupView(discord.ui.View):
    def __init__(self, nombre):
        super().__init__(timeout=120)
        self.nombre = nombre
        self.seleccion = []
        self.add_item(BackupSelect())

    @discord.ui.button(label="Crear Backup", style=discord.ButtonStyle.green)
    async def crear(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not self.seleccion:
            return await interaction.response.send_message(
                "❌ Debes seleccionar al menos un componente.",
                ephemeral=True
            )

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

        # ----------------------------
        # GUARDAR ROLES
        # ----------------------------
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

        # ----------------------------
        # GUARDAR CATEGORÍAS
        # ----------------------------
        if "categorias" in self.seleccion:
            categorias = []
            for c in guild.categories:
                categorias.append({
                    "name": c.name,
                    "position": c.position
                })
            data["data"]["categorias"] = categorias

        # ----------------------------
        # GUARDAR CANALES
        # ----------------------------
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

        # ----------------------------
        # GUARDAR EMOJIS
        # ----------------------------
        if "emojis" in self.seleccion:
            emojis = []
            for e in guild.emojis:
                emojis.append({
                    "name": e.name,
                    "url": str(e.url)
                })
            data["data"]["emojis"] = emojis

        # ----------------------------
        # GUARDAR STICKERS
        # ----------------------------
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

        # GUARDAR EN JSON
        backups[self.nombre] = data
        save_backups(backups)

        # Registrar cooldown
        register_backup(interaction.user.id)

        await interaction.response.send_message(
            f"🎉 Backup **{self.nombre}** creado correctamente.",
            ephemeral=True
        )


# ============================
# COG PRINCIPAL
# ============================

class Backups(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ============================
    # /backup_crear
    # ============================

    @app_commands.command(name="backup_crear", description="Crear un backup del servidor.")
    async def backup_crear(self, interaction: discord.Interaction, nombre: str):

        # COOLDOWN
        puede, razon = can_create_backup(interaction.user.id)
        if not puede:
            return await interaction.response.send_message(razon, ephemeral=True)

        if nombre in backups:
            return await interaction.response.send_message(
                "❌ Ya existe un backup con ese nombre.",
                ephemeral=True
            )

        view = BackupView(nombre)
        await interaction.response.send_message(
            f"🗂 **Creación de Backup — {nombre}**\nSelecciona los componentes:",
            view=view,
            ephemeral=True
        )

    # ============================
    # /backup_listar
    # ============================

    @app_commands.command(name="backup_listar", description="Listar tus backups creados.")
    async def backup_listar(self, interaction: discord.Interaction):

        texto = ""

        for nombre, data in backups.items():
            if data["created_by"] == interaction.user.id:
                fecha = datetime.datetime.utcfromtimestamp(data["created_at"])
                texto += f"📦 **{nombre}** — `{fecha}` — Servidor: **{data['guild_name']}**\n"

        if texto == "":
            texto = "No tienes backups creados."

        await interaction.response.send_message(texto, ephemeral=True)

    # ============================
    # /backup_borrar
    # ============================

    @app_commands.command(name="backup_borrar", description="Borrar un backup.")
    async def backup_borrar(self, interaction: discord.Interaction, nombre: str):

        if nombre not in backups:
            return await interaction.response.send_message("❌ Ese backup no existe.", ephemeral=True)

        if backups[nombre]["created_by"] != interaction.user.id:
            return await interaction.response.send_message("❌ Ese backup no es tuyo.", ephemeral=True)

        del backups[nombre]
        save_backups(backups)

        await interaction.response.send_message(f"🗑 Backup **{nombre}** eliminado.", ephemeral=True)

    # ============================
    # /backup_restaurar
    # ============================

    @app_commands.command(name="backup_restaurar", description="Restaurar un backup.")
    async def backup_restaurar(self, interaction: discord.Interaction, nombre: str):

        if nombre not in backups:
            return await interaction.response.send_message("❌ Ese backup no existe.", ephemeral=True)

        data = backups[nombre]

        # Si NO es premium → solo restaurar en el servidor original
        if not is_premium(interaction.user.id):
            if interaction.guild.id != data["guild_id"]:
                return await interaction.response.send_message(
                    "❌ Solo los usuarios **Premium** pueden restaurar backups en otros servidores.",
                    ephemeral=True
                )

        guild = interaction.guild

        no_restaurado = []

        # ============================
        # RESTAURAR ROLES
        # ============================

        if "roles" in data["components"]:
            bot_role = guild.me.top_role.position

            for r in data["data"]["roles"]:
                if r["position"] >= bot_role:
                    no_restaurado.append(f"Rol: {r['name']}")
                    continue

                try:
                    await guild.create_role(
                        name=r["name"],
                        color=discord.Color(r["color"]),
                        hoist=r["hoist"],
                        mentionable=r["mentionable"]
                    )
                except:
                    no_restaurado.append(f"Rol: {r['name']}")

        # ============================
        # RESTAURAR CATEGORÍAS
        # ============================

        categorias_creadas = {}

        if "categorias" in data["components"]:
            for c in data["data"]["categorias"]:
                try:
                    nueva = await guild.create_category(name=c["name"])
                    categorias_creadas[c["name"]] = nueva
                except:
                    no_restaurado.append(f"Categoría: {c['name']}")

        # ============================
        # RESTAURAR CANALES
        # ============================

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

                except:
                    no_restaurado.append(f"Canal: {ch['name']}")

        # ============================
        # EMOJIS Y STICKERS
        # ============================

        if "emojis" in data["components"]:
            for e in data["data"]["emojis"]:
                try:
                    async with interaction.client.session.get(e["url"]) as resp:
                        img = await resp.read()
                    await guild.create_custom_emoji(name=e["name"], image=img)
                except:
                    no_restaurado.append(f"Emoji: {e['name']}")

        if "stickers" in data["components"]:
            for s in data["data"]["stickers"]:
                no_restaurado.append(f"Sticker: {s['name']} (no soportado)")

        # ============================
        # REPORTE FINAL
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

        await interaction.response.send_message(
            f"🔄 Backup **{nombre}** restaurado.\n{reporte}",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Backups(bot)) 
