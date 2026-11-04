"""Historia Pojazdu integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import FetchError, fetch_report
from .const import CONF_FIRST_REGISTRATION, CONF_REGISTRATION, CONF_VIN, DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ['sensor', 'button']
_SAVED = ('insurance', 'inspection', 'last_success', 'odometer', 'odometer_unit', 'odometer_date')


class VehicleCoordinator(DataUpdateCoordinator):
    """Retain verified dates separately from current retrieval status."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=f'{DOMAIN}_{entry.entry_id}',
                         update_interval=timedelta(hours=24))
        self.entry = entry
        self.store = Store(hass, 1, f'{DOMAIN}.{entry.entry_id}')
        self.data = {'insurance': None, 'inspection': None, 'last_success': None,
                     'odometer': None, 'odometer_unit': None, 'odometer_date': None, 'odometer_fresh': False,
                     'insurance_fresh': False, 'inspection_fresh': False,
                     'problem': 'Oczekiwanie na aktualizację'}

    async def restore(self) -> None:
        try:
            saved = await self.store.async_load()
        except (OSError, ValueError):
            self.data['problem'] = 'Nie udało się odczytać zapisanych danych'
            return
        if isinstance(saved, dict):
            for key in ('insurance', 'inspection', 'last_success'):
                if isinstance(saved.get(key), str):
                    self.data[key] = saved[key]
            if (isinstance(saved.get('odometer'), int) and not isinstance(saved.get('odometer'), bool)
                    and saved.get('odometer_unit') in ('km', 'mi') and isinstance(saved.get('odometer_date'), str)):
                for key in ('odometer', 'odometer_unit', 'odometer_date'):
                    self.data[key] = saved[key]
        # Restored values are explicitly marked stale until a successful fetch.

    async def _async_update_data(self):
        result = dict(self.data)
        result.update(insurance_fresh=False, inspection_fresh=False, odometer_fresh=False)
        try:
            insurance, inspection, odometer = await fetch_report(
                self.entry.data[CONF_REGISTRATION], self.entry.data[CONF_VIN],
                self.entry.data[CONF_FIRST_REGISTRATION])
        except FetchError as exc:
            # Keep the last known dates; the failure is reported by the status sensor.
            result['problem'] = str(exc)
            return result
        missing = []
        if odometer is not None:
            value, unit, day = odometer
            result.update(odometer=value, odometer_unit=unit, odometer_date=day.isoformat(), odometer_fresh=True)
        for key, value, label in (('insurance', insurance, 'OC'), ('inspection', inspection, 'badania technicznego')):
            if value is None:
                missing.append(label)
            else:
                result[key] = value.isoformat()
                result[f'{key}_fresh'] = True
        if missing:
            result['problem'] = 'Brak lub niejednoznaczny termin: ' + ', '.join(missing)
        else:
            result['problem'] = None
            result['last_success'] = dt_util.utcnow().isoformat()
        # Persist selected values only, never the report or session tokens.
        if insurance is not None or inspection is not None or odometer is not None:
            try:
                await self.store.async_save({k: result[k] for k in _SAVED})
            except (OSError, ValueError):
                result['problem'] = ((result['problem'] + '; ') if result['problem'] else '') + 'Nie udało się zapisać danych'
        return result


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = VehicleCoordinator(hass, entry)
    await coordinator.restore()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Do not hold HA startup while the remote government service is slow.
    entry.async_create_background_task(hass, coordinator.async_refresh(), 'historia_pojazdu_initial_refresh')
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove only this entry's persisted dates when the user deletes it."""
    await Store(hass, 1, f'{DOMAIN}.{entry.entry_id}').async_remove()
