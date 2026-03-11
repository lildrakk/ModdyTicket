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
#   SELECTS NUEVOS (ROLES, CATEGORÍA, LOGS, VALORACIONES)
# ============================================================

class SelectRolesStaff(discord.ui.Select):
    def __init__(self, cog, panel_id, roles):
        opciones = [
            discord.SelectOption(label=r.name, value=str(r.id))
            for r in roles if not r.is_default() and r.name
        ]

        if not opciones:
            opciones = [discord.SelectOption(label="No hay roles disponibles", value="0")]

        super().__init__(
            placeholder="Selecciona roles staff",
            min_values=1,
            max_values=min(25, len(opciones)),
            options=opciones,
            custom_id=f"select_roles_staff_{panel_id}"
        )

        self.cog = cog
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        if self.values[0] == "0":
            return await interaction.followup.send("❌ No hay roles válidos.", ephemeral=True)

        nuevos_roles = [int(v) for v in self.values]

        config = self.cog.get_config(interaction.guild.id, self.panel_id)
        config["staff_roles"] = nuevos_roles
        self.cog.save_config()

        await interaction.followup.send("✔ Roles staff actualizados.", ephemeral=True)

        self.values.clear()
        await interaction.message.edit(view=self.view)


class VistaRolesStaff(discord.ui.View):
    def __init__(self, cog, panel_id, roles):
        super().__init__(timeout=None)
        self.add_item(SelectRolesStaff(cog, panel_id, roles))


class SelectCategoria(discord.ui.Select):
    def __init__(self, cog, panel_id, categorias):
        opciones = [
            discord.SelectOption(label=c.name, value=str(c.id))
            for c in categorias if c.name
        ]

        if not opciones:
            opciones = [discord.SelectOption(label="No hay categorías", value="0")]

        super().__init__(
            placeholder="Selecciona una categoría",
            min_values=1,
            max_values=1,
            options=opciones,
            custom_id=f"select_categoria_{panel_id}"
        )

        self.cog = cog
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        if self.values[0] == "0":
            return await interaction.followup.send("❌ No hay categorías válidas.", ephemeral=True)

        categoria_id = int(self.values[0])

        config = self.cog.get_config(interaction.guild.id, self.panel_id)
        config["categoria_id"] = categoria_id
        self.cog.save_config()

        await interaction.followup.send("✔ Categoría actualizada.", ephemeral=True)

        self.values.clear()
        # ❌ ESTA ES LA LÍNEA QUE DEBES QUITAR
        # await interaction.message.edit(view=self.view)


class VistaCategoria(discord.ui.View):
    def __init__(self, cog, panel_id, categorias):
        super().__init__(timeout=None)
        self.add_item(SelectCategoria(cog, panel_id, categorias))


class SelectLogs(discord.ui.Select):
    def __init__(self, cog, panel_id, canales):
        opciones = [
            discord.SelectOption(label=c.name, value=str(c.id))
            for c in canales if c.name
        ]

        if not opciones:
            opciones = [discord.SelectOption(label="No hay canales", value="0")]

        super().__init__(
            placeholder="Selecciona canal de logs",
            min_values=1,
            max_values=1,
            options=opciones,
            custom_id=f"select_logs_{panel_id}"
        )

        self.cog = cog
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        if self.values[0] == "0":
            return await interaction.followup.send("❌ No hay canales válidos.", ephemeral=True)

        logs_id = int(self.values[0])

        config = self.cog.get_config(interaction.guild.id, self.panel_id)
        config["logs_id"] = logs_id
        self.cog.save_config()

        await interaction.followup.send("✔ Canal de logs actualizado.", ephemeral=True)

        self.values.clear()
        await interaction.message.edit(view=self.view)


class VistaLogs(discord.ui.View):
    def __init__(self, cog, panel_id, canales):
        super().__init__(timeout=None)
        self.add_item(SelectLogs(cog, panel_id, canales))


class SelectValoraciones(discord.ui.Select):
    def __init__(self, cog, panel_id: int, opciones):
        if not opciones:
            opciones = [discord.SelectOption(label="No hay canales", value="0")]

        super().__init__(
            placeholder="Selecciona canal de valoraciones",
            min_values=1,
            max_values=1,
            options=opciones,
            custom_id=f"select_valoraciones_{panel_id}"
        )

        self.cog = cog
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        if self.values[0] == "0":
            return await interaction.followup.send("❌ No hay canales válidos.", ephemeral=True)

        config = self.cog.get_config(interaction.guild.id, self.panel_id)
        config["valoraciones_id"] = int(self.values[0])
        self.cog.save_config()

        await interaction.followup.send("✔ Canal de valoraciones actualizado.", ephemeral=True)

        self.values.clear()
        await interaction.message.edit(view=self.view)



      
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
            title="🔔 Staff notificado 🔔",
            description=f"{creador.mention}\nEl staff ha sido notificado.",
            color=discord.Color.orange()
        )

        await interaction.channel.send(embed=embed)

        await interaction.followup.send("✔ Staff notificado correctamente.", ephemeral=True)


# ============================================================
#   BOTÓN CERRAR DEFINITIVO
# ============================================================

class BotonCerrarDefinitivo(discord.ui.Button):
    def __init__(self, disabled: bool = False):
        super().__init__(
            label="⚠️ Cerrar Definitivamente",
            style=discord.ButtonStyle.danger,
            custom_id="cerrar_definitivo_v1",
            disabled=disabled
        )

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        canal = interaction.channel
        canal_id = str(canal.id)
        usuario = interaction.user
        guild = interaction.guild

        tickets = load_json(TICKETS_PATH)
        ticket_data = tickets.get(canal_id)

        if not ticket_data:
            return await interaction.followup.send("❌ No se encontró información del ticket.", ephemeral=True)

        logs_cog = interaction.client.get_cog("Logs")
        if logs_cog:
            await logs_cog.enviar_log(
                guild=guild,
                canal_ticket=canal,
                ticket_data=ticket_data,
                razon_cierre="Cierre definitivo",
                cerrado_por=usuario
            )

        del tickets[canal_id]
        save_json(TICKETS_PATH, tickets)

        await interaction.followup.send("✔ Ticket cerrado definitivamente.", ephemeral=True)

        await canal.delete(reason=f"Ticket cerrado por {usuario}")


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
#   VISTA FINAL DE CIERRE DEFINITIVO
# ============================================================

class VistaCierreFinal(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BotonCerrarDefinitivo())


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

        view = discord.ui.View(timeout=None)
        view.add_item(MenuValoracion(self.cog, self.canal_id))
        view.add_item(BotonCerrarDefinitivo(disabled=False))

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

        for r in ratings[self.canal_id]:
            if (
                r["usuario_id"] == interaction.user.id
                and r["rating"] == self.rating
                and r["comentario"] is None
            ):
                r["comentario"] = self.comentario.value
                break

        save_json(RATINGS_PATH, ratings)

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

        await interaction.response.send_message(
            "⭐ ¡Gracias por tu valoración!",
            ephemeral=True
      )



# ============================================================
#   BOTONES DE CONFIGURACIÓN
# ============================================================

class BotonConfigRoles(discord.ui.Button):
    def __init__(self, cog, panel_id):
        super().__init__(label="👥 Roles Staff", style=discord.ButtonStyle.primary)
        self.cog = cog
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):

        roles = [
            r for r in interaction.guild.roles
            if not r.is_default() and r.name
        ]

        if not roles:
            return await interaction.response.send_message(
                "❌ No hay roles válidos en este servidor.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Selecciona los roles staff:",
            view=VistaRolesStaff(self.cog, self.panel_id, roles),
            ephemeral=True
        )


class BotonConfigCategoria(discord.ui.Button):
    def __init__(self, cog, panel_id):
        super().__init__(label="📂 Categoría", style=discord.ButtonStyle.primary)
        self.cog = cog
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):

        categorias = [c for c in interaction.guild.categories if c.name]

        if not categorias:
            return await interaction.response.send_message(
                "❌ No hay categorías disponibles.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Selecciona la categoría donde se crearán los tickets:",
            view=VistaCategoria(self.cog, self.panel_id, categorias),
            ephemeral=True
        )


class BotonConfigLogs(discord.ui.Button):
    def __init__(self, cog, panel_id):
        super().__init__(label="📘 Canal Logs", style=discord.ButtonStyle.primary)
        self.cog = cog
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):

        canales = [
            c for c in interaction.guild.text_channels
            if c.name
        ]

        if not canales:
            return await interaction.response.send_message(
                "❌ No hay canales de texto disponibles.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Selecciona el canal de logs:",
            view=VistaLogs(self.cog, self.panel_id, canales),
            ephemeral=True
        )


class BotonConfigValoraciones(discord.ui.Button):
    def __init__(self, cog, panel_id):
        super().__init__(label="⭐ Canal Valoraciones", style=discord.ButtonStyle.primary)
        self.cog = cog
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):

        opciones = [
            discord.SelectOption(label=c.name, value=str(c.id))
            for c in interaction.guild.text_channels
            if c.name
        ]

        if not opciones:
            return await interaction.response.send_message(
                "❌ No hay canales válidos para valoraciones.",
                ephemeral=True
            )

        view = discord.ui.View(timeout=None)
        view.add_item(SelectValoraciones(self.cog, self.panel_id, opciones))

        await interaction.response.send_message(
            "Selecciona el canal donde se enviarán las valoraciones:",
            view=view,
            ephemeral=True
        )


class BotonConfigRazon(discord.ui.Button):
    def __init__(self, cog, panel_id):
        super().__init__(label="📝 Razón Obligatoria", style=discord.ButtonStyle.secondary)
        self.cog = cog
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):

        config = self.cog.get_config(interaction.guild.id, self.panel_id)

        actual = config["razon_obligatoria"]
        config["razon_obligatoria"] = not actual
        self.cog.save_config()

        estado = "activada" if not actual else "desactivada"

        await interaction.response.send_message(
            f"✔ Razón obligatoria {estado}.",
            ephemeral=True
        )


# ============================================================
#   BOTÓN ACTIVAR / DESACTIVAR NOTIFICAR STAFF
# ============================================================

class BotonToggleNotificar(discord.ui.Button):
    def __init__(self, cog, panel_id, guild_id):
        super().__init__(
            label="🔔 Activar/Desactivar Notificar",
            style=discord.ButtonStyle.primary
        )
        self.cog = cog
        self.panel_id = panel_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):

        config = self.cog.get_config(self.guild_id, self.panel_id)

        config["notificar_habilitado"] = not config.get("notificar_habilitado", True)
        self.cog.save_config()

        nuevo_embed = generar_embed_config(interaction.guild, config)
        nueva_vista = VistaConfig(self.cog, self.panel_id, self.guild_id)

        await interaction.response.edit_message(embed=nuevo_embed, view=nueva_vista)


# ============================================================
#   BOTÓN CAMBIAR COOLDOWN
# ============================================================

class BotonCambiarCooldown(discord.ui.Button):
    def __init__(self, cog, panel_id, guild_id):
        super().__init__(
            label="⏱ Cambiar Cooldown",
            style=discord.ButtonStyle.secondary
        )
        self.cog = cog
        self.panel_id = panel_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            CooldownModal(self.cog, self.panel_id, self.guild_id)
        )


# ============================================================
#   MODAL PARA CAMBIAR COOLDOWN
# ============================================================

class CooldownModal(discord.ui.Modal, title="Cambiar Cooldown"):

    cooldown = discord.ui.TextInput(
        label="Nuevo cooldown (minutos)",
        placeholder="Ej: 5",
        required=True
    )

    def __init__(self, cog, panel_id, guild_id):
        super().__init__()
        self.cog = cog
        self.panel_id = panel_id
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):

        try:
            nuevo_cooldown = int(self.cooldown.value)
        except:
            return await interaction.response.send_message(
                "❌ Debes poner un número.",
                ephemeral=True
            )

        config = self.cog.get_config(self.guild_id, self.panel_id)
        config["notificar_cooldown"] = nuevo_cooldown
        self.cog.save_config()

        await interaction.response.send_message(
            f"✔ Cooldown actualizado a {nuevo_cooldown} minutos.",
            ephemeral=True
        )


# ============================================================
#   VISTA CONFIG (PERSISTENTE)
# ============================================================

class VistaConfig(discord.ui.View):
    def __init__(self, cog, panel_id, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.panel_id = panel_id
        self.guild_id = guild_id

        self.add_item(BotonConfigRoles(cog, panel_id))
        self.add_item(BotonConfigCategoria(cog, panel_id))
        self.add_item(BotonConfigLogs(cog, panel_id))
        self.add_item(BotonConfigValoraciones(cog, panel_id))
        self.add_item(BotonConfigRazon(cog, panel_id))

        self.add_item(BotonToggleNotificar(cog, panel_id, guild_id))
        self.add_item(BotonCambiarCooldown(cog, panel_id, guild_id))


# ============================================================
#   GENERADOR DE EMBED DE CONFIG
# ============================================================

def generar_embed_config(guild, config):

    estado_notificar = "Activado" if config.get("notificar_habilitado", True) else "Desactivado"
    cooldown = config.get("notificar_cooldown", 5)

    embed = discord.Embed(
        title="⚙️ Configuración del Panel de Tickets",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="Roles staff",
        value=", ".join([f"<@&{r}>" for r in config['staff_roles']]) or "—",
        inline=False
    )
    embed.add_field(
        name="Categoría",
        value=f"<#{config['categoria_id']}>" if config["categoria_id"] else "—",
        inline=False
    )
    embed.add_field(
        name="Canal de logs",
        value=f"<#{config['logs_id']}>" if config["logs_id"] else "—",
        inline=False
    )
    embed.add_field(
        name="Canal de valoraciones",
        value=f"<#{config['valoraciones_id']}>" if config["valoraciones_id"] else "—",
        inline=False
    )
    embed.add_field(
        name="Razón obligatoria",
        value="Sí" if config["razon_obligatoria"] else "No",
        inline=False
    )
    embed.add_field(
        name="Notificar staff",
        value=estado_notificar,
        inline=False
    )
    embed.add_field(
        name="Cooldown de notificación",
        value=f"{cooldown} minutos",
        inline=False
    )

    return embed



# ============================================================
#   COMANDO /ticket_config
# ============================================================

@app_commands.command(name="ticket_config", description="Configura un panel de tickets.")
@app_commands.describe(panel_id="ID del panel que quieres configurar")
async def ticket_config(interaction: discord.Interaction, panel_id: int):

    cog: "Tickets" = interaction.client.get_cog("Tickets")
    if not cog:
        return await interaction.response.send_message(
            "❌ El sistema de tickets no está cargado.",
            ephemeral=True
        )

    await interaction.response.send_message("Cargando configuración...", ephemeral=True)

    config = cog.get_config(interaction.guild.id, panel_id)

    embed = generar_embed_config(interaction.guild, config)
    view = VistaConfig(cog, panel_id, interaction.guild.id)

    await interaction.edit_original_response(
        content=None,
        embed=embed,
        view=view
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

    # ------------------------------
    #   CREAR TICKET (CORREGIDO)
    # ------------------------------

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
        menciones = " ".join(r.mention for r in roles_staff) if roles_staff else ""

        embed = discord.Embed(
            title="🎫 Nuevo ticket abierto",
            description=(
                f"👤 **Usuario:** {user.mention}\n"
                f"📌 **Tipo:** {emoji or ''} {label or 'Ticket'}\n"
                f"🔔 **Staff notificado:** {menciones or '—'}"
            ),
            color=discord.Color.green()
        )

        view = VistaTicket(config)
        await canal.send(embed=embed, view=view)

        await interaction.followup.send(
            f"✔️ {canal.mention} creado correctamente",
            ephemeral=True
        )

    # ------------------------------
    #   CIERRE DEFINITIVO
    # ------------------------------

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

    # ------------------------------
    #   TRACKING DE MENSAJES
    # ------------------------------

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
