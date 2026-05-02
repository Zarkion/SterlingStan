from shared.checks import is_officer
from shared.db import scan_all_profiles
from shared.embeds import error_embed, roster_embed


def handle(interaction):
    if not is_officer(interaction):
        return error_embed("This command is for officers only.")

    members = scan_all_profiles()
    if not members:
        return error_embed("No members are registered yet.")

    return roster_embed(members)
