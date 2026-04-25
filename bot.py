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

def is_owner(user: discord.abc.User | discord.Member) -> bool:
    return user.id == OWNER_ID


def is_staff(member: discord.Member) -> bool:
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
    except ValueError:
        return config.get("panel_color", 0x2f3136)


def owner_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        return is_owner(interaction.user)
    return app_commands.check(predicate)


def get_ticket_types_dict() -> dict:
    return config.get("ticket_types", {})


# ==========================
# MODALES
# ==========================

class TicketModal(Modal):
    def __init__(self, ticket_type_key: str, ticket_type_data: dict, user: discord.Member):
        self.ticket_type_key = ticket_type_key
        self.ticket_type_data = ticket_type_data
        self.creator = user

        super().__init__(title=f"Solicitud: {ticket_type_data['label']}", timeout=None)

        self.inputs: dict[str, TextInput] = {}

        fields = ticket_type_data.get("fields", {})
        # Soportar formato antiguo (lista)
        if isinstance(fields, list):
            fields = {k: k.replace("_", " ").title() for k in fields}

        # Discord solo permite 5 inputs por modal
        for field_key, visible_name in list(fields.items())[:5]:
            label = visible_name or field_key.replace("_", " ").title()

            if field_key == "id_reportado":
                ti = TextInput(
                    label=label,
                    placeholder="Ejemplo: 123456789012345678",
                    required=True,
                    max_length=32
                )
            elif field_key == "motivo":
                ti = TextInput(
                    label=label,
                    style=discord.TextStyle.paragraph,
                    placeholder="Explica el motivo.",
                    required=True,
                    max_length=1024
                )
            else:
                ti = TextInput(
                    label=label,
                    style=discord.TextStyle.paragraph,
                    required=False,
                    max_length=1024
                )

            self.inputs[field_key] = ti
            self.add_item(ti)

    async def on_submit(self, interaction: discord.Interaction):
        staff_channel_id = config.get("staff_channel_id")
        if not staff_channel_id:
            return await interaction.response.send_message(
                "❌ No hay canal de staff configurado.",
                ephemeral=True
            )

        guild = interaction.guild
        staff_channel = guild.get_channel(staff_channel_id)
        if not isinstance(staff_channel, discord.TextChannel):
            return await interaction.response.send_message(
                "❌ El canal de staff configurado ya no existe.",
                ephemeral=True
            )

        answers = {k: str(v.value).strip() for k, v in self.inputs.items()}

        safe_name = self.creator.name.replace(" ", "_")
        ticket_id = f"{self.ticket_type_key}-{safe_name}"

        embed = discord.Embed(
            title=f"📨 Nueva solicitud: {self.ticket_type_data['label']}",
            description=f"ID del ticket: `{ticket_id}`",
            color=discord.Color.blurple()
        )
        embed.add_field(name="👤 Usuario", value=f"{self.creator.mention} (`{self.creator.id}`)", inline=False)
        embed.add_field(name="📂 Tipo", value=self.ticket_type_data["label"], inline=True)

        formatted = []
        for k, v in answers.items():
            if not v:
                continue
            pretty = k.replace("_", " ").title()
            formatted.append(f"**{pretty}:** {v}")

        if formatted:
            embed.add_field(name="📋 Detalles", value="\n".join(formatted), inline=False)

        embed.add_field(name="📌 Estado", value="🟡 Pendiente", inline=False)

        view = StaffTicketView(
            ticket_id=ticket_id,
            creator_id=self.creator.id,
            ticket_type_key=self.ticket_type_key,
            ticket_type_label=self.ticket_type_data["label"],
            answers=answers,
            claimer_id=None
        )

        staff_role_id = config.get("staff_role_id")
        content = None
        if staff_role_id:
            role = guild.get_role(staff_role_id)
            if role:
                content = role.mention

        await staff_channel.send(content=content, embed=embed, view=view)
        await interaction.response.send_message("✅ Solicitud enviada.", ephemeral=True)


class ResolutionModal(Modal):
    def __init__(self, accepted: bool, message: discord.Message, ticket_data: dict):
        self.accepted = accepted
        self.message = message
        self.ticket_data = ticket_data

        super().__init__(title="Resolución: Aceptar" if accepted else "Resolución: Rechazar", timeout=None)

        self.reason_input = TextInput(
            label="Motivo de la resolución",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1024
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        notify_channel_id = config.get("notify_channel_id")
        guild = interaction.guild

        reason = str(self.reason_input.value).strip()
        ticket_id = self.ticket_data["ticket_id"]
        creator_id = self.ticket_data["creator_id"]
        ticket_type_label = self.ticket_data["ticket_type_label"]
        answers = self.ticket_data["answers"]
        claimer_id = self.ticket_data.get("claimer_id")

        original = self.message
        if not original:
            return await interaction.response.send_message(
                "❌ No se encontró el mensaje original del ticket.",
                ephemeral=True
            )

        embed = original.embeds[0] if original.embeds else discord.Embed(color=discord.Color.blurple())
        estado_texto = "🟢 Aceptado" if self.accepted else "🔴 Rechazado"

        old_fields = embed.fields
        embed.clear_fields()
        for field in old_fields:
            if field.name == "📌 Estado":
                embed.add_field(name="📌 Estado", value=estado_texto, inline=False)
            else:
                embed.add_field(name=field.name, value=field.value, inline=field.inline)

        embed.add_field(
            name="💬 Resolución del staff",
            value=reason,
            inline=False
        )
        embed.set_footer(text=f"Revisado por {interaction.user} ({interaction.user.id})")

        # Recrear vista y desactivar aceptar/rechazar
        new_view = StaffTicketView(
            ticket_id=ticket_id,
            creator_id=creator_id,
            ticket_type_key=self.ticket_data["ticket_type_key"],
            ticket_type_label=ticket_type_label,
            answers=answers,
            claimer_id=claimer_id
        )
        for item in new_view.children:
            if isinstance(item, Button) and item.label in ("Aceptar", "Rechazar"):
                item.disabled = True

        await original.edit(embed=embed, view=new_view)

        # Notificación limpia al canal público
        notify_channel = guild.get_channel(notify_channel_id) if notify_channel_id else None
        creator = guild.get_member(creator_id)

        if notify_channel and isinstance(notify_channel, discord.TextChannel) and creator:
            notif_embed = discord.Embed(
                title=f"Resultado de tu solicitud: {ticket_type_label}",
                color=discord.Color.green() if self.accepted else discord.Color.red()
            )
            notif_embed.add_field(name="ID del ticket", value=f"`{ticket_id}`", inline=False)
            notif_embed.add_field(name="Estado", value=estado_texto, inline=False)
            notif_embed.add_field(
                name="Moderador",
                value=f"{interaction.user.mention} (`{interaction.user.id}`)",
                inline=False
            )
            notif_embed.add_field(
                name="Motivo de la resolución",
                value=reason,
                inline=False
            )

            await notify_channel.send(content=creator.mention, embed=notif_embed)

        await interaction.response.send_message("✅ Resolución registrada.", ephemeral=True)


class CloseTicketModal(Modal):
    def __init__(self, message: discord.Message, ticket_data: dict):
        self.message = message
        self.ticket_data = ticket_data

        super().__init__(title="Cerrar ticket", timeout=None)

        self.reason_input = TextInput(
            label="Razón del cierre",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1024
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        reason = str(self.reason_input.value).strip()

        ticket_id = self.ticket_data["ticket_id"]
        creator_id = self.ticket_data["creator_id"]
        ticket_type_label = self.ticket_data["ticket_type_label"]
        answers = self.ticket_data["answers"]
        claimer_id = self.ticket_data.get("claimer_id")

        original = self.message
        if not original:
            return await interaction.response.send_message(
                "❌ No se encontró el mensaje original del ticket.",
                ephemeral=True
            )

        creator = guild.get_member(creator_id)
        claimer = guild.get_member(claimer_id) if claimer_id else None

        # DM al creador
        if creator:
            dm_embed = discord.Embed(
                title=f"Tu ticket ha sido cerrado: {ticket_type_label}",
                color=discord.Color.red()
            )
            dm_embed.add_field(name="ID del ticket", value=f"`{ticket_id}`", inline=False)
            dm_embed.add_field(
                name="Cerrado por",
                value=f"{interaction.user.mention} (`{interaction.user.id}`)",
                inline=False
            )
            dm_embed.add_field(name="Razón del cierre", value=reason, inline=False)

            if answers:
                formatted = []
                for k, v in answers.items():
                    if not v:
                        continue
                    pretty = k.replace("_", " ").title()
                    formatted.append(f"**{pretty}:** {v}")
                if formatted:
                    dm_embed.add_field(
                        name="Detalles del ticket",
                        value="\n".join(formatted),
                        inline=False
                    )

            try:
                await creator.send(embed=dm_embed)
            except:
                pass

        # Mensaje en canal (no ephemeral)
        mentions = []
        if creator:
            mentions.append(creator.mention)
        if claimer:
            mentions.append(claimer.mention)
        else:
            mentions.append(interaction.user.mention)

        content = " ".join(mentions)

        close_embed = discord.Embed(
            title="🎫 Ticket cerrado",
            description=f"Este ticket ha sido cerrado por {interaction.user.mention}.\n"
                        f"El ticket será cerrado en **5 segundos**.",
            color=discord.Color.red()
        )
        close_embed.add_field(name="Razón del cierre", value=reason, inline=False)

        await interaction.channel.send(content=content, embed=close_embed)

        # Actualizar embed original a estado cerrado y desactivar botones
        embed = original.embeds[0] if original.embeds else discord.Embed(color=discord.Color.blurple())
        old_fields = embed.fields
        embed.clear_fields()
        for field in old_fields:
            if field.name == "📌 Estado":
                embed.add_field(name="📌 Estado", value="⚫ Cerrado", inline=False)
            else:
                embed.add_field(name=field.name, value=field.value, inline=field.inline)

        closed_view = View(timeout=None)
        for label, style in (
            ("Aceptar", discord.ButtonStyle.success),
            ("Rechazar", discord.ButtonStyle.danger),
            ("Reclamar", discord.ButtonStyle.primary),
            ("Cerrar ticket", discord.ButtonStyle.secondary),
        ):
            closed_view.add_item(Button(label=label, style=style, disabled=True))

        await original.edit(embed=embed, view=closed_view)

        await interaction.response.send_message("✅ Ticket cerrado. Eliminando en 5 segundos...", ephemeral=True)

        await asyncio.sleep(5)
        try:
            await original.delete()
        except:
            pass


# ==========================
# VISTAS
# ==========================

class StaffTicketView(View):
    def __init__(
        self,
        ticket_id: str,
        creator_id: int,
        ticket_type_key: str,
        ticket_type_label: str,
        answers: dict,
        claimer_id: int | None = None
    ):
        super().__init__(timeout=None)
        self.ticket_data = {
            "ticket_id": ticket_id,
            "creator_id": creator_id,
            "ticket_type_key": ticket_type_key,
            "ticket_type_label": ticket_type_label,
            "answers": answers,
            "claimer_id": claimer_id
        }

    @discord.ui.button(label="Aceptar", style=discord.ButtonStyle.success)
    async def aceptar(self, interaction: discord.Interaction, button: Button):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Solo el staff puede usar esto.", ephemeral=True)

        modal = ResolutionModal(True, interaction.message, self.ticket_data)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Rechazar", style=discord.ButtonStyle.danger)
    async def rechazar(self, interaction: discord.Interaction, button: Button):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Solo el staff puede usar esto.", ephemeral=True)

        modal = ResolutionModal(False, interaction.message, self.ticket_data)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Reclamar", style=discord.ButtonStyle.primary)
    async def reclamar(self, interaction: discord.Interaction, button: Button):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Solo el staff puede reclamar tickets.", ephemeral=True)

        if self.ticket_data.get("claimer_id"):
            return await interaction.response.send_message("❌ Este ticket ya ha sido reclamado.", ephemeral=True)

        self.ticket_data["claimer_id"] = interaction.user.id
        button.disabled = True
        button.label = f"Reclamado por {interaction.user.display_name}"

        await interaction.message.edit(view=self)

        creator = interaction.guild.get_member(self.ticket_data["creator_id"])
        mentions = []
        if creator:
            mentions.append(creator.mention)
        mentions.append(interaction.user.mention)

        content = " ".join(mentions)
        embed = discord.Embed(
            title="🎫 Ticket reclamado",
            description=f"Este ticket ha sido reclamado por {interaction.user.mention} 🎫",
            color=discord.Color.blue()
        )

        await interaction.channel.send(content=content, embed=embed)
        await interaction.response.send_message("✅ Has reclamado este ticket.", ephemeral=True)

    @discord.ui.button(label="Cerrar ticket", style=discord.ButtonStyle.secondary)
    async def cerrar(self, interaction: discord.Interaction, button: Button):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Solo el staff puede cerrar tickets.", ephemeral=True)

        modal = CloseTicketModal(interaction.message, self.ticket_data)
        await interaction.response.send_modal(modal)


class TicketSelect(Select):
    def __init__(self):
        options = []
        for key, data in get_ticket_types_dict().items():
            options.append(discord.SelectOption(
                label=data.get("label", key),
                description=data.get("description", "Sin descripción")[:100],
                emoji=data.get("emoji"),
                value=key
            ))

        super().__init__(
            placeholder="Selecciona una opción",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("❌ Solo miembros del servidor.", ephemeral=True)

        ticket_type_key = self.values[0]
        ticket_type_data = get_ticket_types_dict().get(ticket_type_key)
        if not ticket_type_data:
            return await interaction.response.send_message("❌ Este tipo ya no existe.", ephemeral=True)

        modal = TicketModal(ticket_type_key, ticket_type_data, interaction.user)
        await interaction.response.send_modal(modal)


class PanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        if get_ticket_types_dict():
            self.add_item(TicketSelect())


# ==========================
# EVENTOS
# ==========================

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception:
        pass
    print(f"Bot listo como {bot.user} ({bot.user.id})")



# ==========================
# COMANDOS OWNER (CONFIG)
# ==========================

@bot.tree.command(name="config_staffrol", description="Configura el rol de staff")
@owner_only()
async def config_staffrol(interaction: discord.Interaction, rol: discord.Role):
    config["staff_role_id"] = rol.id
    save_config()
    await interaction.response.send_message(f"✅ Rol de staff configurado: {rol.mention}", ephemeral=True)


@bot.tree.command(name="config_staffcanal", description="Configura el canal donde llegan las solicitudes")
@owner_only()
async def config_staffcanal(interaction: discord.Interaction, canal: discord.TextChannel):
    config["staff_channel_id"] = canal.id
    save_config()
    await interaction.response.send_message(f"✅ Canal de staff configurado: {canal.mention}", ephemeral=True)


@bot.tree.command(name="config_notificaciones", description="Configura el canal de notificaciones para los usuarios")
@owner_only()
async def config_notificaciones(interaction: discord.Interaction, canal: discord.TextChannel):
    config["notify_channel_id"] = canal.id
    save_config()
    await interaction.response.send_message(f"✅ Canal de notificaciones configurado: {canal.mention}", ephemeral=True)


# ==========================
# TICKET TYPES
# ==========================

@bot.tree.command(name="ticket_add", description="Añade un tipo de ticket al select")
@owner_only()
@app_commands.describe(
    tipo="ID interno del tipo (ej: reporte, soporte)",
    nombre="Nombre visible en el select",
    descripcion="Descripción que se verá en el select",
    emoji="Emoji opcional (ej: ⚠️, 🛠️)"
)
async def ticket_add(
    interaction: discord.Interaction,
    tipo: str,
    nombre: str,
    descripcion: str,
    emoji: str | None = None
):
    tipo = tipo.lower().strip()
    ticket_types = get_ticket_types_dict()
    ticket_types[tipo] = {
        "label": nombre,
        "description": descripcion,
        "emoji": emoji,
        "fields": {}
    }
    config["ticket_types"] = ticket_types
    save_config()
    await interaction.response.send_message(
        f"✅ Tipo de ticket añadido: `{tipo}` → **{nombre}**",
        ephemeral=True
    )


@bot.tree.command(name="ticket_remove", description="Elimina un tipo de ticket del select")
@owner_only()
@app_commands.describe(
    tipo="Selecciona el tipo a eliminar"
)
async def ticket_remove(interaction: discord.Interaction, tipo: str):
    tipo = tipo.lower().strip()
    ticket_types = get_ticket_types_dict()
    if tipo not in ticket_types:
        return await interaction.response.send_message("❌ Ese tipo no existe.", ephemeral=True)

    del ticket_types[tipo]
    config["ticket_types"] = ticket_types
    save_config()
    await interaction.response.send_message(f"✅ Tipo `{tipo}` eliminado.", ephemeral=True)


@ticket_remove.autocomplete("tipo")
async def ticket_remove_autocomplete(
    interaction: discord.Interaction,
    current: str
):
    current = current.lower()
    choices = []
    for key, data in get_ticket_types_dict().items():
        if current in key.lower() or current in data.get("label", "").lower():
            choices.append(app_commands.Choice(name=data.get("label", key), value=key))
    return choices[:25]


# ==========================
# TICKET FIELDS (CON ACCIÓN)
# ==========================

@bot.tree.command(
    name="ticket_fields",
    description="Gestiona un field del modal (ejecuta este comando una vez por cada acción)."
)
@owner_only()
@app_commands.describe(
    tipo="Tipo de ticket al que pertenece el field",
    accion="Acción a realizar",
    field="Nombre interno del field (ej: id_reportado, motivo)",
    nombre="Nombre visible del field (solo para añadir/editar)"
)
@app_commands.choices(
    accion=[
        app_commands.Choice(name="Añadir", value="añadir"),
        app_commands.Choice(name="Editar", value="editar"),
        app_commands.Choice(name="Eliminar", value="eliminar"),
    ]
)
async def ticket_fields(
    interaction: discord.Interaction,
    tipo: str,
    accion: app_commands.Choice[str],
    field: str,
    nombre: str | None = None
):
    """
    IMPORTANTE:
    - Ejecuta este comando UNA VEZ por cada field que quieras añadir, editar o eliminar.
    - Discord no permite listas múltiples en un solo parámetro.
    """
    tipo = tipo.lower().strip()
    accion_val = accion.value
    field = field.lower().strip()

    ticket_types = get_ticket_types_dict()
    if tipo not in ticket_types:
        return await interaction.response.send_message("❌ Ese tipo de ticket no existe.", ephemeral=True)

    fields_dict = ticket_types[tipo].get("fields", {})
    if isinstance(fields_dict, list):
        fields_dict = {k: k.replace("_", " ").title() for k in fields_dict}

    if accion_val in ("añadir", "editar"):
        if not nombre:
            return await interaction.response.send_message(
                "❌ Debes indicar `nombre` para añadir o editar.",
                ephemeral=True
            )
        fields_dict[field] = nombre
        ticket_types[tipo]["fields"] = fields_dict
        config["ticket_types"] = ticket_types
        save_config()
        return await interaction.response.send_message(
            f"✅ Field **{field}** {'añadido' if accion_val == 'añadir' else 'editado'} en `{tipo}` como **{nombre}**.",
            ephemeral=True
        )

    if accion_val == "eliminar":
        if field not in fields_dict:
            return await interaction.response.send_message(
                "❌ Ese field no existe en este tipo.",
                ephemeral=True
            )
        del fields_dict[field]
        ticket_types[tipo]["fields"] = fields_dict
        config["ticket_types"] = ticket_types
        save_config()
        return await interaction.response.send_message(
            f"✅ Field **{field}** eliminado de `{tipo}`.",
            ephemeral=True
        )


@ticket_fields.autocomplete("tipo")
async def ticket_fields_tipo_autocomplete(
    interaction: discord.Interaction,
    current: str
):
    current = current.lower()
    choices = []
    for key, data in get_ticket_types_dict().items():
        if current in key.lower() or current in data.get("label", "").lower():
            choices.append(app_commands.Choice(name=data.get("label", key), value=key))
    return choices[:25]


# ==========================
# PANEL
# ==========================

@bot.tree.command(name="panel", description="Envía el panel de solicitudes con el select actualizado")
@owner_only()
@app_commands.describe(
    canal="Canal donde se enviará el panel",
    titulo="Título del panel",
    descripcion="Descripción del panel",
    color="Color (nombre o HEX). Ej: azul oscuro, #3498db"
)
async def panel(
    interaction: discord.Interaction,
    canal: discord.TextChannel,
    titulo: str,
    descripcion: str,
    color: str
):
    if not get_ticket_types_dict():
        return await interaction.response.send_message(
            "❌ No hay tipos de ticket configurados. Usa `/ticket_add` primero.",
            ephemeral=True
        )

    config["panel_title"] = titulo
    config["panel_description"] = descripcion
    config["panel_color"] = parse_color(color)
    save_config()

    embed = discord.Embed(
        title=config["panel_title"],
        description=config["panel_description"],
        color=config["panel_color"]
    )
    embed.set_footer(text="Selecciona una opción del menú para enviar tu solicitud.")

    view = PanelView()
    await canal.send(embed=embed, view=view)
    await interaction.response.send_message(
        f"✅ Panel enviado a {canal.mention}",
        ephemeral=True
    )


# ==========================
# PANEL_CLEAR (ELIMINAR SELECTS)
# ==========================

@bot.tree.command(name="panel_clear", description="Elimina los mensajes de panel con select en un canal")
@owner_only()
@app_commands.describe(
    canal="Canal donde están los paneles a eliminar",
    limite="Número máximo de mensajes a revisar (por defecto 50)"
)
async def panel_clear(
    interaction: discord.Interaction,
    canal: discord.TextChannel,
    limite: int = 50
):
    borrados = 0
    async for msg in canal.history(limit=limite):
        if msg.author == interaction.client.user and msg.components:
            try:
                await msg.delete()
                borrados += 1
            except:
                pass

    await interaction.response.send_message(
        f"✅ Paneles eliminados en {canal.mention}: **{borrados}**",
        ephemeral=True
    )


# ==========================
# LEAVE ALL
# ==========================

@bot.tree.command(name="leave_all", description="El bot abandona todos los servidores")
async def leave_all(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ No tienes permiso para usar este comando.", ephemeral=True)

    count = 0
    for guild in bot.guilds:
        try:
            await guild.leave()
            count += 1
        except:
            pass

    await interaction.response.send_message(
        f"✅ El bot ha salido de **{count}** servidores.",
        ephemeral=True
        )


# ==========================
# RUN
# ==========================

bot.run(TOKEN)
