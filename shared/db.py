import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr, Key


def _table():
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def member_exists(user_id: str) -> bool:
    response = _table().get_item(Key={"PK": f"MEMBER#{user_id}", "SK": "PROFILE"})
    return "Item" in response


def register_member(user_id: str, discord_tag: str, ign: str) -> dict:
    if member_exists(user_id):
        raise ValueError(f"Member {user_id} is already registered.")
    now = _now()
    item = {
        "PK": f"MEMBER#{user_id}",
        "SK": "PROFILE",
        "discord_tag": discord_tag,
        "ign": ign,
        "registered_at": now,
        "updated_at": now,
    }
    _table().put_item(Item=item)
    return {k: v for k, v in item.items() if k not in ("PK", "SK")}


def set_classes(user_id: str, classes: list) -> None:
    table = _table()
    pk = f"MEMBER#{user_id}"
    existing = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with("CLASS#")
    ).get("Items", [])

    if existing:
        with table.batch_writer() as batch:
            for item in existing:
                batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

    if classes:
        with table.batch_writer() as batch:
            for i, class_name in enumerate(classes, start=1):
                batch.put_item(Item={"PK": pk, "SK": f"CLASS#{i}", "class_name": class_name})


def get_member_profile(user_id: str) -> dict | None:
    items = _table().query(
        KeyConditionExpression=Key("PK").eq(f"MEMBER#{user_id}")
    ).get("Items", [])

    profile = next((i for i in items if i["SK"] == "PROFILE"), None)
    if not profile:
        return None

    classes = sorted(
        (i for i in items if i["SK"].startswith("CLASS#")),
        key=lambda x: int(x["SK"].split("#")[1]),
    )
    return {
        "profile": {k: v for k, v in profile.items() if k not in ("PK", "SK")},
        "classes": [c["class_name"] for c in classes],
    }


def update_member(user_id: str, ign: str = None, classes: list = None) -> dict:
    if ign is None and classes is None:
        raise ValueError("At least one of ign or classes must be provided.")
    now = _now()
    if ign is not None:
        _table().update_item(
            Key={"PK": f"MEMBER#{user_id}", "SK": "PROFILE"},
            UpdateExpression="SET ign = :ign, updated_at = :now",
            ExpressionAttributeValues={":ign": ign, ":now": now},
        )
    else:
        _table().update_item(
            Key={"PK": f"MEMBER#{user_id}", "SK": "PROFILE"},
            UpdateExpression="SET updated_at = :now",
            ExpressionAttributeValues={":now": now},
        )
    if classes is not None:
        set_classes(user_id, classes)
    return get_member_profile(user_id)


def delete_member(user_id: str) -> None:
    table = _table()
    items = table.query(
        KeyConditionExpression=Key("PK").eq(f"MEMBER#{user_id}")
    ).get("Items", [])
    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})


def scan_all_profiles() -> list:
    items = _table().scan(
        FilterExpression=Attr("SK").eq("PROFILE")
    ).get("Items", [])
    return [{k: v for k, v in item.items() if k not in ("PK", "SK")} for item in items]
