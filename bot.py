import os
import json
import asyncio
from typing import Optional

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
            "solicitudes_channel_id": None,
            "staff_roles": [],
            "panel": {
                "title": "Centro de Tickets",
                "description": "Selecciona un tipo de ticket",
                "color": "blue"
            },
            "ticket_types": {
                "reporte": {
                    "emoji": "🧾",
                    "label": "Reporte",
                    "description": "Reportar a un usuario",
                    "fields": {
                        "Motivo del reporte": "Motivo del reporte",
                        "Pruebas": "Pruebas"
                    }
                }
            }
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4, ensure_ascii=False)
        return default

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    if "panel" not in cfg:
        cfg["panel"] = {
            "title": "Centro de Tickets",
            "description": "Selecciona un tipo de ticket",
            "color": "blue"
        }

    if "solicitudes_channel_id" not in cfg:
        cfg["solicitudes_channel_id"] = None

    if "notify_channel_id" not in cfg:
        cfg["notify_channel_id"] = None

    if "ticket_types" not in cfg:
        cfg["ticket_types"] = {}

    # Normalizar fields a dict
    for tipo, info in cfg.get("ticket_types", {}).items():
        if isinstance(info.get("fields"), list):
            info["fields"] = {v: v for v in info["fields"]}

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)

    return cfg


def save_config():
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


config = load_config()

# ==========================
# HELPERS
# ==========================

def owner_only():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.id == OWNER_ID
    return app_commands.check(predicate)


def is_staff(member: discord.Member):
    return any(r.id in config.get("staff_roles", []) for r in member.roles)


def get_ticket_types():
    return config.get("ticket_types", {})


def parse_color(color_str: str) -> discord.Color:
    color_str = color_str.lower().strip()
    colores = {
        "rojo": discord.Color.red(),
        "azul": discord.Color.blue(),
        "verde": discord.Color.green(),
        "amarillo": discord.Color.yellow(),
        "morado": discord.Color.purple(),
        "naranja": discord.Color.orange(),
        "gris": discord.Color.greyple(),
        "negro": discord.Color.dark_gray(),
        "blanco": discord.Color.light_gray(),
        "cyan": discord.Color.teal(),
        "rosa": discord.Color.magenta()
    }
    if color_str in colores:
        return colores[color_str]
    if color_str.startswith("#"):
        try:
            return discord.Color(int(color_str[1:], 16))
        except:
            return discord.Color.blue()
    try:
        return discord.Color(int(color_str, 16))
    except:
        return discord.Color.blue()


async def send_public_notification(
    guild: discord.Guild,
    user: discord.Member,
    tipo: str,
    estado: str,
    extra: Optional[str] = None,
    staff: Optional[str] = None,
    ticket_channel: Optional[discord.TextChannel] = None
):
    channel_id = config.get("notify_channel_id")
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if not channel:
        return

    # Solo estos estados
    if estado not in ("pendiente", "aceptado", "rechazado"):
        return

    color = (
        discord.Color.yellow() if estado == "pendiente" else
        discord.Color.green() if estado == "aceptado" else
        discord.Color.red()
    )

    embed = discord.Embed(
        title=f"Ticket de {tipo}",
        color=color
    )

    embed.add_field(name="Usuario", value=f"{user.mention} (`{user.id}`)", inline=False)

    if ticket_channel is not None:
        embed.add_field(name="Canal del ticket", value=ticket_channel.mention, inline=False)

    if staff:
        embed.add_field(name="Staff", value=staff, inline=False)

    if estado == "pendiente":
        embed.add_field(name="Estado", value="🟡 Pendiente", inline=False)
    elif estado == "aceptado":
        embed.add_field(name="Estado", value="🟢 Aceptado", inline=False)
        if extra:
            embed.add_field(name="Motivo de aceptación", value=extra, inline=False)
    elif estado == "rechazado":
        embed.add_field(name="Estado", value="🔴 Rechazado", inline=False)
        if extra:
            embed.add_field(name="Motivo de rechazo", value=extra, inline=False)

    await channel.send(content=user.mention, embed=embed)

# ==========================
# SISTEMA DE SOLICITUDES
# ==========================

class StaffRequestView(View):
    def __init__(self, user_id, tipo, tipo_data, respuestas):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.tipo = tipo
        self.tipo_data = tipo_data
        self.respuestas = respuestas

    @discord.ui.button(label="Aceptar", emoji="✅", style=discord.ButtonStyle.success)
    async def aceptar(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("No eres staff.", ephemeral=True)
        await interaction.response.send_modal(
            AcceptRequestModal(self.user_id, self.tipo, self.tipo_data, self.respuestas, interaction.message)
        )

    @discord.ui.button(label="Rechazar", emoji="❌", style=discord.ButtonStyle.danger)
    async def rechazar(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("No eres staff.", ephemeral=True)
        await interaction.response.send_modal(
            RejectRequestModal(self.user_id, self.tipo, self.tipo_data, self.respuestas, interaction.message)
        )

# ==========================
# MODAL ACEPTAR SOLICITUD
# ==========================

class AcceptRequestModal(Modal):
    def __init__(self, user_id, tipo, tipo_data, respuestas, solicitud_message):
        super().__init__(title="Aceptar solicitud")
        self.user_id = user_id
        self.tipo = tipo
        self.tipo_data = tipo_data
        self.respuestas = respuestas
        self.solicitud_message = solicitud_message

        self.motivo = TextInput(label="Motivo de la aceptación", style=discord.TextStyle.paragraph)
        self.add_item(self.motivo)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = guild.get_member(self.user_id)

        # Crear canal del ticket con topic para cierre
        channel_name = f"{self.tipo}-{user.name}".replace(" ", "-")
        topic = f"user_id:{user.id};tipo:{self.tipo_data['label']}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        for role_id in config.get("staff_roles", []):
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        ticket_channel = await guild.create_text_channel(channel_name, overwrites=overwrites, topic=topic)

        # Ping al staff dentro del ticket
        staff_roles = config.get("staff_roles", [])
        staff_ping = ""
        if staff_roles:
            menciones = []
            for rid in staff_roles:
                role = guild.get_role(rid)
                if role:
                    menciones.append(role.mention)
            if menciones:
                staff_ping = " ".join(menciones)

        # Embed inicial del ticket
        embed = discord.Embed(
            title=f"Has abierto un ticket de {self.tipo_data['label']}",
            description="Espera pacientemente, el staff te atenderá lo antes posible.",
            color=discord.Color.green()
        )

        await ticket_channel.send(
            content=f"{user.mention} {staff_ping}",
            embed=embed,
            view=TicketView(user.id, self.tipo, self.tipo_data)
        )

        # Notificación pública (aceptado)
        await send_public_notification(
            guild,
            user,
            self.tipo_data["label"],
            "aceptado",
            extra=self.motivo.value,
            staff=interaction.user.mention,
            ticket_channel=ticket_channel
        )

        # DM al usuario
        try:
            await user.send(
                embed=discord.Embed(
                    title=f"Tu solicitud de {self.tipo_data['label']} fue aceptada",
                    description=f"Motivo: {self.motivo.value}",
                    color=discord.Color.green()
                )
            )
        except:
            pass

        # Editar solicitud original
        embed = self.solicitud_message.embeds[0]
        embed.set_field_at(3, name="📍 Estado", value="🟢 Aceptado", inline=False)
        embed.add_field(name="Revisado por", value=interaction.user.mention, inline=False)
        embed.add_field(name="Motivo", value=self.motivo.value, inline=False)

        await self.solicitud_message.edit(embed=embed, view=None)

        # Evitar error 10062
        await interaction.followup.send("Solicitud aceptada.", ephemeral=True)

# ==========================
# MODAL RECHAZAR SOLICITUD
# ==========================

class RejectRequestModal(Modal):
    def __init__(self, user_id, tipo, tipo_data, respuestas, solicitud_message):
        super().__init__(title="Rechazar solicitud")
        self.user_id = user_id
        self.tipo = tipo
        self.tipo_data = tipo_data
        self.respuestas = respuestas
        self.solicitud_message = solicitud_message

        self.motivo = TextInput(label="Motivo del rechazo", style=discord.TextStyle.paragraph)
        self.add_item(self.motivo)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = guild.get_member(self.user_id)

        # Notificación pública (rechazado)
        await send_public_notification(
            guild,
            user,
            self.tipo_data["label"],
            "rechazado",
            extra=self.motivo.value,
            staff=interaction.user.mention
        )

        # DM al usuario
        try:
            await user.send(
                embed=discord.Embed(
                    title=f"Tu solicitud de {self.tipo_data['label']} fue rechazada",
                    description=f"Motivo: {self.motivo.value}",
                    color=discord.Color.red()
                )
            )
        except:
            pass

        # Editar solicitud original
        embed = self.solicitud_message.embeds[0]
        embed.set_field_at(3, name="📍 Estado", value="🔴 Rechazado", inline=False)
        embed.add_field(name="Revisado por", value=interaction.user.mention, inline=False)
        embed.add_field(name="Motivo", value=self.motivo.value, inline=False)

        await self.solicitud_message.edit(embed=embed, view=None)

        # Evitar error 10062
        await interaction.followup.send("Solicitud rechazada.", ephemeral=True)

# ==========================
# MODAL DEL USUARIO (ENVÍA SOLICITUD)
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
        tipo = self.tipo

        solicitudes_channel_id = config.get("solicitudes_channel_id")
        if not solicitudes_channel_id:
            return await interaction.response.send_message(
                "No hay canal de solicitudes configurado. Usa `/config_solicitudes`.",
                ephemeral=True
            )

        solicitudes_channel = guild.get_channel(solicitudes_channel_id)
        if not solicitudes_channel:
            return await interaction.response.send_message(
                "El canal de solicitudes configurado ya no existe.",
                ephemeral=True
            )

        # Embed de solicitud
        embed = discord.Embed(
            title=f"📩 Nueva solicitud: {tipo_data['label']}",
            color=discord.Color.yellow()
        )
        embed.add_field(name="👤 Usuario", value=f"{self.user.mention} ({self.user.id})", inline=False)
        embed.add_field(name="📂 Tipo", value=tipo_data["label"], inline=False)

        detalles = []
        for key, label in tipo_data["fields"].items():
            valor = self.inputs[key].value if key in self.inputs else "Sin respuesta"
            detalles.append(f"**{label}:** {valor}")

        if detalles:
            embed.add_field(name="📝 Detalles", value="\n".join(detalles), inline=False)

        embed.add_field(name="📍 Estado", value="🟡 Pendiente", inline=False)

        view = StaffRequestView(
            user_id=self.user.id,
            tipo=tipo,
            tipo_data=tipo_data,
            respuestas={k: self.inputs[k].value for k in self.inputs}
        )

        # Ping al staff
        staff_roles = config.get("staff_roles", [])
        staff_ping = ""
        if staff_roles:
            menciones = []
            for rid in staff_roles:
                role = guild.get_role(rid)
                if role:
                    menciones.append(role.mention)
            if menciones:
                staff_ping = " ".join(menciones)

        await solicitudes_channel.send(content=staff_ping or None, embed=embed, view=view)

        # Notificación pública (pendiente)
        await send_public_notification(guild, self.user, tipo_data["label"], "pendiente")

        await interaction.response.send_message(
            "Tu solicitud ha sido enviada. El staff la revisará.",
            ephemeral=True
        )

# ==========================
# VISTA DEL TICKET (RECLAMAR / CERRAR)
# ==========================

class TicketView(View):
    def __init__(self, user_id, tipo, tipo_data):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.tipo = tipo
        self.tipo_data = tipo_data

    @discord.ui.button(label="Reclamar", emoji="🛠️", style=discord.ButtonStyle.primary)
    async def reclamar(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("No eres staff.", ephemeral=True)

        creador = interaction.guild.get_member(self.user_id)
        reclamador = interaction.user

        content = f"{creador.mention} {reclamador.mention}"

        embed = discord.Embed(
            title="🎫 Ticket reclamado",
            description=f"Este ticket ha sido reclamado por {reclamador.mention}",
            color=discord.Color.orange()
        )

        await interaction.response.send_message(content=content, embed=embed)

        # Ya NO hay notificación pública de "en revisión"

    @discord.ui.button(label="Cerrar ticket", emoji="🔒", style=discord.ButtonStyle.danger)
    async def cerrar(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("No eres staff.", ephemeral=True)

        modal = CloseModal(interaction.channel)
        await interaction.response.send_modal(modal)

# ==========================
# MODAL PARA CERRAR TICKET
# ==========================

class CloseModal(Modal):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(title="Cerrar ticket")
        self.channel = channel
        self.motivo = TextInput(label="Motivo del cierre", style=discord.TextStyle.paragraph)
        self.add_item(self.motivo)

    async def on_submit(self, interaction: discord.Interaction):
        # Intentar DM al creador usando el topic
        user = None
        tipo = "Ticket"
        if self.channel.topic:
            parts = self.channel.topic.split(";")
            data = {}
            for p in parts:
                if ":" in p:
                    k, v = p.split(":", 1)
                    data[k.strip()] = v.strip()
            user_id_str = data.get("user_id")
            tipo_label = data.get("tipo")
            if tipo_label:
                tipo = tipo_label
            if user_id_str and user_id_str.isdigit():
                user = interaction.guild.get_member(int(user_id_str))

        if user:
            try:
                embed = discord.Embed(
                    title=f"Tu ticket de {tipo} ha sido cerrado",
                    description=f"Motivo del cierre: {self.motivo.value}",
                    color=discord.Color.red()
                )
                await user.send(embed=embed)
            except:
                pass

        await interaction.response.send_message("Cerrando ticket...", ephemeral=True)
        await asyncio.sleep(1)
        await self.channel.delete()

# ==========================
# SELECT DEL PANEL
# ==========================

class TicketSelect(discord.ui.Select):
    def __init__(self):
        tipos = get_ticket_types()

        options = [
            discord.SelectOption(
                label=info["label"],
                description=info.get("description", "Sin descripción"),
                emoji=info.get("emoji", None),
                value=tipo
            )
            for tipo, info in tipos.items()
        ]

        super().__init__(
            placeholder="Selecciona un tipo de ticket",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        tipo = self.values[0]
        tipos = get_ticket_types()
        data = tipos[tipo]

        modal = TicketModal(tipo, data, interaction.user)
        await interaction.response.send_modal(modal)


class TicketPanel(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# ==========================
# COMANDO PANEL (EDITA Y ENVÍA)
# ==========================

@bot.tree.command(name="panel", description="Enviar panel de tickets (y editarlo)")
@owner_only()
@app_commands.describe(
    titulo="Título del panel (opcional)",
    descripcion="Descripción del panel (opcional)",
    color="Color del panel (nombre o HEX, opcional)"
)
async def panel(
    interaction: discord.Interaction,
    titulo: Optional[str] = None,
    descripcion: Optional[str] = None,
    color: Optional[str] = None
):
    panel_cfg = config["panel"]

    if titulo is not None:
        panel_cfg["title"] = titulo
    if descripcion is not None:
        panel_cfg["description"] = descripcion
    if color is not None:
        panel_cfg["color"] = color

    save_config()

    embed = discord.Embed(
        title=panel_cfg["title"],
        description=panel_cfg["description"],
        color=parse_color(panel_cfg["color"])
    )

    await interaction.response.send_message("Panel enviado y configuración actualizada.", ephemeral=True)
    await interaction.channel.send(embed=embed, view=TicketPanel())

# ==========================
# COMANDOS DE CONFIGURACIÓN BÁSICA
# ==========================

@bot.tree.command(name="config_solicitudes", description="Configura el canal donde llegarán las solicitudes")
@owner_only()
async def config_solicitudes(interaction: discord.Interaction, canal: discord.TextChannel):
    config["solicitudes_channel_id"] = canal.id
    save_config()
    await interaction.response.send_message(f"Canal de solicitudes configurado en {canal.mention}.", ephemeral=True)


@bot.tree.command(name="config_notis", description="Configura el canal de notificaciones públicas")
@owner_only()
async def config_notis(interaction: discord.Interaction, canal: discord.TextChannel):
    config["notify_channel_id"] = canal.id
    save_config()
    await interaction.response.send_message(f"Canal de notificaciones configurado en {canal.mention}.", ephemeral=True)


@bot.tree.command(name="config_staff", description="Añadir rol staff")
@owner_only()
async def config_staff(interaction: discord.Interaction, rol: discord.Role):
    if rol.id not in config["staff_roles"]:
        config["staff_roles"].append(rol.id)
        save_config()
    await interaction.response.send_message(f"Rol {rol.mention} añadido como staff.", ephemeral=True)

# ==========================
# COMANDO TIPOS DE TICKET
# ==========================

@bot.tree.command(name="ticket_type", description="Gestiona tipos de ticket")
@owner_only()
@app_commands.describe(
    nombre="Nombre interno del tipo (ej: reporte, soporte)",
    emoji="Emoji del tipo (opcional, ej: 🧾)",
    descripcion="Descripción del tipo (opcional)"
)
@app_commands.choices(
    accion=[
        app_commands.Choice(name="Añadir", value="add"),
        app_commands.Choice(name="Eliminar", value="remove")
    ]
)
async def ticket_type(
    interaction: discord.Interaction,
    accion: app_commands.Choice[str],
    nombre: str,
    emoji: Optional[str] = None,
    descripcion: Optional[str] = None
):
    tipos = config.setdefault("ticket_types", {})

    if accion.value == "add":
        if nombre in tipos:
            return await interaction.response.send_message("Ese tipo ya existe.", ephemeral=True)
        tipos[nombre] = {
            "emoji": emoji or "🎫",
            "label": nombre.capitalize(),
            "description": descripcion or "Sin descripción",
            "fields": {}
        }
        save_config()
        return await interaction.response.send_message(f"Tipo de ticket `{nombre}` añadido.", ephemeral=True)

    elif accion.value == "remove":
        if nombre not in tipos:
            return await interaction.response.send_message("Ese tipo no existe.", ephemeral=True)
        del tipos[nombre]
        save_config()
        return await interaction.response.send_message(f"Tipo de ticket `{nombre}` eliminado.", ephemeral=True)

# ==========================
# COMANDO FIELDS DE LOS MODALES
# ==========================

@bot.tree.command(name="ticket_field", description="Gestiona los campos de los modales de ticket")
@owner_only()
@app_commands.describe(
    tipo="Tipo de ticket al que quieres modificar los campos",
    nombre="Nombre del field (lo que aparecerá en el modal)",
    nuevo_nombre="Nuevo texto del field (solo para editar)"
)
@app_commands.choices(
    accion=[
        app_commands.Choice(name="Añadir", value="add"),
        app_commands.Choice(name="Editar", value="edit"),
        app_commands.Choice(name="Eliminar", value="remove")
    ]
)
async def ticket_field(
    interaction: discord.Interaction,
    accion: app_commands.Choice[str],
    tipo: str,
    nombre: str,
    nuevo_nombre: Optional[str] = None
):
    tipos = config.get("ticket_types", {})
    if tipo not in tipos:
        return await interaction.response.send_message("Ese tipo de ticket no existe.", ephemeral=True)

    fields = tipos[tipo].setdefault("fields", {})

    # Añadir
    if accion.value == "add":
        if nombre in fields:
            return await interaction.response.send_message("Ese field ya existe en este tipo.", ephemeral=True)
        fields[nombre] = nombre
        save_config()
        return await interaction.response.send_message(
            f"Field `{nombre}` añadido al tipo `{tipo}`.", ephemeral=True
        )

    # Editar
    if accion.value == "edit":
        if nombre not in fields:
            return await interaction.response.send_message("Ese field no existe en este tipo.", ephemeral=True)
        if not nuevo_nombre:
            return await interaction.response.send_message(
                "Debes indicar `nuevo_nombre` para editar el field.",
                ephemeral=True
            )
        # Renombrar label (y clave para mantenerlo limpio)
        old_value = fields.pop(nombre)
        fields[nuevo_nombre] = nuevo_nombre
        save_config()
        return await interaction.response.send_message(
            f"Field `{nombre}` renombrado a `{nuevo_nombre}` en el tipo `{tipo}`.",
            ephemeral=True
        )

    # Eliminar
    if accion.value == "remove":
        if nombre not in fields:
            return await interaction.response.send_message("Ese field no existe en este tipo.", ephemeral=True)
        del fields[nombre]
        save_config()
        return await interaction.response.send_message(
            f"Field `{nombre}` eliminado del tipo `{tipo}`.",
            ephemeral=True
        )

# ==========================
# ON READY
# ==========================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot iniciado como {bot.user}")

# ==========================
# RUN
# ==========================

bot.run(TOKEN) 
