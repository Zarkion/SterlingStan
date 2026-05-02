import pytest


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
