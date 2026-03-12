import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime

# ============================================================
#   RUTAS JSON
# ============================================================

CONFIG_PATH = "data/tickets_config.json"
TICKETS_PATH = "data/tickets_data.json"
RATINGS_PATH = "data/tickets_ratings.json"

os.makedirs("data", exist_ok=True)

# ============================================================
#   UTILIDADES JSON
# ============================================================

def load_json(path):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump({}, f)
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


# ============================================================
#   NUEVO COMANDO /ticket_config (CORREGIDO)
# ============================================================

@app_commands.command(name="ticket_config", description="Configura un panel de tickets.")
@app_commands.describe(
    panel_id="ID del panel que quieres configurar",
    roles_staff="Rol del staff (ejecuta varias veces para añadir más)",
    categoria="Categoría donde se crearán los tickets",
    logs="Canal donde se enviarán los logs",
    valoraciones="Canal donde se enviarán las valoraciones",
    razon_obligatoria="¿El usuario debe escribir una razón obligatoria?",
    notificar_staff="¿Activar o desactivar el botón de notificar staff?",
    cooldown="Cooldown en minutos para notificar staff"
)
async def ticket_config(
    interaction: discord.Interaction,
    panel_id: int,
    roles_staff: discord.Role | None = None,
    categoria: discord.CategoryChannel | None = None,
    logs: discord.TextChannel | None = None,
    valoraciones: discord.TextChannel | None = None,
    razon_obligatoria: bool | None = None,
    notificar_staff: bool | None = None,
    cooldown: int | None = None
):

    cog: "Tickets" = interaction.client.get_cog("Tickets")
    if not cog:
        return await interaction.response.send_message(
            "❌ El sistema de tickets no está cargado.",
            ephemeral=True
        )

    config = cog.get_config(interaction.guild.id, panel_id)

    # ------------------------------
    #   GUARDAR CAMPOS
    # ------------------------------

    # Añadir rol staff (uno por comando)
    if roles_staff is not None:
        if roles_staff.id not in config["staff_roles"]:
            config["staff_roles"].append(roles_staff.id)

    if categoria is not None:
        config["categoria_id"] = categoria.id

    if logs is not None:
        config["logs_id"] = logs.id

    if valoraciones is not None:
        config["valoraciones_id"] = valoraciones.id

    if razon_obligatoria is not None:
        config["razon_obligatoria"] = razon_obligatoria

    if notificar_staff is not None:
        config["notificar_habilitado"] = notificar_staff

    if cooldown is not None:
        config["notificar_cooldown"] = cooldown

    cog.save_config()

    await interaction.response.send_message(
        f"✔ Configuración del panel **{panel_id}** actualizada correctamente.",
        ephemeral=True
        ) 



# ============================================================
#   BOTONES DEL TICKET (PERSISTENTES)
# ============================================================

class BotonCerrarTicket(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="🔒 Cerrar Ticket",
            style=discord.ButtonStyle.danger,
            custom_id="cerrar_ticket_v3"
        )

    async def callback(self, interaction: discord.Interaction):
        canal_id = str(interaction.channel.id)
        tickets = load_json(TICKETS_PATH)

        if canal_id not in tickets:
            return await interaction.response.send_message(
                "❌ No se encontró información del ticket.",
                ephemeral=True
            )

        cog = interaction.client.get_cog("Tickets")
        if not cog:
            return await interaction.response.send_message(
                "❌ El sistema de tickets no está disponible.",
                ephemeral=True
            )

        view = SelectorStaff(cog, canal_id)

        await interaction.response.send_message(
            "⭐ **Antes de cerrar el ticket, selecciona quién te atendió.**",
            view=view,
            ephemeral=True
        )


class BotonReclamar(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="📌 Reclamar",
            style=discord.ButtonStyle.success,
            custom_id="reclamar_ticket"
        )

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        canal_id = str(interaction.channel.id)
        tickets = load_json(TICKETS_PATH)
        ticket = tickets.get(canal_id)

        if not ticket:
            return await interaction.followup.send("❌ Este canal no es un ticket.", ephemeral=True)

        if ticket.get("reclamado", False):
            return await interaction.followup.send("❌ Este ticket ya ha sido reclamado.", ephemeral=True)

        ticket["reclamado"] = True
        ticket["reclamado_por"] = interaction.user.id
        save_json(TICKETS_PATH, tickets)

        creador = interaction.guild.get_member(ticket["usuario_id"])
        if creador:
            await interaction.channel.send(creador.mention)

        embed = discord.Embed(
            title="📌 Ticket Reclamado",
            description=f"Ticket reclamado por {interaction.user.mention}",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=embed)

        self.disabled = True
        self.style = discord.ButtonStyle.gray
        self.label = "📌 Ticket reclamado"
        await interaction.message.edit(view=self.view)

        await interaction.followup.send("✔ Ticket reclamado correctamente.", ephemeral=True)


class BotonNotificar(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="🔔 Notificar Staff",
            style=discord.ButtonStyle.primary,
            custom_id="notificar_staff"
        )

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        canal_id = str(interaction.channel.id)
        tickets = load_json(TICKETS_PATH)
        ticket = tickets.get(canal_id)

        if not ticket:
            return await interaction.followup.send("❌ Este canal no es un ticket.", ephemeral=True)

        cog = interaction.client.get_cog("Tickets")
        if not cog:
            return await interaction.followup.send("❌ El sistema de tickets no está disponible.", ephemeral=True)

        config = cog.get_config(interaction.guild.id, ticket["panel_id"])

        cooldown_min = config.get("notificar_cooldown", 5)
        cooldown_seg = cooldown_min * 60

        ahora = int(datetime.datetime.utcnow().timestamp())
        ultimo = ticket.get("last_notify", 0)

        if ahora - ultimo < cooldown_seg:
            restante = cooldown_seg - (ahora - ultimo)
            minutos = restante // 60
            segundos = restante % 60

            return await interaction.followup.send(
                f"⏳ Debes esperar **{minutos}m {segundos}s** para volver a notificar al staff.",
                ephemeral=True
            )

        ticket["last_notify"] = ahora
        save_json(TICKETS_PATH, tickets)

        creador = interaction.guild.get_member(ticket["usuario_id"])

        roles_staff = [
            interaction.guild.get_role(r)
            for r in config["staff_roles"]
            if interaction.guild.get_role(r)
        ]

        menciones_staff = " ".join(r.mention for r in roles_staff) if roles_staff else "—"

        await interaction.channel.send(f"{creador.mention} {menciones_staff}")

        embed = discord.Embed(
            title="🔔 Staff notificado",
            description=f"{creador.mention}\nEl staff ha sido notificado.",
            color=discord.Color.orange()
        )

        await interaction.channel.send(embed=embed)

        await interaction.followup.send("✔ Staff notificado correctamente.", ephemeral=True)


# ============================================================
#   VISTA TICKET (PERSISTENTE)
# ============================================================

class VistaTicket(discord.ui.View):
    def __init__(self, config):
        super().__init__(timeout=None)

        self.add_item(BotonReclamar())
        self.add_item(BotonCerrarTicket())

        if config.get("notificar_habilitado", True):
            self.add_item(BotonNotificar())


# ============================================================
#   SELECTOR “¿QUIÉN TE ATENDIÓ?”
# ============================================================

class SelectorStaff(discord.ui.View):
    def __init__(self, cog: "Tickets", canal_id: str):
        super().__init__(timeout=None)
        self.add_item(SelectStaff(cog, canal_id))


class SelectStaff(discord.ui.Select):
    def __init__(self, cog: "Tickets", canal_id: str):
        self.cog = cog
        self.canal_id = canal_id

        tickets = load_json(TICKETS_PATH)
        ticket = tickets.get(canal_id)

        guild = cog.bot.get_guild(ticket["guild_id"])
        config = cog.get_config(ticket["guild_id"], ticket["panel_id"])

        participantes = ticket.get("participantes", [])

        opciones = []

        for rol_id in config["staff_roles"]:
            rol = guild.get_role(rol_id)
            if not rol:
                continue

            for miembro in rol.members:
                if miembro.id in participantes:
                    opciones.append(
                        discord.SelectOption(
                            label=miembro.name,
                            value=str(miembro.id)
                        )
                    )

        if not opciones:
            opciones = [discord.SelectOption(label="No hay staff que haya participado", value="0")]

        super().__init__(
            placeholder="Selecciona quién te atendió",
            options=opciones,
            custom_id=f"select_staff_{canal_id}"
        )

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        if self.values[0] == "0":
            return await interaction.followup.send(
                "❌ Ningún miembro de staff participó en este ticket.",
                ephemeral=True
            )

        tickets = load_json(TICKETS_PATH)
        tickets[self.canal_id]["reclamado_por"] = int(self.values[0])
        save_json(TICKETS_PATH, tickets)

        await interaction.followup.send("✔ Staff registrado.", ephemeral=True)

        # ------------------------------
        #   FIX IMPORTANTE
        # ------------------------------
        # El botón NO acepta parámetros → ahora se añade correctamente
        boton = BotonCerrarDefinitivo()
        boton.disabled = False

        view = discord.ui.View(timeout=None)
        view.add_item(MenuValoracion(self.cog, self.canal_id))
        view.add_item(boton)

        await interaction.channel.send(
            "⭐ Selecciona la valoración:",
            view=view
        )


# ============================================================
#   VALORACIÓN (1–5 ESTRELLAS + COMENTARIO)
# ============================================================

class MenuValoracion(discord.ui.Select):
    def __init__(self, cog: "Tickets", canal_id: str):
        opciones = [
            discord.SelectOption(label="⭐ 1", value="1"),
            discord.SelectOption(label="⭐⭐ 2", value="2"),
            discord.SelectOption(label="⭐⭐⭐ 3", value="3"),
            discord.SelectOption(label="⭐⭐⭐⭐ 4", value="4"),
            discord.SelectOption(label="⭐⭐⭐⭐⭐ 5", value="5"),
        ]
        super().__init__(
            placeholder="Valora la atención recibida",
            options=opciones,
            custom_id=f"menu_valoracion_{canal_id}"
        )
        self.cog = cog
        self.canal_id = canal_id

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        rating = int(self.values[0])

        ratings = load_json(RATINGS_PATH)
        if self.canal_id not in ratings:
            ratings[self.canal_id] = []

        ratings[self.canal_id].append({
            "usuario_id": interaction.user.id,
            "rating": rating,
            "comentario": None,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })

        save_json(RATINGS_PATH, ratings)

        modal = ModalComentarioValoracion(self.cog, self.canal_id, rating)
        await interaction.followup.send_modal(modal)


# ============================================================
#   MODAL PARA RAZÓN DE CIERRE
# ============================================================

class ModalRazonCierre(discord.ui.Modal, title="Razón del cierre"):
    razon = discord.ui.TextInput(
        label="Escribe la razón del cierre",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=300
    )

    def __init__(self, cog, interaction):
        super().__init__()
        self.cog = cog
        self.interaction = interaction

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.cerrar_definitivo(self.interaction, self.razon.value)
        await interaction.response.send_message("✔ Ticket cerrado correctamente.", ephemeral=True)


# ============================================================
#   BOTÓN CIERRE DEFINITIVO (ABRE MODAL)
# ============================================================

class BotonCerrarDefinitivo(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="⚠️ Cerrar Definitivamente",
            style=discord.ButtonStyle.danger,
            custom_id="cerrar_definitivo_v1"
        )

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Tickets")
        modal = ModalRazonCierre(cog, interaction)
        await interaction.response.send_modal(modal)


# ============================================================
#   VISTA FINAL DE CIERRE DEFINITIVO (PERSISTENTE)
# ============================================================

class VistaCierreFinal(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BotonCerrarDefinitivo())


class ModalComentarioValoracion(discord.ui.Modal, title="Comentario opcional"):
    comentario = discord.ui.TextInput(
        label="Comentario (opcional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=300
    )

    def __init__(self, cog: "Tickets", canal_id: str, rating: int):
        super().__init__()
        self.cog = cog
        self.canal_id = canal_id
        self.rating = rating

    async def on_submit(self, interaction: discord.Interaction):

        ratings = load_json(RATINGS_PATH)

        if self.canal_id not in ratings:
            ratings[self.canal_id] = []

        # Guardar comentario en la última valoración sin comentario
        for r in ratings[self.canal_id]:
            if (
                r["usuario_id"] == interaction.user.id
                and r["rating"] == self.rating
                and r["comentario"] is None
            ):
                r["comentario"] = self.comentario.value
                break

        save_json(RATINGS_PATH, ratings)

        # Enviar valoración al canal configurado
        tickets = load_json(TICKETS_PATH)
        ticket = tickets.get(self.canal_id)

        if ticket:
            config = self.cog.get_config(interaction.guild.id, ticket["panel_id"])

            if config["valoraciones_id"]:
                canal_val = interaction.guild.get_channel(config["valoraciones_id"])
                if canal_val:
                    embed = discord.Embed(
                        title="⭐ Nueva valoración recibida",
                        color=discord.Color.gold()
                    )
                    embed.add_field(name="Usuario", value=f"<@{interaction.user.id}>")
                    embed.add_field(name="Ticket", value=f"<#{self.canal_id}>")
                    embed.add_field(name="Valoración", value=f"{'⭐' * self.rating}")

                    staff_id = ticket.get("reclamado_por")
                    if staff_id:
                        embed.add_field(name="Staff que atendió", value=f"<@{staff_id}>")

                    embed.add_field(
                        name="Comentario",
                        value=self.comentario.value or "Sin comentario"
                    )
                    embed.timestamp = datetime.datetime.utcnow()

                    await canal_val.send(embed=embed)

        # ------------------------------
        #   MENSAJE FINAL AL USUARIO
        # ------------------------------
        await interaction.response.send_message(
            "⭐ ¡Gracias por tu valoración!",
            ephemeral=True
        )



# ============================================================
#   CLASE PRINCIPAL TICKETS
# ============================================================

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_json(CONFIG_PATH)

    # ------------------------------
    #   CONFIG
    # ------------------------------

    def get_config(self, guild_id: int, panel_id: int):
        guild_id = str(guild_id)
        panel_id = str(panel_id)

        if guild_id not in self.config:
            self.config[guild_id] = {}

        if panel_id not in self.config[guild_id]:
            self.config[guild_id][panel_id] = {
                "staff_roles": [],
                "categoria_id": None,
                "logs_id": None,
                "valoraciones_id": None,
                "razon_obligatoria": False,
                "notificar_habilitado": True,
                "notificar_cooldown": 5
            }

        return self.config[guild_id][panel_id]

    def save_config(self):
        save_json(CONFIG_PATH, self.config)

    # ============================================================
    #   CREAR TICKET
    # ============================================================

    async def crear_ticket(self, interaction: discord.Interaction, panel_id=None, label=None, emoji=None):

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user

        config = self.get_config(guild.id, panel_id)
        categoria = guild.get_channel(config["categoria_id"]) if config["categoria_id"] else None

        nombre_canal = f"ticket-{user.name}".replace(" ", "-")[:90]

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }

        for rol_id in config["staff_roles"]:
            rol = guild.get_role(rol_id)
            if rol:
                overwrites[rol] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        canal = await guild.create_text_channel(
            nombre_canal,
            category=categoria,
            overwrites=overwrites
        )

        tickets = load_json(TICKETS_PATH)
        tickets[str(canal.id)] = {
            "guild_id": guild.id,
            "usuario_id": user.id,
            "panel_id": panel_id,
            "reclamado_por": None,
            "reclamado": False,
            "last_notify": 0,
            "participantes": [user.id],
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        save_json(TICKETS_PATH, tickets)

        roles_staff = [guild.get_role(r) for r in config["staff_roles"] if guild.get_role(r)]
        menciones_staff = " ".join(r.mention for r in roles_staff) if roles_staff else "—"

        await canal.send(f"{user.mention} {menciones_staff}")

        embed = discord.Embed(
            title="🎫 Nuevo ticket abierto",
            description=(
                f"👤 Usuario: {user.mention}\n"
                f"🔔 Staff: {menciones_staff}\n"
                f"📌 Tipo: {emoji or ''} {label or 'Ticket'}"
            ),
            color=discord.Color.green()
        )

        view = VistaTicket(config)
        await canal.send(embed=embed, view=view)

        await interaction.followup.send(
            f"✔️ {canal.mention} creado correctamente",
            ephemeral=True
        )

    # ============================================================
    #   CIERRE DEFINITIVO (RECIBE LA RAZÓN DEL MODAL)
    # ============================================================

    async def cerrar_definitivo(self, interaction: discord.Interaction, razon: str):

        canal = interaction.channel
        canal_id = str(canal.id)
        usuario = interaction.user
        guild = interaction.guild

        tickets = load_json(TICKETS_PATH)
        ticket_data = tickets.get(canal_id)

        if not ticket_data:
            return await interaction.followup.send("❌ No se encontró información del ticket.", ephemeral=True)

        logs_cog = self.bot.get_cog("Logs")
        if logs_cog:
            await logs_cog.enviar_log(
                guild=guild,
                canal_ticket=canal,
                ticket_data=ticket_data,
                razon_cierre=razon,
                cerrado_por=usuario
            )

        del tickets[canal_id]
        save_json(TICKETS_PATH, tickets)

        await canal.delete(reason=f"Ticket cerrado por {usuario} — {razon}")

    # ============================================================
    #   TRACKING DE MENSAJES
    # ============================================================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        canal_id = str(message.channel.id)
        tickets = load_json(TICKETS_PATH)

        if canal_id not in tickets:
            return

        ticket = tickets[canal_id]

        if message.author.id not in ticket["participantes"]:
            ticket["participantes"].append(message.author.id)
            save_json(TICKETS_PATH, tickets)


# ============================================================
#   SETUP FINAL DEL COG
# ============================================================

async def setup(bot: commands.Bot):
    cog = Tickets(bot)
    await bot.add_cog(cog)

    bot.tree.add_command(ticket_config)

    bot.add_view(VistaCierreFinal())

    print("[Tickets] Sistema de tickets cargado correctamente.")
