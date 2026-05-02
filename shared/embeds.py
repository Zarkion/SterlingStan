def profile_embed(ign, discord_tag, classes, registered_at):
    fields = [
        {"name": "Discord", "value": f"@{discord_tag}", "inline": True},
        {"name": "Member since", "value": registered_at[:10], "inline": True},
    ]
    if classes:
        fields.append({
            "name": "Favorite Classes",
            "value": "\n".join(f"{i + 1}. {c}" for i, c in enumerate(classes)),
        })
    return {
        "flags": 64,
        "embeds": [{"title": f"🗡️  {ign}", "fields": fields}],
    }


def roster_embed(members, page=1):
    page_size = 10
    start = (page - 1) * page_size
    page_members = members[start:start + page_size]
    total_pages = max(1, (len(members) + page_size - 1) // page_size)
    lines = [f"**@{m['discord_tag']}** — {m['ign']}" for m in page_members]
    return {
        "flags": 64,
        "embeds": [{
            "title": "Guild Roster",
            "description": "\n".join(lines) if lines else "No members registered.",
            "footer": {"text": f"Page {page} of {total_pages} · {len(members)} members"},
        }],
    }


def error_embed(message):
    return {
        "flags": 64,
        "embeds": [{"description": f"❌ {message}", "color": 0xED4245}],
    }


def confirmation_embed(prompt, custom_id):
    return {
        "flags": 64,
        "content": prompt,
        "components": [{
            "type": 1,
            "components": [
                {"type": 2, "style": 4, "label": "Yes, remove it", "custom_id": f"{custom_id}_confirm"},
                {"type": 2, "style": 2, "label": "Cancel", "custom_id": f"{custom_id}_cancel"},
            ],
        }],
    }
