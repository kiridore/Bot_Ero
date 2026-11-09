from copy import deepcopy

import pytest
import yaml

from core import config
from core.web_panel import _validate_config


@pytest.mark.parametrize('value', [None, 0, 1, 'true', [], False])
def test_bad_section_or_enabled(value):
    data = deepcopy(config._RAW)
    data['blacklist'] = value
    assert any('blacklist' in s for s in config.validate_config(data))
    assert 'blacklist' in _validate_config(yaml.safe_dump(data))
    data['blacklist'] = {'enabled': value}
    if type(value) is not bool:
        assert any('blacklist' in s for s in config.validate_config(data))


def test_enabled_requires_management_defaults_compatible():
    data = deepcopy(config._RAW)
    data.pop('blacklist', None)
    assert config.validate_config(data) == []
    data['blacklist'] = {'enabled': True}
    data['bot']['system_plugins'] = ['menu']
    assert any('blacklist' in s for s in config.validate_config(data))
    data['bot']['system_plugins'].append('blacklist')
    data['bot']['allowed_plugins'] = ['menu', 'blacklist']
    for edition in ('private', 'community'):
        data['bot']['edition'] = edition
        assert config.validate_config(data) == []
    data['bot']['allowed_plugins'] = ['menu']
    assert any('blacklist' in s for s in config.validate_config(data))
