"""Minimal Home Assistant boundary stubs, so the logic can be tested without installing HA.

Behaviour inside a running Home Assistant still has to be checked there.
"""
import importlib.util
import pathlib
import sys
import types
from datetime import date, datetime, timezone

BASE = pathlib.Path(__file__).parents[1] / 'custom_components/historia_pojazdu'
PACKAGE = 'custom_components.historia_pojazdu'


def _module(name):
    return sys.modules.setdefault(name, types.ModuleType(name))


def install():
    for name in ('homeassistant', 'homeassistant.config_entries', 'homeassistant.core', 'homeassistant.const',
                 'homeassistant.helpers', 'homeassistant.helpers.storage', 'homeassistant.helpers.update_coordinator',
                 'homeassistant.helpers.selector',
                 'homeassistant.util', 'homeassistant.util.dt', 'voluptuous'):
        _module(name)
    ce = sys.modules['homeassistant.config_entries']
    ce.ConfigEntry = object

    class ConfigFlow:
        def __init_subclass__(cls, **kwargs):
            pass
    ce.ConfigFlow = ConfigFlow
    sys.modules['homeassistant.core'].HomeAssistant = object
    sys.modules['homeassistant.const'].CONF_NAME = 'name'
    dt = sys.modules['homeassistant.util.dt']
    dt.utcnow = lambda: datetime(2026, 10, 30, tzinfo=timezone.utc)
    dt.now = lambda: datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
    sys.modules['homeassistant.util'].dt = dt

    class Coordinator:
        def __init__(self, hass, logger, **kwargs):
            self.hass = hass
            self.kwargs = kwargs
    sys.modules['homeassistant.helpers.update_coordinator'].DataUpdateCoordinator = Coordinator

    class Store:
        contents = {}
        def __init__(self, hass, version, key): self.key = key
        async def async_load(self): return self.contents.get(self.key)
        async def async_save(self, value): self.contents[self.key] = dict(value)
    sys.modules['homeassistant.helpers.storage'].Store = Store
    sel = sys.modules['homeassistant.helpers.selector']
    for name in ('TextSelector', 'TextSelectorConfig'):
        setattr(sel, name, lambda *a, **k: None)
    vol = sys.modules['voluptuous']
    vol.UNDEFINED = object()
    vol.Required = lambda key, **kw: key
    vol.Schema = dict


def load(module='__init__'):
    """Import the integration package (and optionally a submodule) against the stubs."""
    install()
    if PACKAGE not in sys.modules:
        _module('custom_components')
        spec = importlib.util.spec_from_file_location(PACKAGE, BASE / '__init__.py', submodule_search_locations=[str(BASE)])
        pkg = importlib.util.module_from_spec(spec)
        sys.modules[PACKAGE] = pkg
        spec.loader.exec_module(pkg)
    if module == '__init__':
        return sys.modules[PACKAGE]
    return importlib.import_module(f'{PACKAGE}.{module}')


__all__ = ['install', 'load', 'date']
