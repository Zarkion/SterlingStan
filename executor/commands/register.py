import re

from shared.db import (delete_member, get_member_profile, member_exists,
                       register_member, set_classes, update_member)
from shared.embeds import confirmation_embed, error_embed, profile_embed

_IGN_RE = re.compile(r'^[a-zA-Z0-9]{3,20}$')


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


def handle(interaction):
    user_id = interaction["member"]["user"]["id"]
    username = interaction["member"]["user"]["username"]
    ign = _opt(interaction, "ign") or ""

    if not _IGN_RE.match(ign):
        return error_embed("IGN must be 3–20 alphanumeric characters.")

    if member_exists(user_id):
        return error_embed("You are already registered.")

    register_member(user_id, username, ign)
    return _profile_response(user_id)


def handle_classes(interaction):
    user_id = interaction["member"]["user"]["id"]

    if not member_exists(user_id):
        return error_embed("You are not registered. Use /register first.")

    raw = _opt(interaction, "classes") or ""
    classes = [c.strip() for c in raw.split(",") if c.strip()]

    if not classes or len(classes) > 5:
        return error_embed("Please provide 1–5 classes, comma-separated.")

    set_classes(user_id, classes)
    return _profile_response(user_id)


def handle_update(interaction):
    user_id = interaction["member"]["user"]["id"]

    if not member_exists(user_id):
        return error_embed("You are not registered. Use /register first.")

    ign = _opt(interaction, "ign")
    classes_raw = _opt(interaction, "classes")

    if ign is None and classes_raw is None:
        return error_embed("Provide at least one of: ign, classes.")

    classes = None
    if classes_raw is not None:
        classes = [c.strip() for c in classes_raw.split(",") if c.strip()]
        if not classes or len(classes) > 5:
            return error_embed("Please provide 1–5 classes, comma-separated.")

    update_member(user_id, ign=ign, classes=classes)
    return _profile_response(user_id)


def handle_unregister(interaction):
    user_id = interaction["member"]["user"]["id"]

    if not member_exists(user_id):
        return error_embed("You are not registered.")

    return confirmation_embed(
        "Are you sure you want to remove your profile? This cannot be undone.",
        f"unregister_{user_id}",
    )
