import pytest
from conftest import make_interaction, OFFICER_ROLE_ID


class TestSecrets:

    def test_get_secret_returns_all_keys(self, secrets_mock):
        from shared.secrets import get_secret
        result = get_secret()
        for key in ("DISCORD_BOT_TOKEN", "DISCORD_PUBLIC_KEY", "DISCORD_APP_ID",
                    "DISCORD_GUILD_ID", "OFFICER_ROLE_ID"):
            assert key in result

    def test_get_secret_caches_on_second_call(self, secrets_mock):
        from shared.secrets import get_secret
        result1 = get_secret()
        result2 = get_secret()
        assert result1 is result2

    def test_get_secret_reads_secret_name_from_env(self, aws, monkeypatch):
        from shared.secrets import get_secret
        monkeypatch.setenv("SECRET_NAME", "nonexistent/secret")
        with pytest.raises(Exception):
            get_secret()


class TestChecks:

    def test_is_officer_true_when_role_present(self, secrets_mock, officer_interaction):
        from shared.checks import is_officer
        assert is_officer(officer_interaction) is True

    def test_is_officer_false_when_role_absent(self, secrets_mock, member_interaction):
        from shared.checks import is_officer
        assert is_officer(member_interaction) is False

    def test_is_officer_false_when_no_roles(self, secrets_mock, member_interaction):
        from shared.checks import is_officer
        member_interaction["member"]["roles"] = []
        assert is_officer(member_interaction) is False

    def test_is_officer_false_when_no_member_key(self, secrets_mock, member_interaction):
        from shared.checks import is_officer
        del member_interaction["member"]
        assert is_officer(member_interaction) is False


class TestDb:

    def test_member_exists_false_when_not_registered(self, dynamodb_table):
        from shared.db import member_exists
        assert member_exists("999") is False

    def test_register_member_creates_profile_item(self, dynamodb_table):
        from shared.db import register_member
        result = register_member("444444444444444444", "TestPlayer", "HeroOfLore")
        assert result["ign"] == "HeroOfLore"
        assert result["discord_tag"] == "TestPlayer"
        assert "registered_at" in result

    def test_member_exists_true_after_register(self, dynamodb_table):
        from shared.db import register_member, member_exists
        register_member("444444444444444444", "TestPlayer", "HeroOfLore")
        assert member_exists("444444444444444444") is True

    def test_register_member_fails_if_already_registered(self, dynamodb_table):
        from shared.db import register_member
        register_member("444444444444444444", "TestPlayer", "HeroOfLore")
        with pytest.raises(ValueError):
            register_member("444444444444444444", "TestPlayer", "HeroOfLore2")

    def test_set_classes_writes_class_items(self, dynamodb_table):
        from shared.db import register_member, set_classes, get_member_profile
        register_member("444444444444444444", "TestPlayer", "HeroOfLore")
        set_classes("444444444444444444", ["Void Highlord", "Stonecrusher"])
        profile = get_member_profile("444444444444444444")
        assert profile["classes"] == ["Void Highlord", "Stonecrusher"]

    def test_set_classes_replaces_old_classes(self, dynamodb_table):
        from shared.db import register_member, set_classes, get_member_profile
        register_member("444444444444444444", "TestPlayer", "HeroOfLore")
        set_classes("444444444444444444", ["ClassA", "ClassB", "ClassC"])
        set_classes("444444444444444444", ["OnlyClass"])
        profile = get_member_profile("444444444444444444")
        assert profile["classes"] == ["OnlyClass"]

    def test_get_member_profile_returns_profile_and_classes(self, dynamodb_table):
        from shared.db import register_member, set_classes, get_member_profile
        register_member("444444444444444444", "TestPlayer", "HeroOfLore")
        set_classes("444444444444444444", ["Void Highlord"])
        profile = get_member_profile("444444444444444444")
        assert profile["profile"]["ign"] == "HeroOfLore"
        assert profile["classes"] == ["Void Highlord"]

    def test_get_member_profile_returns_none_if_not_registered(self, dynamodb_table):
        from shared.db import get_member_profile
        assert get_member_profile("nonexistent") is None

    def test_delete_member_removes_all_items(self, dynamodb_table):
        from shared.db import register_member, set_classes, delete_member, member_exists, get_member_profile
        register_member("444444444444444444", "TestPlayer", "HeroOfLore")
        set_classes("444444444444444444", ["Void Highlord", "Stonecrusher"])
        delete_member("444444444444444444")
        assert member_exists("444444444444444444") is False
        assert get_member_profile("444444444444444444") is None

    def test_scan_all_profiles_returns_only_profile_items(self, dynamodb_table):
        from shared.db import register_member, set_classes, scan_all_profiles
        register_member("111", "PlayerOne", "HeroOne")
        register_member("222", "PlayerTwo", "HeroTwo")
        set_classes("111", ["Void Highlord", "Stonecrusher"])
        profiles = scan_all_profiles()
        assert len(profiles) == 2
        assert {p["ign"] for p in profiles} == {"HeroOne", "HeroTwo"}


class TestRegisterCommand:

    def test_register_success_returns_profile_embed(self, dynamodb_table):
        from commands.register import handle
        result = handle(make_interaction("register", options=[
            {"name": "ign", "type": 3, "value": "HeroOfLore"}
        ]))
        assert "embeds" in result

    def test_register_stores_ign_in_dynamo(self, dynamodb_table):
        from commands.register import handle
        from shared.db import get_member_profile
        handle(make_interaction("register", options=[
            {"name": "ign", "type": 3, "value": "HeroOfLore"}
        ]))
        assert get_member_profile("444444444444444444")["profile"]["ign"] == "HeroOfLore"

    def test_register_rejects_ign_too_short(self, dynamodb_table):
        from commands.register import handle
        result = handle(make_interaction("register", options=[
            {"name": "ign", "type": 3, "value": "ab"}
        ]))
        assert result.get("flags") == 64

    def test_register_rejects_ign_too_long(self, dynamodb_table):
        from commands.register import handle
        result = handle(make_interaction("register", options=[
            {"name": "ign", "type": 3, "value": "a" * 21}
        ]))
        assert result.get("flags") == 64

    def test_register_rejects_non_alphanumeric_ign(self, dynamodb_table):
        from commands.register import handle
        result = handle(make_interaction("register", options=[
            {"name": "ign", "type": 3, "value": "Hero!Lore"}
        ]))
        assert result.get("flags") == 64

    def test_register_rejects_already_registered(self, registered_member):
        from commands.register import handle
        result = handle(make_interaction("register", options=[
            {"name": "ign", "type": 3, "value": "AnotherHero"}
        ]))
        assert result.get("flags") == 64


class TestSetClassesCommand:

    def test_setclasses_saves_up_to_5_classes(self, registered_member):
        from commands.register import handle_classes
        from shared.db import get_member_profile
        handle_classes(make_interaction("setclasses", options=[
            {"name": "classes", "type": 3, "value": "Void Highlord, Stonecrusher, Archpaladin"}
        ]))
        profile = get_member_profile("444444444444444444")
        assert profile["classes"] == ["Void Highlord", "Stonecrusher", "Archpaladin"]

    def test_setclasses_rejects_more_than_5(self, registered_member):
        from commands.register import handle_classes
        result = handle_classes(make_interaction("setclasses", options=[
            {"name": "classes", "type": 3, "value": "A, B, C, D, E, F"}
        ]))
        assert result.get("flags") == 64

    def test_setclasses_rejects_empty_input(self, registered_member):
        from commands.register import handle_classes
        result = handle_classes(make_interaction("setclasses", options=[
            {"name": "classes", "type": 3, "value": "   "}
        ]))
        assert result.get("flags") == 64

    def test_setclasses_rejects_not_registered(self, dynamodb_table):
        from commands.register import handle_classes
        result = handle_classes(make_interaction("setclasses", options=[
            {"name": "classes", "type": 3, "value": "Void Highlord"}
        ]))
        assert result.get("flags") == 64


class TestUpdateCommand:

    def test_update_ign_returns_updated_profile_embed(self, registered_member):
        from commands.register import handle_update
        from shared.db import get_member_profile
        result = handle_update(make_interaction("update", options=[
            {"name": "ign", "type": 3, "value": "NewHeroName"}
        ]))
        assert "embeds" in result
        assert get_member_profile("444444444444444444")["profile"]["ign"] == "NewHeroName"

    def test_update_classes_updates_classes(self, registered_member):
        from commands.register import handle_update
        from shared.db import get_member_profile
        handle_update(make_interaction("update", options=[
            {"name": "classes", "type": 3, "value": "Stonecrusher"}
        ]))
        assert get_member_profile("444444444444444444")["classes"] == ["Stonecrusher"]

    def test_update_requires_at_least_one_option(self, registered_member):
        from commands.register import handle_update
        result = handle_update(make_interaction("update", options=[]))
        assert result.get("flags") == 64

    def test_update_rejects_not_registered(self, dynamodb_table):
        from commands.register import handle_update
        result = handle_update(make_interaction("update", options=[
            {"name": "ign", "type": 3, "value": "NewHero"}
        ]))
        assert result.get("flags") == 64


class TestVerifierHandler:

    @pytest.fixture
    def signing_key(self):
        from nacl.signing import SigningKey
        return SigningKey.generate()

    @pytest.fixture
    def verifier_secrets(self, signing_key, aws, monkeypatch):
        import boto3
        monkeypatch.setenv("SECRET_NAME", "sterlingstan/discord")
        monkeypatch.setenv("EXECUTOR_FUNCTION_NAME", "sterlingstan-executor")
        client = boto3.client("secretsmanager", region_name="us-east-1")
        client.create_secret(
            Name="sterlingstan/discord",
            SecretString=__import__("json").dumps({
                "DISCORD_BOT_TOKEN": "test_token",
                "DISCORD_PUBLIC_KEY": signing_key.verify_key.encode().hex(),
                "DISCORD_APP_ID": "111111111111111111",
                "DISCORD_GUILD_ID": "222222222222222222",
                "OFFICER_ROLE_ID": OFFICER_ROLE_ID,
            }),
        )
        yield

    def _signed_event(self, signing_key, body_dict):
        import json
        body = json.dumps(body_dict)
        timestamp = "1234567890"
        signed = signing_key.sign(f"{timestamp}{body}".encode())
        return {
            "headers": {
                "x-signature-ed25519": signed.signature.hex(),
                "x-signature-timestamp": timestamp,
            },
            "body": body,
        }

    def test_warmup_event_returns_200(self, aws_credentials):
        from verifier.handler import handler
        result = handler({"source": "sterlingstan.warmup"}, None)
        assert result["statusCode"] == 200

    def test_invalid_signature_returns_401(self, verifier_secrets):
        from verifier.handler import handler
        result = handler({
            "headers": {
                "x-signature-ed25519": "aa" * 64,
                "x-signature-timestamp": "1234567890",
            },
            "body": "{}",
        }, None)
        assert result["statusCode"] == 401

    def test_ping_returns_type_1(self, verifier_secrets, signing_key):
        from verifier.handler import handler
        event = self._signed_event(signing_key, {"type": 1})
        result = handler(event, None)
        assert result["statusCode"] == 200
        assert __import__("json").loads(result["body"]) == {"type": 1}

    def test_slash_command_returns_type_5(self, verifier_secrets, signing_key, mocker):
        from verifier import handler as verifier_handler
        mocker.patch.object(verifier_handler.lambda_client, "invoke")
        event = self._signed_event(signing_key, {"type": 2, "data": {"name": "profile"}})
        result = verifier_handler.handler(event, None)
        assert result["statusCode"] == 200
        assert __import__("json").loads(result["body"]) == {"type": 5}

    def test_slash_command_invokes_executor_async(self, verifier_secrets, signing_key, mocker):
        from verifier import handler as verifier_handler
        mock_invoke = mocker.patch.object(verifier_handler.lambda_client, "invoke")
        event = self._signed_event(signing_key, {"type": 2, "data": {"name": "profile"}})
        verifier_handler.handler(event, None)
        mock_invoke.assert_called_once()
        assert mock_invoke.call_args.kwargs["InvocationType"] == "Event"


class TestExecutorHandler:

    def test_dispatch_routes_to_correct_handler(self, mocker):
        from executor import handler as executor_handler
        mocker.patch.object(executor_handler, "post_followup")
        mock_cmd = mocker.MagicMock(return_value={"content": "ok"})
        mocker.patch.dict(executor_handler.DISPATCH, {"register": mock_cmd})
        executor_handler.handler(make_interaction("register"), None)
        mock_cmd.assert_called_once()

    def test_unknown_command_returns_error_content(self, mocker):
        from executor import handler as executor_handler
        captured = {}
        def fake_followup(app_id, token, data):
            captured["data"] = data
        mocker.patch.object(executor_handler, "post_followup", side_effect=fake_followup)
        executor_handler.handler(make_interaction("nonexistent_command"), None)
        assert "nonexistent_command" in captured["data"]["content"]

    def test_post_followup_patches_correct_url(self, mocker):
        from executor.handler import post_followup
        mock_urlopen = mocker.patch("urllib.request.urlopen")
        post_followup("111111111111111111", "test_token", {"content": "hello"})
        call_args = mock_urlopen.call_args[0][0]
        assert "111111111111111111" in call_args.full_url
        assert "test_token" in call_args.full_url
        assert call_args.method == "PATCH"


class TestAdminCommand:

    def test_adminset_creates_new_member_profile(self, dynamodb_table, secrets_mock):
        from commands.admin import handle_set
        from shared.db import get_member_profile
        target_id = "999999999999999999"
        result = handle_set(make_interaction(
            "adminset",
            options=[
                {"name": "user", "type": 6, "value": target_id},
                {"name": "ign",  "type": 3, "value": "NewHero"},
            ],
            roles=[OFFICER_ROLE_ID],
            resolved={"members": {target_id: {"user": {"id": target_id, "username": "NewPlayer"}}}},
        ))
        assert "embeds" in result
        assert get_member_profile(target_id)["profile"]["ign"] == "NewHero"

    def test_adminset_updates_existing_member(self, registered_member):
        from commands.admin import handle_set
        from shared.db import get_member_profile
        target_id = "444444444444444444"
        handle_set(make_interaction(
            "adminset",
            options=[
                {"name": "user", "type": 6, "value": target_id},
                {"name": "ign",  "type": 3, "value": "UpdatedHero"},
            ],
            roles=[OFFICER_ROLE_ID],
            resolved={"members": {target_id: {"user": {"id": target_id, "username": "TestPlayer"}}}},
        ))
        assert get_member_profile(target_id)["profile"]["ign"] == "UpdatedHero"

    def test_adminset_rejects_non_officer(self, dynamodb_table, secrets_mock):
        from commands.admin import handle_set
        target_id = "999999999999999999"
        result = handle_set(make_interaction(
            "adminset",
            options=[{"name": "user", "type": 6, "value": target_id}],
            resolved={"members": {target_id: {"user": {"id": target_id, "username": "Someone"}}}},
        ))
        assert result.get("flags") == 64

    def test_adminremove_returns_confirmation_embed(self, registered_member):
        from commands.admin import handle_remove
        target_id = "444444444444444444"
        result = handle_remove(make_interaction(
            "adminremove",
            options=[{"name": "user", "type": 6, "value": target_id}],
            roles=[OFFICER_ROLE_ID],
            resolved={"members": {target_id: {"user": {"id": target_id, "username": "TestPlayer"}}}},
        ))
        assert "components" in result
        assert len(result["components"][0]["components"]) == 2

    def test_adminremove_rejects_non_officer(self, registered_member):
        from commands.admin import handle_remove
        target_id = "444444444444444444"
        result = handle_remove(make_interaction(
            "adminremove",
            options=[{"name": "user", "type": 6, "value": target_id}],
            resolved={"members": {target_id: {"user": {"id": target_id, "username": "TestPlayer"}}}},
        ))
        assert result.get("flags") == 64


class TestRosterCommand:

    def test_roster_returns_embed_listing_members(self, dynamodb_table, secrets_mock):
        from commands.roster import handle
        from shared.db import register_member
        register_member("111", "PlayerOne", "HeroOne")
        register_member("222", "PlayerTwo", "HeroTwo")
        result = handle(make_interaction("roster", roles=[OFFICER_ROLE_ID]))
        assert "embeds" in result
        embed_text = str(result["embeds"][0])
        assert "HeroOne" in embed_text
        assert "HeroTwo" in embed_text

    def test_roster_returns_error_if_no_members(self, dynamodb_table, secrets_mock):
        from commands.roster import handle
        result = handle(make_interaction("roster", roles=[OFFICER_ROLE_ID]))
        assert result.get("flags") == 64

    def test_roster_rejects_non_officer(self, dynamodb_table, secrets_mock):
        from commands.roster import handle
        result = handle(make_interaction("roster"))
        assert result.get("flags") == 64


class TestProfileCommand:

    def test_profile_returns_embed_for_registered_user(self, registered_member):
        from commands.profile import handle
        result = handle(make_interaction("profile"))
        assert "embeds" in result

    def test_profile_returns_error_if_not_registered(self, dynamodb_table):
        from commands.profile import handle
        result = handle(make_interaction("profile"))
        assert result.get("flags") == 64

    def test_lookup_returns_target_profile(self, registered_member):
        from commands.profile import handle_lookup
        target_id = "444444444444444444"
        result = handle_lookup(make_interaction(
            "lookup",
            options=[{"name": "user", "type": 6, "value": target_id}],
            roles=[OFFICER_ROLE_ID],
            resolved={"members": {target_id: {"user": {"id": target_id, "username": "TestPlayer"}}}},
        ))
        assert "embeds" in result

    def test_lookup_rejects_non_officer(self, registered_member):
        from commands.profile import handle_lookup
        target_id = "444444444444444444"
        result = handle_lookup(make_interaction(
            "lookup",
            options=[{"name": "user", "type": 6, "value": target_id}],
            resolved={"members": {target_id: {"user": {"id": target_id, "username": "TestPlayer"}}}},
        ))
        assert result.get("flags") == 64

    def test_lookup_returns_error_if_target_not_registered(self, dynamodb_table, secrets_mock):
        from commands.profile import handle_lookup
        target_id = "999999999999999999"
        result = handle_lookup(make_interaction(
            "lookup",
            options=[{"name": "user", "type": 6, "value": target_id}],
            roles=[OFFICER_ROLE_ID],
            resolved={"members": {target_id: {"user": {"id": target_id, "username": "Ghost"}}}},
        ))
        assert result.get("flags") == 64


class TestUnregisterCommand:

    def test_unregister_returns_confirmation_embed(self, registered_member):
        from commands.register import handle_unregister
        result = handle_unregister(make_interaction("unregister"))
        assert "components" in result
        buttons = result["components"][0]["components"]
        assert len(buttons) == 2

    def test_unregister_rejects_not_registered(self, dynamodb_table):
        from commands.register import handle_unregister
        result = handle_unregister(make_interaction("unregister"))
        assert result.get("flags") == 64


class TestEmbeds:

    def test_profile_embed_has_required_fields(self):
        from shared.embeds import profile_embed
        result = profile_embed("HeroOfLore", "TestPlayer", ["VoidHighlord"], "2025-04-01T00:00:00Z")
        assert "embeds" in result
        embed = result["embeds"][0]
        assert "title" in embed
        assert "fields" in embed

    def test_profile_embed_shows_ign_and_tag(self):
        from shared.embeds import profile_embed
        result = profile_embed("HeroOfLore", "TestPlayer", [], "2025-04-01T00:00:00Z")
        embed_text = str(result["embeds"][0])
        assert "HeroOfLore" in embed_text
        assert "TestPlayer" in embed_text

    def test_profile_embed_shows_classes_in_order(self):
        from shared.embeds import profile_embed
        classes = ["Void Highlord", "Stonecrusher", "Archpaladin"]
        result = profile_embed("Hero", "Player", classes, "2025-04-01T00:00:00Z")
        fields_text = " ".join(str(f.get("value", "")) for f in result["embeds"][0]["fields"])
        assert "1. Void Highlord" in fields_text
        assert "2. Stonecrusher" in fields_text
        assert "3. Archpaladin" in fields_text

    def test_roster_embed_paginates_at_10(self):
        from shared.embeds import roster_embed
        members = [{"ign": f"Hero{i}", "discord_tag": f"Player{i}"} for i in range(11)]
        result = roster_embed(members, page=1)
        embed_text = str(result["embeds"][0])
        assert "Hero9" in embed_text
        assert "Hero10" not in embed_text

    def test_error_embed_is_ephemeral(self):
        from shared.embeds import error_embed
        result = error_embed("Something went wrong")
        assert result.get("flags") == 64

    def test_confirmation_embed_has_two_components(self):
        from shared.embeds import confirmation_embed
        result = confirmation_embed("Are you sure?", "unregister_123")
        buttons = result["components"][0]["components"]
        assert len(buttons) == 2
        labels = [b["label"] for b in buttons]
        assert "Yes, remove it" in labels
        assert "Cancel" in labels
