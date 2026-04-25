import os
import json
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
                # Ejemplos iniciales (puedes borrarlos con /ticket_remove)
                "reporte": {
                    "label": "Reporte",
                    "description": "Reportar a un usuario",
                    "emoji": "⚠️",
                    "fields": ["id_reportado", "motivo", "pruebas"]
                },
                "soporte": {
                    "label": "Soporte",
                    "description": "Ayuda general",
                    "emoji": "🛠️",
                    "fields": ["motivo", "detalles"]
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


# ==========================
# MODALES
# ==========================

class TicketModal(Modal):
    def __init__(self, ticket_type_key: str, ticket_type_data: dict, user: discord.Member):
        self.ticket_type_key = ticket_type_key
        self.ticket_type_data = ticket_type_data
        self.creator = user

        title = f"Solicitud: {ticket_type_data['label']}"
        super().__init__(title=title, timeout=None)

        self.inputs = {}
        for field in ticket_type_data.get("fields", []):
            if field == "id_reportado":
                ti = TextInput(
                    label="ID del usuario reportado",
                    placeholder="Ejemplo: 123456789012345678",
                    required=True,
                    max_length=32
                )
            elif field == "motivo":
                ti = TextInput(
                    label="Motivo",
                    style=discord.TextStyle.paragraph,
                    placeholder="Explica el motivo de tu solicitud.",
                    required=True,
                    max_length=1024
                )
            elif field == "pruebas":
                ti = TextInput(
                    label="Pruebas (links, descripción, etc.)",
                    style=discord.TextStyle.paragraph,
                    required=False,
                    max_length=1024
                )
            elif field == "detalles":
                ti = TextInput(
                    label="Detalles adicionales",
                    style=discord.TextStyle.paragraph,
                    required=False,
                    max_length=1024
                )
            elif field == "id_moderador":
                ti = TextInput(
                    label="ID del moderador que te sancionó",
                    required=True,
                    max_length=32
                )
            else:
                ti = TextInput(
                    label=field.replace("_", " ").title(),
                    style=discord.TextStyle.paragraph,
                    required=False,
                    max_length=1024
                )

            self.inputs[field] = ti
            self.add_item(ti)

    async def on_submit(self, interaction: discord.Interaction):
        staff_channel_id = config.get("staff_channel_id")
        if not staff_channel_id:
            return await interaction.response.send_message(
                "❌ No hay canal de staff configurado. Contacta con la administración.",
                ephemeral=True
            )

        guild = interaction.guild
        staff_channel = guild.get_channel(staff_channel_id)
        if not isinstance(staff_channel, discord.TextChannel):
            return await interaction.response.send_message(
                "❌ El canal de staff configurado ya no existe.",
                ephemeral=True
            )

        # Recoger respuestas
        answers = {}
        for key, ti in self.inputs.items():
            answers[key] = str(ti.value).strip()

        ticket_type_key = self.ticket_type_key
        ticket_type_data = self.ticket_type_data

        # ID tipo-usuario
        safe_name = self.creator.name.replace(" ", "_")
        ticket_id = f"{ticket_type_key}-{safe_name}"

        # Embed para staff
        embed = discord.Embed(
            title=f"📨 Nueva solicitud: {ticket_type_data['label']}",
            description=f"ID del ticket: `{ticket_id}`",
            color=discord.Color.blurple()
        )
        embed.add_field(name="👤 Usuario", value=f"{self.creator.mention} (`{self.creator.id}`)", inline=False)
        embed.add_field(name="📂 Tipo", value=ticket_type_data["label"], inline=True)

        if answers:
            formatted = []
            for k, v in answers.items():
                if not v:
                    continue
                pretty = k.replace("_", " ").title()
                formatted.append(f"**{pretty}:** {v}")
            if formatted:
                embed.add_field(name="📋 Detalles de la solicitud", value="\n".join(formatted), inline=False)

        embed.add_field(name="📌 Estado", value="🟡 Pendiente de revisión", inline=False)

        view = StaffTicketView(
            ticket_id=ticket_id,
            creator_id=self.creator.id,
            ticket_type_key=ticket_type_key,
            ticket_type_label=ticket_type_data["label"],
            answers=answers
        )

        staff_role_id = config.get("staff_role_id")
        content = None
        if staff_role_id:
            role = guild.get_role(staff_role_id)
            if role:
                content = role.mention

        await staff_channel.send(content=content, embed=embed, view=view)
        await interaction.response.send_message(
            "✅ Tu solicitud ha sido enviada. El staff la revisará en breve.",
            ephemeral=True
        )


class VerdictModal(Modal):
    def __init__(self, *, accepted: bool, message: discord.Message, ticket_data: dict):
        self.accepted = accepted
        self.message = message
        self.ticket_data = ticket_data

        title = "Veredicto: Aceptar" if accepted else "Veredicto: Rechazar"
        super().__init__(title=title, timeout=None)

        label = "Motivo del veredicto" if accepted else "Razón del rechazo"
        self.reason_input = TextInput(
            label=label,
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

        # Editar embed del mensaje de staff
        original = self.message
        if not original:
            return await interaction.response.send_message(
                "❌ No se pudo encontrar el mensaje original del ticket.",
                ephemeral=True
            )

        embed = original.embeds[0] if original.embeds else discord.Embed(color=discord.Color.blurple())
        # Actualizar estado
        estado_texto = "🟢 Aceptado" if self.accepted else "🔴 Rechazado"
        # Reemplazar o añadir campo de estado
        new_fields = []
        for field in embed.fields:
            if field.name == "📌 Estado":
                new_fields.append(discord.EmbedField(name="📌 Estado", value=estado_texto, inline=False))
            else:
                new_fields.append(field)
        embed.clear_fields()
        for f in new_fields:
            embed.add_field(name=f.name, value=f.value, inline=f.inline)

        # Añadir veredicto
        embed.add_field(
            name="💬 Veredicto del staff",
            value=reason,
            inline=False
        )
        embed.set_footer(text=f"Revisado por {interaction.user} ({interaction.user.id})")

        # Desactivar botones
        disabled_view = View(timeout=None)
        disabled_view.add_item(Button(label="Aceptar", style=discord.ButtonStyle.success, disabled=True))
        disabled_view.add_item(Button(label="Rechazar", style=discord.ButtonStyle.danger, disabled=True))

        await original.edit(embed=embed, view=disabled_view)

        # Notificación al usuario
        notify_channel = guild.get_channel(notify_channel_id) if notify_channel_id else None
        creator = guild.get_member(creator_id)

        if notify_channel and isinstance(notify_channel, discord.TextChannel) and creator:
            notif_embed = discord.Embed(
                title=f"Resultado de tu solicitud: {ticket_type_label}",
                color=discord.Color.green() if self.accepted else discord.Color.red()
            )
            notif_embed.add_field(name="ID del ticket", value=f"`{ticket_id}`", inline=False)
            notif_embed.add_field(
                name="Estado",
                value="🟢 Aceptado" if self.accepted else "🔴 Rechazado",
                inline=False
            )
            notif_embed.add_field(
                name="Moderador",
                value=f"{interaction.user.mention} (`{interaction.user.id}`)",
                inline=False
            )

            if answers:
                formatted = []
                for k, v in answers.items():
                    if not v:
                        continue
                    pretty = k.replace("_", " ").title()
                    formatted.append(f"**{pretty}:** {v}")
                if formatted:
                    notif_embed.add_field(
                        name="Tus respuestas",
                        value="\n".join(formatted),
                        inline=False
                    )

            notif_embed.add_field(
                name="Motivo del veredicto",
                value=reason,
                inline=False
            )

            await notify_channel.send(content=creator.mention, embed=notif_embed)

        await interaction.response.send_message("✅ Veredicto registrado.", ephemeral=True)


# ==========================
# VISTAS
# ==========================

class StaffTicketView(View):
    def __init__(self, ticket_id: str, creator_id: int, ticket_type_key: str, ticket_type_label: str, answers: dict):
        super().__init__(timeout=None)
        self.ticket_data = {
            "ticket_id": ticket_id,
            "creator_id": creator_id,
            "ticket_type_key": ticket_type_key,
            "ticket_type_label": ticket_type_label,
            "answers": answers
        }

    @discord.ui.button(label="Aceptar", style=discord.ButtonStyle.success)
    async def aceptar(self, interaction: discord.Interaction, button: Button):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Solo el staff puede usar este botón.",
                ephemeral=True
            )

        modal = VerdictModal(accepted=True, message=interaction.message, ticket_data=self.ticket_data)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Rechazar", style=discord.ButtonStyle.danger)
    async def rechazar(self, interaction: discord.Interaction, button: Button):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Solo el staff puede usar este botón.",
                ephemeral=True
            )

        modal = VerdictModal(accepted=False, message=interaction.message, ticket_data=self.ticket_data)
        await interaction.response.send_modal(modal)


class TicketSelect(Select):
    def __init__(self):
        options = []
        for key, data in config.get("ticket_types", {}).items():
            label = data.get("label", key)
            description = data.get("description", "Sin descripción")
            emoji = data.get("emoji")
            options.append(discord.SelectOption(
                label=label,
                description=description[:100],
                emoji=emoji,
                value=key
            ))

        placeholder = "Selecciona el tipo de solicitud"
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message(
                "❌ Solo miembros del servidor pueden usar esto.",
                ephemeral=True
            )

        ticket_type_key = self.values[0]
        ticket_type_data = config["ticket_types"].get(ticket_type_key)
        if not ticket_type_data:
            return await interaction.response.send_message(
                "❌ Este tipo de ticket ya no está disponible.",
                ephemeral=True
            )

        modal = TicketModal(ticket_type_key, ticket_type_data, interaction.user)
        await interaction.response.send_modal(modal)


class PanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        if config.get("ticket_types"):
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

    await interaction.response.send_message(f"✅ El bot ha salido de **{count}** servidores.", ephemeral=True)


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
# COMANDOS OWNER (TICKET TYPES)
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
    if "ticket_types" not in config:
        config["ticket_types"] = {}

    config["ticket_types"][tipo] = {
        "label": nombre,
        "description": descripcion,
        "emoji": emoji,
        "fields": ["motivo"]  # por defecto, luego lo puedes cambiar con /ticket_fields
    }
    save_config()
    await interaction.response.send_message(
        f"✅ Tipo de ticket añadido: `{tipo}` → **{nombre}**",
        ephemeral=True
    )


@bot.tree.command(name="ticket_remove", description="Elimina un tipo de ticket del select")
@owner_only()
@app_commands.describe(
    tipo="ID interno del tipo (ej: reporte, soporte)"
)
async def ticket_remove(interaction: discord.Interaction, tipo: str):
    tipo = tipo.lower().strip()
    if tipo not in config.get("ticket_types", {}):
        return await interaction.response.send_message(
            "❌ Ese tipo de ticket no existe.",
            ephemeral=True
        )

    del config["ticket_types"][tipo]
    save_config()
    await interaction.response.send_message(
        f"✅ Tipo de ticket eliminado: `{tipo}`",
        ephemeral=True
    )


@bot.tree.command(name="ticket_fields", description="Configura los campos del modal para un tipo de ticket")
@owner_only()
@app_commands.describe(
    tipo="ID interno del tipo (ej: reporte, soporte)",
    campos="Lista separada por comas. Ej: id_reportado, motivo, pruebas"
)
async def ticket_fields(interaction: discord.Interaction, tipo: str, campos: str):
    tipo = tipo.lower().strip()
    if tipo not in config.get("ticket_types", {}):
        return await interaction.response.send_message(
            "❌ Ese tipo de ticket no existe.",
            ephemeral=True
        )

    raw = [c.strip().lower() for c in campos.split(",") if c.strip()]
    if not raw:
        return await interaction.response.send_message(
            "❌ Debes indicar al menos un campo.",
            ephemeral=True
        )

    config["ticket_types"][tipo]["fields"] = raw
    save_config()
    await interaction.response.send_message(
        f"✅ Campos actualizados para `{tipo}`:\n`{', '.join(raw)}`",
        ephemeral=True
    )


# ==========================
# COMANDO OWNER PANEL
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
    if not config.get("ticket_types"):
        return await interaction.response.send_message(
            "❌ No hay tipos de ticket configurados. Usa `/ticket_add` primero.",
            ephemeral=True
        )

    await canal.send(embed=embed, view=view)
    await interaction.response.send_message(
        f"✅ Panel enviado a {canal.mention}",
        ephemeral=True
    )


# ==========================
# RUN
# ==========================

bot.run(TOKEN)
