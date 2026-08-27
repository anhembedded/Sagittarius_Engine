import json
from unittest.mock import MagicMock

import pytest

from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.config.config_source import ConfigSource


def test_config_manager_convenience_loaders(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"json_k": "json_v"}))
    monkeypatch.setenv("TEST_ENV_K", "env_v")

    manager = ConfigManager()
    manager.load_dict({"dict_k": "dict_v"})
    manager.load_json(str(config_file))
    manager.load_env("TEST_ENV_")

    assert manager.get("dict_k") == "dict_v"
    assert manager.get("json_k") == "json_v"
    assert manager.get("K") == "env_v"


def test_config_manager_from_json(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"json_k": "json_v"}))

    manager = ConfigManager.from_json(str(config_file))
    assert manager.get("json_k") == "json_v"


def test_config_manager_load_exception():
    manager = ConfigManager()
    broken_source = MagicMock(spec=ConfigSource)
    broken_source.read.side_effect = Exception("Failed to read")
    manager.add_source(broken_source)

    manager.load_dict({"valid_k": "valid_v"})

    # Should swallow exception and continue loading subsequent sources
    assert manager.get("valid_k") == "valid_v"


def test_config_manager_get_casting():
    manager = ConfigManager()
    manager.load_dict(
        {
            "int_str": "123",
            "float_str": "1.23",
            "invalid_int": "abc",
            "already_int": 456,
        }
    )

    # Test successful cast
    assert manager.get("int_str", cast=int) == 123
    assert manager.get("float_str", cast=float) == 1.23

    # Test invalid cast (should fallback to returning original value)
    assert manager.get("invalid_int", cast=int) == "abc"

    # Test already same type
    assert manager.get("already_int", cast=int) == 456

    # Test default
    assert manager.get("non_existent", default="def", cast=int) == "def"

    # Test TypeError (e.g., passing a list to int) falls back to original value
    manager.load_dict({"list_val": [1, 2]})
    assert manager.get("list_val", cast=int) == [1, 2]


def test_save_without_writable_source_raises():
    manager = ConfigManager()
    manager.set("k", "v")

    with pytest.raises(ValueError):
        manager.save()


def test_save_writes_only_dirty_keys_onto_existing_file(tmp_path):
    defaults_file = tmp_path / "defaults.json"
    defaults_file.write_text(json.dumps({"A": "default_a", "B": "default_b"}))

    user_file = tmp_path / "user.json"
    user_file.write_text(json.dumps({"C": "existing_c"}))

    manager = ConfigManager()
    manager.load_json(str(defaults_file))
    manager.load_json(str(user_file), writable=True)

    manager.set("A", "overridden_a")
    manager.save()

    on_disk = json.loads(user_file.read_text())
    # The pre-existing user override survives...
    assert on_disk["C"] == "existing_c"
    # ...and the new override is added, without leaking the untouched default B.
    assert on_disk["A"] == "overridden_a"
    assert "B" not in on_disk


def test_save_is_noop_when_nothing_dirty(tmp_path):
    user_file = tmp_path / "user.json"
    user_file.write_text(json.dumps({"C": "existing_c"}))

    manager = ConfigManager()
    manager.load_json(str(user_file), writable=True)

    manager.save()

    assert json.loads(user_file.read_text()) == {"C": "existing_c"}


def test_save_creates_missing_writable_file(tmp_path):
    user_file = tmp_path / "nested" / "user.json"

    manager = ConfigManager()
    manager.load_json(str(user_file), writable=True)
    manager.set("A", "a")
    manager.save()

    assert json.loads(user_file.read_text()) == {"A": "a"}


def test_save_clears_dirty_so_second_save_is_noop(tmp_path):
    user_file = tmp_path / "user.json"

    manager = ConfigManager()
    manager.load_json(str(user_file), writable=True)
    manager.set("A", "a")
    manager.save()

    user_file.write_text(json.dumps({"A": "a", "manually_added": "x"}))
    manager.save()  # nothing dirty anymore — must not clobber the manual edit

    assert json.loads(user_file.read_text()) == {"A": "a", "manually_added": "x"}


# ------------------------------------------------------------ EPIC-007B: sources()


def test_sources_labels_each_key_by_the_source_that_won_it(tmp_path, monkeypatch):
    """ "Which layer won" is the question a config panel is opened for --
    get_all() already answers *what* the merged value is, never *why*."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"json_k": "json_v"}))
    monkeypatch.setenv("TEST_ENV_K", "env_v")

    manager = ConfigManager()
    manager.load_dict({"dict_k": "dict_v"})
    manager.load_json(str(config_file))
    manager.load_env("TEST_ENV_")
    manager.get_all()  # forces _load()

    sources = manager.sources()
    assert sources["dict_k"] == "DictSource"
    assert sources["json_k"] == f"json:{config_file}"
    assert sources["K"] == "env:TEST_ENV_"


def test_sources_reflects_override_order_the_same_way_get_all_does():
    """A later source overriding an earlier one's key must report the later
    source's label -- reporting the earlier one would be a lie about which
    value actually won."""
    manager = ConfigManager()
    manager.load_dict({"shared_key": "from_dict"})
    manager.load_json("/nonexistent/does-not-matter.json")  # JsonSource.read() -> {}
    manager.load_dict({"shared_key": "from_second_dict"})

    assert manager.get("shared_key") == "from_second_dict"
    assert manager.sources()["shared_key"] == "DictSource"


def test_set_labels_the_key_as_runtime_not_a_registered_source():
    manager = ConfigManager()
    manager.load_dict({"a": 1})
    manager.set("b", 2)

    sources = manager.sources()
    assert sources["a"] == "DictSource"
    assert sources["b"] == "runtime:set()"


def test_sources_of_an_unloaded_manager_is_empty_not_a_crash():
    manager = ConfigManager()
    assert manager.sources() == {}


def test_dictconfig_inherits_the_empty_default_honestly():
    """DictConfig has no layering concept at all -- {} is the honest answer,
    not a fabricated per-key label."""
    from sagittarius_engine.infrastructure.config.dict_config import DictConfig

    config = DictConfig({"a": 1, "b": 2})
    assert config.sources() == {}
