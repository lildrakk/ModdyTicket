import discord
from discord.ext import commands
from discord import app_commands
import json
import os

PANELS_PATH = "data/panels.json"

# ============================================================
#   UTILIDADES JSON
# ============================================================

def cargar_paneles():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(PANELS_PATH):
        with open(PANELS_PATH, "w") as f:
            json.dump({}, f)
    with open(PANELS_PATH, "r") as f:
        return json.load(f)

def guardar_paneles(data):
    with open(PANELS_PATH, "w") as f:
        json.dump(data, f, indent=4)

# ============================================================
#   VALIDADORES
# ============================================================

def validar_color(color_str):
    if not color_str:
        return discord.Color.blue()

    if not isinstance(color_str, str):
        return discord.Color.blue()

    color_str = color_str.replace("#", "")

    if len(color_str) not in (3, 6):
        return discord.Color.blue()

    try:
        return discord.Color(int(color_str, 16))
    except:
        return discord.Color.blue()

def validar_emoji(emoji):
    if not emoji:
        return None
    try:
        return str(emoji)
    except:
        return None

# ============================================================
#   BOTONES PERSISTENTES
# ============================================================

class BotonPanel(discord.ui.Button):
    def __init__(self, panel_id, label, emoji, value):
        super().__init__(
            label=label,
            emoji=validar_emoji(emoji),
            style=discord.ButtonStyle.primary,
            custom_id=f"panel_btn_{panel_id}_{value}"
        )
        self.panel_id = panel_id
        self.label_text = label
        self.emoji_text = emoji
        self.value = value

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Tickets")
        if not cog:
            return await interaction.response.send_message("❌ Sistema de tickets no cargado.", ephemeral=True)

        await cog.crear_ticket(
            interaction,
            panel_id=self.panel_id,
            label=self.label_text,
            emoji=self.emoji_text
        )

# ============================================================
#   MENÚ SELECT (PERSISTENTE)
# ============================================================

class SelectPanel(discord.ui.Select):
    def __init__(self, panel_id, opciones_menu):
        self.panel_id = panel_id

        opciones = [
            discord.SelectOption(
                label=o["label"],
                description=o.get("descripcion", "Abrir ticket"),
                emoji=o.get("emoji"),
                value=o["value"]
            )
            for o in opciones_menu
        ]

        super().__init__(
            placeholder="Selecciona una opción...",
            min_values=1,
            max_values=1,
            options=opciones,
            custom_id=f"panel_menu_{panel_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        opcion = next(o for o in self.options if o.value == self.values[0])

        cog = interaction.client.get_cog("Tickets")
        if not cog:
            return await interaction.response.send_message("❌ Sistema de tickets no cargado.", ephemeral=True)

        await cog.crear_ticket(
            interaction,
            panel_id=self.panel_id,
            label=opcion.label,
            emoji=opcion.emoji
        )

class VistaPanelMenu(discord.ui.View):
    def __init__(self, panel_id, opciones_menu):
        super().__init__(timeout=None)
        self.add_item(SelectPanel(panel_id, opciones_menu))

# ============================================================
#   VISTA BOTONES
# ============================================================

class VistaPanel(discord.ui.View):
    def __init__(self, panel_id, panel_data):
        super().__init__(timeout=None)
        for b in panel_data.get("botones", []):
            self.add_item(BotonPanel(
                panel_id=panel_id,
                label=b["label"],
                emoji=b.get("emoji"),
                value=b.get("value") or b["label"]
            ))



# ============================================================
#   COG PRINCIPAL
# ============================================================

class Panels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def obtener_panel(self, guild_id, panel_id):
        data = cargar_paneles()
        guild = str(guild_id)
        pid = str(panel_id)
        return data.get(guild, {}).get(pid)

    # ============================================================
    #   CREAR PANEL
    # ============================================================

    @app_commands.command(name="panel_crear", description="Crea un panel vacío.")
    async def panel_crear(self, interaction: discord.Interaction, panel_id: int):
        data = cargar_paneles()
        guild = str(interaction.guild.id)
        pid = str(panel_id)

        if guild not in data:
            data[guild] = {}

        if pid in data[guild]:
            return await interaction.response.send_message("❌ Ese panel ya existe.", ephemeral=True)

        data[guild][pid] = {
            "titulo": "🎫 Panel de Tickets",
            "descripcion": "Pulsa un botón para abrir un ticket.",
            "color": "#5865F2",
            "botones": [],
            "menu": []
        }

        guardar_paneles(data)
        await interaction.response.send_message("✔ Panel creado.", ephemeral=True)

    # ============================================================
    #   EDITAR PANEL
    # ============================================================

    @app_commands.command(name="panel_editar", description="Edita el embed del panel.")
    async def panel_editar(self, interaction: discord.Interaction, panel_id: int, titulo: str = None, descripcion: str = None, color: str = None):
        data = cargar_paneles()
        guild = str(interaction.guild.id)
        pid = str(panel_id)

        if guild not in data or pid not in data[guild]:
            return await interaction.response.send_message("❌ Ese panel no existe.", ephemeral=True)

        if titulo:
            data[guild][pid]["titulo"] = titulo
        if descripcion:
            data[guild][pid]["descripcion"] = descripcion
        if color:
            data[guild][pid]["color"] = color

        guardar_paneles(data)
        await interaction.response.send_message("✔ Panel actualizado.", ephemeral=True)

    # ============================================================
    #   AÑADIR BOTÓN
    # ============================================================

    @app_commands.command(name="panel_boton", description="Añade un botón al panel.")
    async def panel_boton(self, interaction: discord.Interaction, panel_id: int, etiqueta: str, emoji: str = None, valor: str = None):
        data = cargar_paneles()
        guild = str(interaction.guild.id)
        pid = str(panel_id)

        if guild not in data or pid not in data[guild]:
            return await interaction.response.send_message("❌ Ese panel no existe.", ephemeral=True)

        data[guild][pid]["botones"].append({
            "label": etiqueta,
            "emoji": validar_emoji(emoji),
            "value": valor or etiqueta
        })

        guardar_paneles(data)
        await interaction.response.send_message("✔ Botón añadido.", ephemeral=True)

    # ============================================================
    #   AÑADIR OPCIÓN AL MENÚ
    # ============================================================

    @app_commands.command(name="panel_menu", description="Añade una opción al menú del panel.")
    async def panel_menu(self, interaction: discord.Interaction, panel_id: int, etiqueta: str, descripcion: str, emoji: str = None, valor: str = None):
        data = cargar_paneles()
        guild = str(interaction.guild.id)
        pid = str(panel_id)

        if guild not in data or pid not in data[guild]:
            return await interaction.response.send_message("❌ Ese panel no existe.", ephemeral=True)

        data[guild][pid]["menu"].append({
            "label": etiqueta,
            "descripcion": descripcion,
            "emoji": validar_emoji(emoji),
            "value": valor or etiqueta
        })

        guardar_paneles(data)
        await interaction.response.send_message("✔ Opción añadida al menú.", ephemeral=True)

    # ============================================================
    #   ENVIAR PANEL CON MENÚ
    # ============================================================

    @app_commands.command(name="panel_menu_enviar", description="Envía un panel con menú select.")
    async def panel_menu_enviar(self, interaction: discord.Interaction, panel_id: int):
        panel = self.obtener_panel(interaction.guild.id, panel_id)

        if not panel:
            return await interaction.response.send_message("❌ Panel no encontrado.", ephemeral=True)

        if not panel["menu"]:
            return await interaction.response.send_message("❌ Este panel no tiene opciones de menú.", ephemeral=True)

        embed = discord.Embed(
            title=panel["titulo"],
            description=panel["descripcion"],
            color=validar_color(panel["color"])
        )

        view = VistaPanelMenu(panel_id, panel["menu"])

        await interaction.response.send_message("✔ Panel con menú enviado.", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)

    # ============================================================
    #   LISTAR PANELES
    # ============================================================

    @app_commands.command(name="panel_listar", description="Lista los paneles.")
    async def panel_listar(self, interaction: discord.Interaction):
        data = cargar_paneles()
        guild = str(interaction.guild.id)

        if guild not in data or not data[guild]:
            return await interaction.response.send_message("📭 No hay paneles.", ephemeral=True)

        lista = "\n".join([f"• Panel **{pid}**" for pid in data[guild]])
        await interaction.response.send_message(f"📋 Paneles:\n{lista}", ephemeral=True)

    # ============================================================
    #   BORRAR PANEL
    # ============================================================

    @app_commands.command(name="panel_borrar", description="Elimina un panel existente.")
    async def panel_borrar(self, interaction: discord.Interaction, panel_id: int):
        data = cargar_paneles()
        guild = str(interaction.guild.id)
        pid = str(panel_id)

        if guild not in data or pid not in data[guild]:
            return await interaction.response.send_message("❌ Ese panel no existe.", ephemeral=True)

        del data[guild][pid]

        if not data[guild]:
            del data[guild]

        guardar_paneles(data)
        await interaction.response.send_message(f"🗑️ Panel **{panel_id}** eliminado.", ephemeral=True)

    # ============================================================
    #   ENVIAR PANEL CON BOTONES
    # ============================================================

    @app_commands.command(name="panel_enviar", description="Envía un panel con botones.")
    async def panel_enviar(self, interaction: discord.Interaction, panel_id: int):
        panel = self.obtener_panel(interaction.guild.id, panel_id)
        if not panel:
            return await interaction.response.send_message("❌ Ese panel no existe.", ephemeral=True)

        if not panel["botones"]:
            return await interaction.response.send_message("❌ Este panel no tiene botones.", ephemeral=True)

        embed = discord.Embed(
            title=panel["titulo"],
            description=panel["descripcion"],
            color=validar_color(panel["color"])
        )

        view = VistaPanel(panel_id, panel)

        await interaction.response.send_message("✔ Panel enviado.", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)

# ============================================================
#   SETUP
# ============================================================

async def setup(bot):
    await bot.add_cog(Panels(bot))

    data = cargar_paneles()
    for guild_id, guild_panels in data.items():
        for panel_id, panel in guild_panels.items():

            # Registrar botones persistentes
            bot.add_view(VistaPanel(panel_id, panel))

            # Registrar menú persistente
            if "menu" in panel and panel["menu"]:
                bot.add_view(VistaPanelMenu(panel_id, panel["menu"]))