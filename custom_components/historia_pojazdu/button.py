"""Manual refresh button."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .entity import VehicleEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([RefreshButton(entry.runtime_data, entry, 'refresh')])


class RefreshButton(VehicleEntity, ButtonEntity):
    _attr_translation_key = 'refresh'

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
