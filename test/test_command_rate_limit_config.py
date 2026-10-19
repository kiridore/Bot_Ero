from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from core import config
from core.web_panel import _validate_config


@pytest.mark.parametrize('value', [-1, True, False, '20', 1.5, None])
def test_invalid_limit_shared_validation(value):
    data = deepcopy(config._RAW)
    data.setdefault('community', {})['command_limit_per_minute'] = value
    assert any('command_limit_per_minute' in e for e in config.validate_config(data))
    assert 'command_limit_per_minute' in _validate_config(yaml.safe_dump(data))


def test_menu_help_tracks_limit(monkeypatch):
    from plugins.menu.entries import render_menu
    monkeypatch.setattr(config, 'COMMAND_LIMIT_PER_MINUTE', 20)
    assert '每60秒最多20次指令' in render_menu({'menu': True}, False, False)
    monkeypatch.setattr(config, 'COMMAND_LIMIT_PER_MINUTE', 0)
    assert '每60秒最多' not in render_menu({'menu': True}, False, False)


def test_default_templates_edition_and_old_cooldown(tmp_path):
    data = deepcopy(config._RAW)
    data.setdefault('community', {}).pop('command_limit_per_minute', None)
    data['community']['cmd_cooldown_seconds'] = 3
    for label in ('private', 'community', 'test'):
        data['bot']['edition'] = label
        for value in (None, 0, 20):
            if value is not None:
                data['community']['command_limit_per_minute'] = value
            else:
                data['community'].pop('command_limit_per_minute', None)
            assert config.validate_config(data) == []
            path = tmp_path / 'config.yaml'
            path.write_text(yaml.safe_dump(data), encoding='utf-8')
            loaded = config._load(path)
            assert loaded['community'].get('command_limit_per_minute', 0) == (value or 0)
            assert loaded['community']['cmd_cooldown_seconds'] == 3
    assert yaml.safe_load(Path('config.public.example.yaml').read_text(encoding='utf-8'))['community']['command_limit_per_minute'] == 20
    assert yaml.safe_load(Path('config.example.yaml').read_text(encoding='utf-8'))['community']['command_limit_per_minute'] == 0
