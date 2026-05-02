from shared.checks import is_officer
from shared.db import get_member_profile
from shared.embeds import error_embed, profile_embed


def _profile_response(user_id):
    data = get_member_profile(user_id)
    if not data:
        return error_embed("That member is not registered.")
    return profile_embed(
        data["profile"]["ign"],
        data["profile"]["discord_tag"],
        data["classes"],
        data["profile"]["registered_at"],
    )


def handle(interaction):
    user_id = interaction["member"]["user"]["id"]
    data = get_member_profile(user_id)
    if not data:
        return error_embed("You are not registered. Use /register first.")
    return profile_embed(
        data["profile"]["ign"],
        data["profile"]["discord_tag"],
        data["classes"],
        data["profile"]["registered_at"],
    )


def handle_lookup(interaction):
    if not is_officer(interaction):
        return error_embed("This command is for officers only.")

    target_id = interaction["data"]["options"][0]["value"]
    return _profile_response(target_id)
