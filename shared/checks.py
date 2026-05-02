from shared.secrets import get_secret


def is_officer(interaction: dict) -> bool:
    officer_role_id = get_secret()["OFFICER_ROLE_ID"]
    member_roles = interaction.get("member", {}).get("roles", [])
    return officer_role_id in member_roles
