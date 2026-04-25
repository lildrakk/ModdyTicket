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
            "solicitudes_channel_id": None,  # canal donde llegan las solicitudes
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
        cfg = json.load(f)

    # AUTOFIX: panel
    if "panel" not in cfg:
        cfg["panel"] = {
            "title": "Centro de Tickets",
            "description": "Selecciona un tipo de ticket",
            "color": "blue"
        }

    # AUTOFIX: canal de solicitudes
    if "solicitudes_channel_id" not in cfg:
        cfg["solicitudes_channel_id"] = None

    # AUTOFIX: notify_channel_id por si no existiera
    if "notify_channel_id" not in cfg:
        cfg["notify_channel_id"] = None

    # AUTOFIX: fields corruptos
    for tipo, info in cfg.get("ticket_types", {}).items():
        if isinstance(info.get("fields"), list):
            info["fields"] = {}

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)

    return cfg


def save_config():
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


# ==========================
# CARGAR CONFIG + AUTOFIX EXTRA
# ==========================

config = load_config()

if "panel" not in config:
    config["panel"] = {
        "title": "Centro de Tickets",
        "description": "Selecciona un tipo de ticket",
        "color": "blue"
    }
    save_config()

for tipo, info in config.get("ticket_types", {}).items():
    if isinstance(info.get("fields"), list):
        info["fields"] = {}
        save_config()


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
        except Exception:
            return discord.Color.blue()

    try:
        return discord.Color(int(color_str, 16))
    except Exception:
        return discord.Color.blue()


async def send_public_notification(guild, user, tipo, estado, extra=None):
    channel_id = config.get("notify_channel_id")
    if not channel_id:
        return

    channel = guild.get_channel(channel_id)
    if not channel:
        return

    embed = discord.Embed(
        title=f"Ticket de {tipo}",
        color=(
            discord.Color.yellow() if estado == "pendiente" else
            discord.Color.orange() if estado == "revision" else
            discord.Color.green() if estado == "aceptado" else
            discord.Color.red()
        )
    )

    if estado == "pendiente":
        embed.add_field(name="Estado", value="🟡 Pendiente", inline=False)

    elif estado == "revision":
        embed.add_field(name="Estado", value="🟠 En revisión", inline=False)
        if extra:
            embed.add_field(name="Staff", value=extra, inline=False)

    elif estado == "aceptado":
        embed.add_field(name="Estado", value="🟢 Aceptado", inline=False)
        if extra:
            embed.add_field(name="Motivo", value=extra, inline=False)

    elif estado == "rechazado":
        embed.add_field(name="Estado", value="🔴 Rechazado", inline=False)
        if extra:
            embed.add_field(name="Razón", value=extra, inline=False)

    await channel.send(content=user.mention, embed=embed) 



# ==========================
# SISTEMA DE SOLICITUDES (NUEVO)
# ==========================

class StaffRequestView(View):
    def __init__(self, user_id: int, tipo: str, tipo_data: dict, respuestas: dict):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.tipo = tipo
        self.tipo_data = tipo_data
        self.respuestas = respuestas

    @discord.ui.button(label="Aceptar", style=discord.ButtonStyle.success)
    async def aceptar(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("No eres staff.", ephemeral=True)

        modal = AcceptRequestModal(
            self.user_id, self.tipo, self.tipo_data, self.respuestas, interaction.message
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Rechazar", style=discord.ButtonStyle.danger)
    async def rechazar(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("No eres staff.", ephemeral=True)

        modal = RejectRequestModal(
            self.user_id, self.tipo, self.tipo_data, self.respuestas, interaction.message
        )
        await interaction.response.send_modal(modal)


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

        # Crear canal del ticket
        channel_name = f"{self.tipo}-{user.name}".replace(" ", "-")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        for role_id in config.get("staff_roles", []):
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        ticket_channel = await guild.create_text_channel(channel_name, overwrites=overwrites)

        # Embed dentro del ticket
        embed = discord.Embed(
            title=f"Ticket de {self.tipo_data['label']}",
            description="El staff te atenderá lo antes posible.",
            color=discord.Color.green()
        )

        await ticket_channel.send(
            content=f"{user.mention}",
            embed=embed,
            view=TicketView(user.id, self.tipo, self.tipo_data)
        )

        # Notificación pública
        await send_public_notification(
            guild, user, self.tipo_data["label"], "aceptado", extra=self.motivo.value
        )

        # Notificación al usuario por DM
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

        await interaction.response.send_message("Solicitud aceptada.", ephemeral=True)


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

        # Notificación pública
        await send_public_notification(
            guild, user, self.tipo_data["label"], "rechazado", extra=self.motivo.value
        )

        # Notificación al usuario por DM
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

        await interaction.response.send_message("Solicitud rechazada.", ephemeral=True)




# ==========================
# MODAL DEL USUARIO (ENVÍA SOLICITUD, NO TICKET)
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

        # Embed de solicitud para STAFF
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
        staff_ping = ""
        staff_roles = config.get("staff_roles", [])
        if staff_roles:
            menciones = []
            for rid in staff_roles:
                role = guild.get_role(rid)
                if role:
                    menciones.append(role.mention)
            if menciones:
                staff_ping = " ".join(menciones)

        await solicitudes_channel.send(content=staff_ping or None, embed=embed, view=view)

        # Notificación pública de solicitud pendiente
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

    @discord.ui.button(label="Reclamar", style=discord.ButtonStyle.primary)
    async def reclamar(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("No eres staff.", ephemeral=True)

        await interaction.response.send_message(
            f"Ticket reclamado por {interaction.user.mention}.",
            ephemeral=False
        )

        await send_public_notification(
            interaction.guild,
            interaction.guild.get_member(self.user_id),
            self.tipo_data["label"],
            "revision",
            extra=interaction.user.mention
        )

    @discord.ui.button(label="Cerrar ticket", style=discord.ButtonStyle.danger)
    async def cerrar(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("No eres staff.", ephemeral=True)

        modal = CloseModal(interaction.channel)
        await interaction.response.send_modal(modal)


# ==========================
# MODAL PARA CERRAR TICKET
# ==========================

class CloseModal(Modal):
    def __init__(self, channel):
        super().__init__(title="Cerrar ticket")
        self.channel = channel
        self.motivo = TextInput(label="Motivo del cierre", style=discord.TextStyle.paragraph)
        self.add_item(self.motivo)

    async def on_submit(self, interaction: discord.Interaction):
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
# COMANDO PARA ENVIAR PANEL
# ==========================

@bot.tree.command(name="panel", description="Enviar panel de tickets")
@owner_only()
async def panel(interaction: discord.Interaction):
    panel_cfg = config["panel"]

    embed = discord.Embed(
        title=panel_cfg["title"],
        description=panel_cfg["description"],
        color=parse_color(panel_cfg["color"])
    )

    await interaction.response.send_message(
        "Panel enviado.",
        ephemeral=True
    )

    await interaction.channel.send(embed=embed, view=TicketPanel())


# ==========================
# COMANDOS DE CONFIGURACIÓN
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
