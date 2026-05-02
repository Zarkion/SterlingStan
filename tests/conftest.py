import json
import os
import sys

import boto3
import pytest
from moto import mock_aws

_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _repo_root)
sys.path.insert(0, os.path.join(_repo_root, "executor"))

EVENTS_DIR = os.path.join(os.path.dirname(__file__), "events")
OFFICER_ROLE_ID = "777777777777777777"


@pytest.fixture
def aws_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def aws(aws_credentials):
    with mock_aws():
        yield


@pytest.fixture
def dynamodb_table(aws, monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "sterlingstan-members")
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName="sterlingstan-members",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    yield table


@pytest.fixture
def secrets_mock(aws, monkeypatch):
    monkeypatch.setenv("SECRET_NAME", "sterlingstan/discord")
    client = boto3.client("secretsmanager", region_name="us-east-1")
    client.create_secret(
        Name="sterlingstan/discord",
        SecretString=json.dumps({
            "DISCORD_BOT_TOKEN": "test_bot_token",
            "DISCORD_PUBLIC_KEY": "aa" * 32,
            "DISCORD_APP_ID": "111111111111111111",
            "DISCORD_GUILD_ID": "222222222222222222",
            "OFFICER_ROLE_ID": OFFICER_ROLE_ID,
        }),
    )
    yield


@pytest.fixture(autouse=True)
def reset_secrets_cache(monkeypatch):
    try:
        import shared.secrets as secrets_module
        monkeypatch.setattr(secrets_module, "_secret_cache", None, raising=False)
    except ImportError:
        pass
    yield


def make_interaction(command_name, options=None, user_id="444444444444444444",
                     username="TestPlayer", roles=None, resolved=None):
    data = {"id": "555555555555555555", "name": command_name,
            "type": 1, "options": options or []}
    if resolved:
        data["resolved"] = resolved
    return {
        "type": 2, "application_id": "111111111111111111",
        "token": "test_interaction_token", "id": "999999999999999999",
        "guild_id": "222222222222222222", "channel_id": "333333333333333333",
        "member": {
            "user": {"id": user_id, "username": username, "discriminator": "0"},
            "roles": roles or [],
        },
        "data": data,
    }


@pytest.fixture
def registered_member(dynamodb_table, secrets_mock):
    from shared.db import register_member
    register_member("444444444444444444", "TestPlayer", "HeroOfLore")
    return {"user_id": "444444444444444444", "discord_tag": "TestPlayer", "ign": "HeroOfLore"}


@pytest.fixture
def member_interaction():
    with open(os.path.join(EVENTS_DIR, "register_command.json")) as f:
        return json.load(f)


@pytest.fixture
def officer_interaction():
    with open(os.path.join(EVENTS_DIR, "register_command.json")) as f:
        event = json.load(f)
    event["member"]["roles"] = [OFFICER_ROLE_ID]
    return event
