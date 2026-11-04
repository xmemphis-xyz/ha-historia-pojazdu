"""Shared entity base."""
from __future__ import annotations

from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class VehicleEntity(CoordinatorEntity):
    """One device per configured vehicle."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f'{entry.entry_id}_{key}'
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            manufacturer='Historia Pojazdu',
            entry_type=DeviceEntryType.SERVICE,
            configuration_url='https://historiapojazdu.gov.pl/',
        )
