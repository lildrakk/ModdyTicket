import os
import json
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select, Button, Modal, TextInput
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
# CONFIG JSON
# ==========================

def load_config():
    if not os.path.exists(CONFIG_PATH):
        default = {
            "staff_role_id": None,
            "staff_channel_id": None,
            "notify_channel_id": None,
            "panel_title": "Centro de Solicitudes",
            "panel_description": "Selecciona una opción del menú para enviar una solicitud.",
            "panel_color": 0x2f3136,
            "ticket_types": {
                "reporte": {
                    "label": "Reporte",
                    "description": "Reportar a un usuario",
                    "emoji": "⚠️",
                    "fields": {
                        "id_reportado": "ID del usuario reportado",
                        "motivo": "Motivo del reporte",
                        "pruebas": "Pruebas"
                    }
                },
                "soporte": {
                    "label": "Soporte",
                    "description": "Ayuda general",
                    "emoji": "🛠️",
                    "fields": {
                        "motivo": "Motivo",
                        "detalles": "Detalles adicionales"
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

def is_owner(user):
    return user.id == OWNER_ID

def is_staff(member):
    role_id = config.get("staff_role_id")
    if not role_id:
        return False
    return any(r.id == role_id for r in member.roles)


COLOR_MAP = {
    "rojo": 0xE74C3C,
    "azul": 0x3498DB,
    "azul oscuro": 0x1F2A3C,
    "verde": 0x2ECC71,
    "morado": 0x9B59B6,
    "naranja": 0xE67E22,
    "rosa": 0xE91E63,
    "amarillo": 0xF1C40F,
    "negro": 0x000000,
    "blanco": 0xFFFFFF,
    "gris": 0x95A5A6,
    "cian": 0x00FFFF,
    "turquesa": 0x1ABC9C,
}

def parse_color(text: str) -> int:
    text = text.lower().strip()
    if text in COLOR_MAP:
        return COLOR_MAP[text]
    t = text.replace("#", "").strip()
    try:
        return int(t, 16)
    except:
        return config.get("panel_color", 0x2f3136)


def owner_only():
    async def predicate(interaction):
        return is_owner(interaction.user)
    return app_commands.check(predicate)


# ==========================
# MODALES
# ==========================

class TicketModal(Modal):
    def __init__(self, ticket_type_key, ticket_type_data, user):
        self.ticket_type_key = ticket_type_key
        self.ticket_type_data = ticket_type_data
        self.creator = user

        super().__init__(title=f"Solicitud: {ticket_type_data['label']}", timeout=None)

        self.inputs = {}
        fields = ticket_type_data.get("fields", {})

        for field_key, visible_name in fields.items():
            label = visible_name or field_key.replace("_", " ").title()

            if field_key == "id_reportado":
                ti = TextInput(label=label, placeholder="Ej: 123456789012345678", required=True, max_length=32)
            elif field_key == "motivo":
                ti = TextInput(label=label, style=discord.TextStyle.paragraph, required=True, max_length=1024)
            else:
                ti = TextInput(label=label, style=discord.TextStyle.paragraph, required=False, max_length=1024)

            self.inputs[field_key] = ti
            self.add_item(ti)

    async def on_submit(self, interaction):
        staff_channel = interaction.guild.get_channel(config["staff_channel_id"])
        if not staff_channel:
            return await interaction.response.send_message("❌ No hay canal de staff configurado.", ephemeral=True)

        answers = {k: v.value for k, v in self.inputs.items()}
        safe_name = self.creator.name.replace(" ", "_")
        ticket_id = f"{self.ticket_type_key}-{safe_name}"

        embed = discord.Embed(
            title=f"📨 Nueva solicitud: {self.ticket_type_data['label']}",
            description=f"ID del ticket: `{ticket_id}`",
            color=discord.Color.blurple()
        )
        embed.add_field(name="👤 Usuario", value=f"{self.creator.mention}", inline=False)

        formatted = []
        for k, v in answers.items():
            if v:
                formatted.append(f"**{k.replace('_',' ').title()}:** {v}")

        if formatted:
            embed.add_field(name="📋 Detalles", value="\n".join(formatted), inline=False)

        embed.add_field(name="📌 Estado", value="🟡 Pendiente", inline=False)

        view = StaffTicketView(ticket_id, self.creator.id, self.ticket_type_key, self.ticket_type_data["label"], answers)

        await staff_channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Solicitud enviada.", ephemeral=True)


class ResolutionModal(Modal):
    def __init__(self, accepted, message, ticket_data):
        self.accepted = accepted
        self.message = message
        self.ticket_data = ticket_data

        super().__init__(title="Resolución: Aceptar" if accepted else "Resolución: Rechazar")

        self.reason = TextInput(
            label="Motivo de la resolución",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction):
        embed = self.message.embeds[0]
        old_fields = embed.fields
        embed.clear_fields()

        estado = "🟢 Aceptado" if self.accepted else "🔴 Rechazado"

        for f in old_fields:
            if f.name == "📌 Estado":
                embed.add_field(name="📌 Estado", value=estado, inline=False)
            else:
                embed.add_field(name=f.name, value=f.value, inline=f.inline)

        embed.add_field(name="💬 Resolución del staff", value=self.reason.value, inline=False)

        # Desactivar botones de aceptar/rechazar
        view = StaffTicketView(**self.ticket_data)
        for item in view.children:
            if isinstance(item, Button) and item.label in ("Aceptar", "Rechazar"):
                item.disabled = True

        await self.message.edit(embed=embed, view=view)

        # Notificación limpia
        notify = interaction.guild.get_channel(config["notify_channel_id"])
        creator = interaction.guild.get_member(self.ticket_data["creator_id"])

        if notify and creator:
            notif = discord.Embed(
                title=f"Resultado de tu solicitud: {self.ticket_data['ticket_type_label']}",
                color=discord.Color.green() if self.accepted else discord.Color.red()
            )
            notif.add_field(name="Estado", value=estado, inline=False)
            notif.add_field(name="Motivo de la resolución", value=self.reason.value, inline=False)

            await notify.send(content=creator.mention, embed=notif)

        await interaction.response.send_message("Resolución registrada.", ephemeral=True)


class CloseTicketModal(Modal):
    def __init__(self, message, ticket_data):
        self.message = message
        self.ticket_data = ticket_data

        super().__init__(title="Cerrar ticket")

        self.reason = TextInput(
            label="Razón del cierre",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction):
        creator = interaction.guild.get_member(self.ticket_data["creator_id"])
        claimer = interaction.guild.get_member(self.ticket_data.get("claimer_id"))

        # DM al creador
        if creator:
            try:
                dm = discord.Embed(
                    title="Tu ticket ha sido cerrado",
                    description=f"Razón: {self.reason.value}",
                    color=discord.Color.red()
                )
                await creator.send(embed=dm)
            except:
                pass

        # Mensaje en canal
        mentions = f"{creator.mention if creator else ''} {claimer.mention if claimer else interaction.user.mention}"

        embed = discord.Embed(
            title="🎫 Ticket cerrado",
            description=f"Este ticket ha sido cerrado por {interaction.user.mention}.\nSe eliminará en **5 segundos**.",
            color=discord.Color.red()
        )
        embed.add_field(name="Razón", value=self.reason.value, inline=False)

        await interaction.channel.send(content=mentions, embed=embed)

        # Desactivar botones
        closed = View()
        for label in ("Aceptar", "Rechazar", "Reclamar", "Cerrar ticket"):
            closed.add_item(Button(label=label, disabled=True))

        await self.message.edit(view=closed)

        await interaction.response.send_message("Ticket cerrado.", ephemeral=True)

        await asyncio.sleep(5)
        try:
            await self.message.delete()
        except:
            pass


# ==========================
# VISTAS
# ==========================

class StaffTicketView(View):
    def __init__(self, ticket_id, creator_id, ticket_type_key, ticket_type_label, answers):
        super().__init__(timeout=None)
        self.ticket_data = {
            "ticket_id": ticket_id,
            "creator_id": creator_id,
            "ticket_type_key": ticket_type_key,
            "ticket_type_label": ticket_type_label,
            "answers": answers,
            "claimer_id": None
        }

    @discord.ui.button(label="Aceptar", style=discord.ButtonStyle.success)
    async def aceptar(self, interaction, button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("Solo staff.", ephemeral=True)

        modal = ResolutionModal(True, interaction.message, self.ticket_data)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Rechazar", style=discord.ButtonStyle.danger)
    async def rechazar(self, interaction, button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("Solo staff.", ephemeral=True)

        modal = ResolutionModal(False, interaction.message, self.ticket_data)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Reclamar", style=discord.ButtonStyle.primary)
    async def reclamar(self, interaction, button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("Solo staff.", ephemeral=True)

        if self.ticket_data["claimer_id"]:
            return await interaction.response.send_message("Ya reclamado.", ephemeral=True)

        self.ticket_data["claimer_id"] = interaction.user.id
        button.disabled = True
        button.label = f"Reclamado por {interaction.user.display_name}"

        await interaction.message.edit(view=self)

        creator = interaction.guild.get_member(self.ticket_data["creator_id"])
        mentions = f"{creator.mention if creator else ''} {interaction.user.mention}"

        embed = discord.Embed(
            title="🎫 Ticket reclamado",
            description=f"Este ticket ha sido reclamado por {interaction.user.mention}",
            color=discord.Color.blue()
        )

        await interaction.channel.send(content=mentions, embed=embed)
        await interaction.response.send_message("Reclamado.", ephemeral=True)

    @discord.ui.button(label="Cerrar ticket", style=discord.ButtonStyle.secondary)
    async def cerrar(self, interaction, button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("Solo staff.", ephemeral=True)

        modal = CloseTicketModal(interaction.message, self.ticket_data)
        await interaction.response.send_modal(modal)


class TicketSelect(Select):
    def __init__(self):
        options = []
        for key, data in config["ticket_types"].items():
            options.append(discord.SelectOption(
                label=data["label"],
                description=data["description"],
                emoji=data["emoji"],
                value=key
            ))

        super().__init__(placeholder="Selecciona una opción", options=options)

    async def callback(self, interaction):
        modal = TicketModal(self.values[0], config["ticket_types"][self.values[0]], interaction.user)
        await interaction.response.send_modal(modal)


class PanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


@bot.event
async def on_ready():
    await bot.tree.sync()
    print("Bot listo") 



# ==========================
# COMANDOS OWNER (CONFIG)
# ==========================

@bot.tree.command(name="config_staffrol", description="Configura el rol de staff")
@owner_only()
async def config_staffrol(interaction, rol: discord.Role):
    config["staff_role_id"] = rol.id
    save_config()
    await interaction.response.send_message("Rol de staff configurado.", ephemeral=True)


@bot.tree.command(name="config_staffcanal", description="Configura el canal donde llegan las solicitudes")
@owner_only()
async def config_staffcanal(interaction, canal: discord.TextChannel):
    config["staff_channel_id"] = canal.id
    save_config()
    await interaction.response.send_message("Canal de staff configurado.", ephemeral=True)


@bot.tree.command(name="config_notificaciones", description="Configura el canal de notificaciones")
@owner_only()
async def config_notificaciones(interaction, canal: discord.TextChannel):
    config["notify_channel_id"] = canal.id
    save_config()
    await interaction.response.send_message("Canal de notificaciones configurado.", ephemeral=True)


# ==========================
# TICKET TYPES
# ==========================

@bot.tree.command(name="ticket_add", description="Añade un tipo de ticket")
@owner_only()
async def ticket_add(interaction, tipo: str, nombre: str, descripcion: str, emoji: str = None):
    tipo = tipo.lower()
    config["ticket_types"][tipo] = {
        "label": nombre,
        "description": descripcion,
        "emoji": emoji,
        "fields": {}
    }
    save_config()
    await interaction.response.send_message("Tipo añadido.", ephemeral=True)


@bot.tree.command(name="ticket_remove", description="Elimina un tipo de ticket")
@owner_only()
async def ticket_remove(interaction, tipo: str):
    tipo = tipo.lower()
    if tipo not in config["ticket_types"]:
        return await interaction.response.send_message("No existe.", ephemeral=True)

    del config["ticket_types"][tipo]
    save_config()
    await interaction.response.send_message("Tipo eliminado.", ephemeral=True)


@bot.tree.command(
    name="ticket_fields",
    description="Gestiona un field del modal (ejecuta este comando una vez por cada acción)"
)
@owner_only()
async def ticket_fields(interaction, tipo: str, accion: str, field: str, nombre: str = None):
    tipo = tipo.lower()
    accion = accion.lower()
    field = field.lower()

    if tipo not in config["ticket_types"]:
        return await interaction.response.send_message("Tipo no existe.", ephemeral=True)

    fields = config["ticket_types"][tipo]["fields"]

    if accion in ("añadir", "anadir", "editar"):
        if not nombre:
            return await interaction.response.send_message("Falta nombre.", ephemeral=True)
        fields[field] = nombre
        save_config()
        return await interaction.response.send_message("Field actualizado.", ephemeral=True)

    if accion == "eliminar":
        if field not in fields:
            return await interaction.response.send_message("Field no existe.", ephemeral=True)
        del fields[field]
        save_config()
        return await interaction.response.send_message("Field eliminado.", ephemeral=True)

    await interaction.response.send_message("Acción inválida.", ephemeral=True)


# ==========================
# PANEL
# ==========================

@bot.tree.command(name="panel", description="Envía el panel de tickets")
@owner_only()
async def panel(interaction, canal: discord.TextChannel, titulo: str, descripcion: str, color: str):
    config["panel_title"] = titulo
    config["panel_description"] = descripcion
    config["panel_color"] = parse_color(color)
    save_config()

    embed = discord.Embed(
        title=titulo,
        description=descripcion,
        color=config["panel_color"]
    )

    await canal.send(embed=embed, view=PanelView())
    await interaction.response.send_message("Panel enviado.", ephemeral=True)


# ==========================
# LEAVE ALL
# ==========================

@bot.tree.command(name="leave_all", description="El bot abandona todos los servidores")
async def leave_all(interaction):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("No autorizado.", ephemeral=True)

    count = 0
    for g in bot.guilds:
        try:
            await g.leave()
            count += 1
        except:
            pass

    await interaction.response.send_message(f"Salí de {count} servidores.", ephemeral=True) 



# ==========================
# RUN
# ==========================

bot.run(TOKEN)
