import os
import json
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
OWNER_ID = 1394342273919225959
CONFIG_PATH = "ticket_config.json"

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ==========================
# CONFIG
# ==========================

def load_config():
    if not os.path.exists(CONFIG_PATH):
        default = {
            "notify_channel_id": None,
            "staff_roles": [],
            "ticket_types": {
                "reporte": {
                    "emoji": "🎫",
                    "label": "Reporte",
                    "description": "Reportar a un usuario",
                    "fields": {
                        "motivo": "Motivo del reporte",
                        "pruebas": "Pruebas"
                    }
                }
            }
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4, ensure_ascii=False)
        return default

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config():
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


config = load_config()


# ==========================
# HELPERS
# ==========================

def owner_only():
    async def predicate(interaction):
        return interaction.user.id == OWNER_ID
    return app_commands.check(predicate)


def is_staff(member: discord.Member):
    staff_roles = config.get("staff_roles", [])
    return any(r.id in staff_roles for r in member.roles)


def get_ticket_types():
    return config.get("ticket_types", {})


async def send_public_notification(guild, user, tipo, estado, extra=None):
    channel_id = config.get("notify_channel_id")
    if not channel_id:
        return

    channel = guild.get_channel(channel_id)
    if not channel:
        return

    embed = discord.Embed(
        title=f"Ticket de {tipo}",
        color=discord.Color.yellow() if estado == "pendiente" else
              discord.Color.orange() if estado == "revision" else
              discord.Color.green() if estado == "aceptado" else
              discord.Color.red()
    )

    if estado == "pendiente":
        embed.add_field(name="Estado", value="🟡 Pendiente", inline=False)

    elif estado == "revision":
        embed.add_field(name="Estado", value="🟠 En revisión", inline=False)
        embed.add_field(name="Staff", value=extra, inline=False)

    elif estado == "aceptado":
        embed.add_field(name="Estado", value="🟢 Aceptado", inline=False)
        embed.add_field(name="Motivo", value=extra, inline=False)

    elif estado == "rechazado":
        embed.add_field(name="Estado", value="🔴 Rechazado", inline=False)
        embed.add_field(name="Razón", value=extra, inline=False)

    await channel.send(content=user.mention, embed=embed)


# ==========================
# MODAL PARA CAMPOS DEL TICKET
# ==========================

class TicketModal(Modal):
    def __init__(self, tipo, data, user):
        super().__init__(title=f"Ticket: {data['label']}")
        self.tipo = tipo
        self.data = data
        self.user = user
        self.inputs = {}

        for key, label in list(data["fields"].items())[:5]:
            ti = TextInput(label=label, style=discord.TextStyle.paragraph)
            self.inputs[key] = ti
            self.add_item(ti)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        tipo_data = self.data
        emoji = tipo_data["emoji"]
        tipo = self.tipo

        # Crear canal
        channel_name = f"{emoji} {tipo}-{self.user.name}".replace(" ", "-")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            self.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        for role_id in config.get("staff_roles", []):
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(channel_name, overwrites=overwrites)

        # Embed inicial
        embed = discord.Embed(
            title=f"Ticket de {tipo_data['label']}",
            description="Has abierto un ticket. El staff te atenderá lo antes posible.",
            color=discord.Color.blue()
        )

        staff_mentions = " ".join(
            role.mention for role in (guild.get_role(r) for r in config["staff_roles"]) if role
        )

        await channel.send(
            content=f"{self.user.mention} {staff_mentions}",
            embed=embed,
            view=TicketView(self.user.id, tipo, tipo_data)
        )

        # Notificación pública
        await send_public_notification(guild, self.user, tipo_data["label"], "pendiente")

        await interaction.response.send_message("Ticket creado.", ephemeral=True)


# ==========================
# BOTONES DENTRO DEL TICKET
# ==========================

class TicketView(View):
    def __init__(self, user_id, tipo, tipo_data):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.tipo = tipo
        self.tipo_data = tipo_data
        self.claimed_by = None

    @discord.ui.button(label="Reclamar", style=discord.ButtonStyle.primary)
    async def claim(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("No eres staff.", ephemeral=True)

        if self.claimed_by:
            return await interaction.response.send_message("Ya está reclamado.", ephemeral=True)

        self.claimed_by = interaction.user.id
        button.disabled = True
        button.label = f"Reclamado por {interaction.user.display_name}"

        await interaction.message.edit(view=self)

        # Notificación pública
        await send_public_notification(
            interaction.guild,
            interaction.guild.get_member(self.user_id),
            self.tipo_data["label"],
            "revision",
            extra=interaction.user.mention
        )

        await interaction.channel.send(
            content=f"<@{self.user_id}> {interaction.user.mention}",
            embed=discord.Embed(
                title="Ticket reclamado",
                description=f"Este ticket ha sido reclamado por {interaction.user.mention}",
                color=discord.Color.orange()
            )
        )

        await interaction.response.send_message("Reclamado.", ephemeral=True)

    @discord.ui.button(label="Cerrar ticket", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("No eres staff.", ephemeral=True)

        modal = CloseModal(self.user_id, self.tipo_data)
        await interaction.response.send_modal(modal)


# ==========================
# MODAL DE CIERRE
# ==========================

class CloseModal(Modal):
    def __init__(self, user_id, tipo_data):
        super().__init__(title="Cerrar ticket")
        self.user_id = user_id
        self.tipo_data = tipo_data

        self.reason = TextInput(label="Razón del cierre", style=discord.TextStyle.paragraph)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = guild.get_member(self.user_id)

        # DM al usuario
        try:
            await user.send(
                embed=discord.Embed(
                    title=f"Tu ticket de {self.tipo_data['label']} ha sido cerrado",
                    description=f"Razón: {self.reason.value}",
                    color=discord.Color.red()
                )
            )
        except:
            pass

        # Notificación pública
        await send_public_notification(
            guild,
            user,
            self.tipo_data["label"],
            "rechazado",
            extra=self.reason.value
        )

        # Mensaje en el canal
        await interaction.channel.send(
            content=f"{user.mention} {interaction.user.mention}",
            embed=discord.Embed(
                title="Ticket cerrado",
                description=f"Razón: {self.reason.value}\nEl canal se eliminará en 5 segundos.",
                color=discord.Color.red()
            )
        )

        await interaction.response.send_message("Ticket cerrado.", ephemeral=True)

        await asyncio.sleep(5)
        await interaction.channel.delete() 



# ==========================
# STAFF ROLES (OWNER ONLY)
# ==========================

@bot.tree.command(name="staff_roles", description="Gestiona los roles de staff")
@owner_only()
@app_commands.describe(
    accion="Acción a realizar",
    rol="Rol a añadir o eliminar"
)
@app_commands.choices(
    accion=[
        app_commands.Choice(name="Añadir", value="add"),
        app_commands.Choice(name="Eliminar", value="remove"),
        app_commands.Choice(name="Listar", value="list")
    ]
)
async def staff_roles(interaction: discord.Interaction, accion: app_commands.Choice[str], rol: discord.Role = None):
    staff = config.get("staff_roles", [])

    if accion.value == "list":
        if not staff:
            return await interaction.response.send_message("No hay roles de staff configurados.", ephemeral=True)

        roles = [interaction.guild.get_role(r).mention for r in staff if interaction.guild.get_role(r)]
        return await interaction.response.send_message(
            "Roles de staff:\n" + "\n".join(roles),
            ephemeral=True
        )

    if not rol:
        return await interaction.response.send_message("Debes seleccionar un rol.", ephemeral=True)

    if accion.value == "add":
        if rol.id in staff:
            return await interaction.response.send_message("Ese rol ya es staff.", ephemeral=True)

        staff.append(rol.id)
        config["staff_roles"] = staff
        save_config()
        return await interaction.response.send_message(f"Rol {rol.mention} añadido como staff.", ephemeral=True)

    if accion.value == "remove":
        if rol.id not in staff:
            return await interaction.response.send_message("Ese rol no es staff.", ephemeral=True)

        staff.remove(rol.id)
        config["staff_roles"] = staff
        save_config()
        return await interaction.response.send_message(f"Rol {rol.mention} eliminado del staff.", ephemeral=True)


# ==========================
# TICKET TYPES (OWNER ONLY)
# ==========================

@bot.tree.command(name="ticket_add", description="Añade un tipo de ticket")
@owner_only()
@app_commands.describe(
    tipo="ID interno del tipo (ej: reporte)",
    label="Nombre visible",
    descripcion="Descripción del tipo",
    emoji="Emoji del tipo"
)
async def ticket_add(interaction: discord.Interaction, tipo: str, label: str, descripcion: str, emoji: str):
    tipo = tipo.lower()

    config["ticket_types"][tipo] = {
        "emoji": emoji,
        "label": label,
        "description": descripcion,
        "fields": {}
    }

    save_config()
    await interaction.response.send_message(f"Tipo **{label}** añadido correctamente.", ephemeral=True)


@bot.tree.command(name="ticket_remove", description="Elimina un tipo de ticket")
@owner_only()
@app_commands.describe(tipo="Selecciona el tipo a eliminar")
async def ticket_remove(interaction: discord.Interaction, tipo: str):
    tipo = tipo.lower()

    if tipo not in config["ticket_types"]:
        return await interaction.response.send_message("Ese tipo no existe.", ephemeral=True)

    del config["ticket_types"][tipo]
    save_config()
    await interaction.response.send_message(f"Tipo `{tipo}` eliminado.", ephemeral=True)


@ticket_remove.autocomplete("tipo")
async def ticket_remove_autocomplete(interaction: discord.Interaction, current: str):
    current = current.lower()
    return [
        app_commands.Choice(name=data["label"], value=key)
        for key, data in config["ticket_types"].items()
        if current in key.lower() or current in data["label"].lower()
    ][:25]


# ==========================
# TICKET FIELDS (OWNER ONLY)
# ==========================

@bot.tree.command(name="ticket_fields", description="Gestiona los campos del modal de un tipo de ticket")
@owner_only()
@app_commands.describe(
    tipo="Tipo de ticket",
    accion="Acción a realizar",
    field="Nombre interno del campo",
    nombre="Nombre visible del campo"
)
@app_commands.choices(
    accion=[
        app_commands.Choice(name="Añadir", value="add"),
        app_commands.Choice(name="Editar", value="edit"),
        app_commands.Choice(name="Eliminar", value="remove")
    ]
)
async def ticket_fields(interaction: discord.Interaction, tipo: str, accion: app_commands.Choice[str], field: str, nombre: str = None):
    tipo = tipo.lower()

    if tipo not in config["ticket_types"]:
        return await interaction.response.send_message("Ese tipo no existe.", ephemeral=True)

    fields = config["ticket_types"][tipo]["fields"]

    if accion.value in ("add", "edit"):
        if not nombre:
            return await interaction.response.send_message("Debes indicar un nombre visible.", ephemeral=True)

        fields[field] = nombre
        save_config()
        return await interaction.response.send_message(f"Campo **{field}** actualizado.", ephemeral=True)

    if accion.value == "remove":
        if field not in fields:
            return await interaction.response.send_message("Ese campo no existe.", ephemeral=True)

        del fields[field]
        save_config()
        return await interaction.response.send_message(f"Campo **{field}** eliminado.", ephemeral=True)


@ticket_fields.autocomplete("tipo")
async def ticket_fields_tipo_autocomplete(interaction: discord.Interaction, current: str):
    current = current.lower()
    return [
        app_commands.Choice(name=data["label"], value=key)
        for key, data in config["ticket_types"].items()
        if current in key.lower() or current in data["label"].lower()
    ][:25]


# ==========================
# PANEL (OWNER ONLY)
# ==========================

@bot.tree.command(name="panel", description="Envía el panel de tickets")
@owner_only()
@app_commands.describe(
    canal="Canal donde se enviará el panel"
)
async def panel(interaction: discord.Interaction, canal: discord.TextChannel):
    if not config["ticket_types"]:
        return await interaction.response.send_message("No hay tipos de ticket configurados.", ephemeral=True)

    embed = discord.Embed(
        title="Centro de Tickets",
        description="Selecciona un tipo de ticket para abrir uno.",
        color=discord.Color.blue()
    )

    view = PanelView()

    await canal.send(embed=embed, view=view)
    await interaction.response.send_message("Panel enviado.", ephemeral=True)


# ==========================
# PANEL CLEAR (OWNER ONLY)
# ==========================

@bot.tree.command(name="panel_clear", description="Elimina paneles antiguos")
@owner_only()
@app_commands.describe(
    canal="Canal donde están los paneles",
    limite="Cantidad de mensajes a revisar"
)
async def panel_clear(interaction: discord.Interaction, canal: discord.TextChannel, limite: int = 50):
    borrados = 0

    async for msg in canal.history(limit=limite):
        if msg.author == interaction.client.user and msg.components:
            try:
                await msg.delete()
                borrados += 1
            except:
                pass

    await interaction.response.send_message(f"Paneles eliminados: **{borrados}**", ephemeral=True)




# ==========================
# PANEL VIEW (SELECT MENU)
# ==========================

class PanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

        options = []
        for key, data in config["ticket_types"].items():
            options.append(
                discord.SelectOption(
                    label=data["label"],
                    value=key,
                    description=data["description"],
                    emoji=data["emoji"]
                )
            )

        self.add_item(TicketSelect(options))


class TicketSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Selecciona un tipo de ticket",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        tipo = self.values[0]
        data = config["ticket_types"][tipo]

        modal = TicketModal(tipo, data, interaction.user)
        await interaction.response.send_modal(modal)


# ==========================
# EVENTO READY
# ==========================

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception as e:
        print("Error sincronizando comandos:", e)

    print(f"Bot listo como {bot.user} ({bot.user.id})")


# ==========================
# RUN
# ==========================

bot.run(TOKEN) 
