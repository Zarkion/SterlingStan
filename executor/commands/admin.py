from shared.checks import is_officer
from shared.db import get_member_profile, member_exists, register_member, update_member
from shared.embeds import confirmation_embed, error_embed, profile_embed


def _opt(interaction, name):
    for o in interaction["data"].get("options", []):
        if o["name"] == name:
            return o["value"]
    return None


def _profile_response(user_id):
    data = get_member_profile(user_id)
    return profile_embed(
        data["profile"]["ign"],
        data["profile"]["discord_tag"],
        data["classes"],
        data["profile"]["registered_at"],
    )


def handle_set(interaction):
    if not is_officer(interaction):
        return error_embed("This command is for officers only.")

    target_id = _opt(interaction, "user")
    members = interaction["data"].get("resolved", {}).get("members", {})
    target_username = members.get(target_id, {}).get("user", {}).get("username", "")

    ign = _opt(interaction, "ign")
    classes_raw = _opt(interaction, "classes")
    classes = None
    if classes_raw is not None:
        classes = [c.strip() for c in classes_raw.split(",") if c.strip()]

    if not member_exists(target_id):
        register_member(target_id, target_username, ign or "")
    else:
        update_member(target_id, ign=ign, classes=classes if classes else None)
        return _profile_response(target_id)

    if classes:
        from shared.db import set_classes
        set_classes(target_id, classes)

    return _profile_response(target_id)


def handle_remove(interaction):
    if not is_officer(interaction):
        return error_embed("This command is for officers only.")

    target_id = _opt(interaction, "user")
    members = interaction["data"].get("resolved", {}).get("members", {})
    target_username = members.get(target_id, {}).get("user", {}).get("username", target_id)

    return confirmation_embed(
        f"Remove all data for **@{target_username}**? This cannot be undone.",
        f"adminremove_{target_id}",
    )
