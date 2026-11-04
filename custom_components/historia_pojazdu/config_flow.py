"""Configuration from the Home Assistant UI."""
from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig
from homeassistant.util import dt as dt_util

from .api import FetchError, VehicleRejected, fetch_report
from .const import CONF_FIRST_REGISTRATION, CONF_REGISTRATION, CONF_VIN, DOMAIN


def _parse_date(raw: Any) -> date | None:
    """Accept DD.MM.RRRR (as on the registration card) or RRRR-MM-DD."""
    text = str(raw or '').strip()
    for parse in (date.fromisoformat, lambda s: date(*reversed([int(p) for p in s.split('.')]))):
        try:
            value = parse(text)
        except (ValueError, TypeError):
            continue
        return value
    return None


def _normalize(user_input: dict) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    name = str(user_input.get(CONF_NAME, '')).strip()
    registration = re.sub(r'\s+', '', str(user_input.get(CONF_REGISTRATION, ''))).upper()
    vin = re.sub(r'\s+', '', str(user_input.get(CONF_VIN, ''))).upper()
    first_date = _parse_date(user_input.get(CONF_FIRST_REGISTRATION))
    if not name:
        errors[CONF_NAME] = 'invalid_name'
    if not re.fullmatch(r'[A-Z0-9]{2,10}', registration):
        errors[CONF_REGISTRATION] = 'invalid_registration'
    if not re.fullmatch(r'[A-HJ-NPR-Z0-9]{17}', vin):
        errors[CONF_VIN] = 'invalid_vin'
    if first_date is None or first_date > dt_util.now().date() or first_date.year < 1900:
        errors[CONF_FIRST_REGISTRATION] = 'invalid_date'
    data = {CONF_NAME: name, CONF_REGISTRATION: registration, CONF_VIN: vin,
            CONF_FIRST_REGISTRATION: first_date.isoformat() if first_date else ''}
    return data, errors


def _schema(defaults: dict, include_vin: bool = True) -> vol.Schema:
    fields = {
        vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, vol.UNDEFINED)): TextSelector(),
        vol.Required(CONF_REGISTRATION, default=defaults.get(CONF_REGISTRATION, vol.UNDEFINED)): TextSelector(),
    }
    if include_vin:
        fields[vol.Required(CONF_VIN, default=defaults.get(CONF_VIN, vol.UNDEFINED))] = TextSelector(
            TextSelectorConfig(autocomplete='off'))
    stored = _parse_date(defaults.get(CONF_FIRST_REGISTRATION))
    fields[vol.Required(CONF_FIRST_REGISTRATION, default=stored.strftime('%d.%m.%Y') if stored else vol.UNDEFINED)] = \
        TextSelector(TextSelectorConfig(autocomplete='off'))
    return vol.Schema(fields)


class HistoriaPojazduConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, data: dict, errors: dict) -> None:
        """Check the data with the service so typos surface in the form, not in a sensor."""
        try:
            await fetch_report(data[CONF_REGISTRATION], data[CONF_VIN], data[CONF_FIRST_REGISTRATION])
        except VehicleRejected:
            errors['base'] = 'vehicle_rejected'
        except FetchError:
            errors['base'] = 'cannot_connect'

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _normalize(user_input)
            if not errors:
                # VIN only: a vehicle keeps its VIN when it gets new plates.
                await self.async_set_unique_id(hashlib.sha256(data[CONF_VIN].encode()).hexdigest())
                self._abort_if_unique_id_configured()
                await self._validate(data, errors)
            if not errors:
                return self.async_create_entry(title=data[CONF_NAME], data=data)
        return self.async_show_form(step_id='user', data_schema=self.add_suggested_values_to_schema(
            _schema({}), user_input or {}), errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        """Change name, plates or first registration date; the VIN identifies the vehicle."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _normalize({**user_input, CONF_VIN: entry.data[CONF_VIN]})
            if not errors:
                await self._validate(data, errors)
            if not errors:
                return self.async_update_reload_and_abort(entry, title=data[CONF_NAME], data=data)
        return self.async_show_form(step_id='reconfigure', data_schema=_schema(entry.data, include_vin=False),
                                    errors=errors)
