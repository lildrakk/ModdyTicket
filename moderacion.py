import discord
from discord.ext import commands
from discord import app_commands
import json
import asyncio
import os
import sys


class Moderacion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ============================
    # PURGE USER
    # ============================

    @app_commands.command(name="purgeuser", description="Elimina mensajes de un usuario en este canal")
    @app_commands.describe(usuario="Usuario cuyos mensajes se eliminarán", cantidad="Máximo 100")
    async def purgeuser(self, interaction: discord.Interaction, usuario: discord.User, cantidad: int):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)

        cantidad = min(cantidad, 100)
        borrados = await interaction.channel.purge(limit=cantidad, check=lambda m: m.author == usuario)

        await interaction.response.send_message(
            f"🧹 Se eliminaron **{len(borrados)}** mensajes de {usuario.mention}.",
            ephemeral=True
        )

    # ============================
    # PURGE BOT
    # ============================

    @app_commands.command(name="purgebot", description="Elimina mensajes de bots en este canal")
    @app_commands.describe(cantidad="Máximo 100")
    async def purgebot(self, interaction: discord.Interaction, cantidad: int):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)

        cantidad = min(cantidad, 100)
        borrados = await interaction.channel.purge(limit=cantidad, check=lambda m: m.author.bot)

        await interaction.response.send_message(
            f"🤖 Se eliminaron **{len(borrados)}** mensajes de bots.",
            ephemeral=True
        )

    # ============================
    # PURGE GENERAL
    # ============================

    @app_commands.command(name="purge", description="Borra mensajes rápidamente")
    @app_commands.describe(cantidad="Cantidad de mensajes a borrar")
    async def purge(self, interaction: discord.Interaction, cantidad: int):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        borrados = await interaction.channel.purge(limit=cantidad)

        await interaction.followup.send(
            f"🧹 Se borraron **{len(borrados)}** mensajes.",
            ephemeral=True
        )

    # ============================
    # WARN (VERSIÓN ULTRA EXTENDIDA)
    # ============================

    @app_commands.command(name="warn", description="Da un warning a un usuario")
    async def warn(self, interaction: discord.Interaction, usuario: discord.User, motivo: str):
        if not interaction.user.guild_permissions.kick_members:
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)

        # Cargar base de datos
        try:
            with open("warnings.json", "r") as f:
                data = json.load(f)
        except:
            data = {}

        gid = str(interaction.guild.id)
        uid = str(usuario.id)

        if gid not in data:
            data[gid] = {}
        if uid not in data[gid]:
            data[gid][uid] = []

        # Registrar warn
        fecha_raw = discord.utils.utcnow()
        fecha_formateada = fecha_raw.strftime("%d/%m/%Y • %H:%M UTC")

        data[gid][uid].append({
            "moderator": interaction.user.id,
            "motivo": motivo,
            "fecha": fecha_formateada
        })

        with open("warnings.json", "w") as f:
            json.dump(data, f, indent=4)

        total_warns = len(data[gid][uid])

        # ============================
        # EMBED PÚBLICO (ULTRA EXTENDIDO)
        # ============================

        embed_publico = discord.Embed(
            title="🟧 Informe Disciplinario — Advertencia Emitida",
            description=(
                f"Se ha registrado una acción disciplinaria para {usuario.mention}.\n"
                "Este informe contiene todos los detalles relevantes del caso."
            ),
            color=discord.Color.from_rgb(255, 120, 40)
        )

        embed_publico.add_field(
            name="👤 Usuario sancionado",
            value=f"{usuario.mention}",
            inline=False
        )

        embed_publico.add_field(
            name="👮 Moderador que aplicó la advertencia",
            value=f"{interaction.user.mention}",
            inline=False
        )

        embed_publico.add_field(
            name="📄 Motivo detallado",
            value=motivo,
            inline=False
        )

        embed_publico.add_field(
            name="🕒 Fecha y hora del registro",
            value=fecha_formateada,
            inline=False
        )

        embed_publico.add_field(
            name="📊 Historial del usuario",
            value=f"Advertencias acumuladas en este servidor: **{total_warns}**",
            inline=False
        )

        embed_publico.add_field(
            name="📨 Notificación al usuario",
            value="Se intentó enviar un mensaje privado con los detalles de la advertencia.",
            inline=False
        )

        embed_publico.add_field(
            name="🗂️ Información adicional",
            value=(
                "• Este registro ha sido archivado en el sistema interno.\n"
                "• El equipo de moderación puede revisar este caso en cualquier momento.\n"
                "• Acciones futuras pueden depender del historial acumulado."
            ),
            inline=False
        )

        embed_publico.set_footer(
            text=f"ID del usuario: {usuario.id} • Sistema de Moderación Avanzada"
        )

        await interaction.response.send_message(embed=embed_publico)

        # ============================
        # EMBED DM (ESTILO QUE TE GUSTÓ)
        # ============================

        embed_dm = discord.Embed(
            title="📢 Aviso Importante — Registro Disciplinario",
            description="Has recibido una advertencia en un servidor.",
            color=discord.Color.from_rgb(255, 60, 60)
        )

        embed_dm.add_field(
            name="🏛️ Servidor",
            value=interaction.guild.name,
            inline=False
        )

        embed_dm.add_field(
            name="📄 Motivo de la advertencia",
            value=motivo,
            inline=False
        )

        embed_dm.add_field(
            name="👮 Moderador que aplicó la sanción",
            value=f"{interaction.user} (`{interaction.user.id}`)",
            inline=False
        )

        embed_dm.add_field(
            name="🕒 Fecha del registro",
            value=fecha_formateada,
            inline=False
        )

        embed_dm.add_field(
            name="📊 Historial del usuario",
            value=f"Tienes ahora **{total_warns}** advertencias en este servidor.",
            inline=False
        )

        embed_dm.set_footer(text="Este mensaje fue enviado automáticamente por el sistema de moderación.")

        try:
            await usuario.send(embed=embed_dm)
        except:
            pass
    # ============================
    # WARNINGS LIST
    # ============================

    @app_commands.command(name="ver_warns", description="Muestra los warnings de un usuario")
    async def warnings(self, interaction: discord.Interaction, usuario: discord.User):
        try:
            with open("warnings.json", "r") as f:
                data = json.load(f)
        except:
            data = {}

        gid = str(interaction.guild.id)
        uid = str(usuario.id)

        if gid in data and uid in data[gid]:
            embed = discord.Embed(
                title=f"⚠️ Warnings de {usuario}",
                color=discord.Color.orange()
            )

            for i, w in enumerate(data[gid][uid], 1):
                mod = interaction.guild.get_member(w["moderator"])
                embed.add_field(
                    name=f"Warn #{i}",
                    value=f"Moderador: {mod}\nMotivo: {w['motivo']}",
                    inline=False
                )

            return await interaction.response.send_message(embed=embed, ephemeral=True)

        await interaction.response.send_message(
            f"✅ {usuario.mention} no tiene warnings.",
            ephemeral=True
        )

    # ============================
    # ELIMINAR WARN
    # ============================

    @app_commands.command(name="eliminar_warn", description="Elimina un warning específico de un usuario")
    @app_commands.describe(usuario="Usuario al que quieres quitar el warn", numero="Número del warn a eliminar (1, 2, 3...)")
    async def delwarn(self, interaction: discord.Interaction, usuario: discord.User, numero: int):
        if not interaction.user.guild_permissions.kick_members:
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)

        try:
            with open("warnings.json", "r") as f:
                data = json.load(f)
        except:
            data = {}

        gid = str(interaction.guild.id)
        uid = str(usuario.id)

        if gid not in data or uid not in data[gid] or len(data[gid][uid]) == 0:
            return await interaction.response.send_message(
                f"ℹ️ {usuario.mention} no tiene warnings.",
                ephemeral=True
            )

        warnings_list = data[gid][uid]

        if numero < 1 or numero > len(warnings_list):
            return await interaction.response.send_message(
                f"❌ Número inválido. Este usuario solo tiene **{len(warnings_list)}** warnings.",
                ephemeral=True
            )

        eliminado = warnings_list.pop(numero - 1)

        with open("warnings.json", "w") as f:
            json.dump(data, f, indent=4)

        await interaction.response.send_message(
            f"🗑️ Se eliminó el **warn #{numero}** de {usuario.mention}.\n"
            f"Motivo eliminado: **{eliminado['motivo']}**",
            ephemeral=True
        )

    # ============================
    # ELIMINAR WARNS
    # ============================

    @app_commands.command(name="eliminar_warns", description="Limpia todos los warns de un usuario")
    async def clearwarnings(self, interaction: discord.Interaction, usuario: discord.User):
        if not interaction.user.guild_permissions.kick_members:
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)

        try:
            with open("warnings.json", "r") as f:
                data = json.load(f)
        except:
            data = {}

        gid = str(interaction.guild.id)
        uid = str(usuario.id)

        if gid in data and uid in data[gid]:
            data[gid][uid] = []
            with open("warnings.json", "w") as f:
                json.dump(data, f, indent=4)

            return await interaction.response.send_message(
                f"🧽 Warnings de {usuario.mention} eliminados.",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"ℹ️ {usuario.mention} no tenía warnings.",
            ephemeral=True
        )

    # ============================
    # MUTE
    # ============================

    @app_commands.command(name="mute", description="Mutea a un usuario")
    async def mute(self, interaction: discord.Interaction, usuario: discord.Member, minutos: int = 10):
        if not interaction.user.guild_permissions.moderate_members:
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)

        duracion = discord.utils.utcnow() + discord.timedelta(minutes=minutos)

        await usuario.timeout(duracion, reason="Mute manual")

        await interaction.response.send_message(
            f"🔇 {usuario.mention} muteado por **{minutos} minutos**.",
            ephemeral=True
        )

    # ============================
    # UNMUTE
    # ============================

    @app_commands.command(name="unmute", description="Desmutea a un usuario")
    async def unmute(self, interaction: discord.Interaction, usuario: discord.Member):
        if not interaction.user.guild_permissions.moderate_members:
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)

        await usuario.timeout(None)

        await interaction.response.send_message(
            f"🔊 {usuario.mention} ha sido desmuteado.",
            ephemeral=True
        )

    # ============================
    # BAN
    # ============================

    @app_commands.command(name="ban", description="Banea a un usuario")
    async def ban(self, interaction: discord.Interaction, usuario: discord.User, razon: str = "No especificada"):
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)

        await interaction.guild.ban(usuario, reason=razon)

        await interaction.response.send_message(
            f"⛔ {usuario.mention} ha sido baneado.\nRazón: **{razon}**",
            ephemeral=True
        )

    # ============================
    # UNBAN
    # ============================

    @app_commands.command(name="unban", description="Desbanea a un usuario por ID")
    async def unban(self, interaction: discord.Interaction, user_id: str):
        if not interaction.user.guild_permissions.ban_members:
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)

        try:
            usuario = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(usuario)
            await interaction.response.send_message(
                f"✅ Usuario `{user_id}` desbaneado.",
                ephemeral=True
            )
        except:
            await interaction.response.send_message(
                "❌ No se pudo desbanear. ¿ID correcto?",
                ephemeral=True
            )

    # ============================
    # CAMBIAR NICK
    # ============================

    @app_commands.command(name="nick", description="Cambia el nick de un usuario")
    @app_commands.describe(usuario="Usuario al que cambiar el nick", nuevo_nick="Nuevo nick")
    async def nick(self, interaction: discord.Interaction, usuario: discord.Member, nuevo_nick: str):
        if not interaction.user.guild_permissions.manage_nicknames:
            return await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        try:
            await usuario.edit(nick=nuevo_nick)
            await interaction.followup.send(f"✏️ Nick cambiado a **{nuevo_nick}** para {usuario.mention}.")
        except discord.Forbidden:
            await interaction.followup.send("❌ No tengo permisos para cambiar ese nick.")
        except Exception as e:
            await interaction.followup.send(f"❌ Error inesperado: {e}")


async def setup(bot):
    await bot.add_cog(Moderacion(bot))
