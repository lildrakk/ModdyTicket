import json
import os
import datetime
from cogs.premium import is_premium

COOLDOWN_FILE = "cooldowns.json"


# ============================
# CARGAR / GUARDAR JSON
# ============================

def load_cooldowns():
    if not os.path.exists(COOLDOWN_FILE):
        with open(COOLDOWN_FILE, "w") as f:
            json.dump({}, f)
    with open(COOLDOWN_FILE, "r") as f:
        return json.load(f)

def save_cooldowns(data):
    with open(COOLDOWN_FILE, "w") as f:
        json.dump(data, f, indent=4)

cooldowns = load_cooldowns()


# ============================
# FUNCIONES PRINCIPALES
# ============================

def can_create_backup(user_id: int):
    """
    Devuelve:
    - True si puede crear backup
    - False si está en cooldown
    - Mensaje explicando el motivo
    """

    user_id = str(user_id)
    ahora = int(datetime.datetime.utcnow().timestamp())

    # Si no tiene registros → puede crear
    if user_id not in cooldowns:
        return True, None

    data = cooldowns[user_id]

    # ============================
    # SI ES PREMIUM
    # ============================

    if is_premium(int(user_id)):

        # Máximo 3 backups por día
        backups_hoy = 0
        hace_24h = ahora - 86400

        for t in data.get("backups", []):
            if t >= hace_24h:
                backups_hoy += 1

        if backups_hoy >= 3:
            return False, "❌ Como usuario **Premium**, puedes crear hasta **3 backups por día**."

        # Cooldown de 2 días
        ultimo = data.get("last_backup", 0)
        if ahora - ultimo < 172800:  # 2 días
            faltan = 172800 - (ahora - ultimo)
            horas = int(faltan / 3600)
            return False, f"⏳ Debes esperar **{horas} horas** para crear otro backup."

        return True, None

    # ============================
    # SI ES FREE
    # ============================

    ultimo = data.get("last_backup", 0)

    # Cooldown de 7 días
    if ahora - ultimo < 604800:  # 7 días
        faltan = 604800 - (ahora - ultimo)
        dias = int(faltan / 86400)
        return False, f"⏳ Como usuario **Free**, puedes crear un backup cada **7 días**. Te faltan **{dias} días**."

    return True, None


def register_backup(user_id: int):
    """
    Registra la creación de un backup.
    """

    user_id = str(user_id)
    ahora = int(datetime.datetime.utcnow().timestamp())

    if user_id not in cooldowns:
        cooldowns[user_id] = {
            "last_backup": ahora,
            "backups": [ahora]
        }
    else:
        cooldowns[user_id]["last_backup"] = ahora
        cooldowns[user_id].setdefault("backups", []).append(ahora)

    save_cooldowns(cooldowns)
