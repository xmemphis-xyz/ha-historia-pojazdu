"""Date, odometer and status sensors."""
from __future__ import annotations

from datetime import date, datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory

from .entity import VehicleEntity

DESCRIPTIONS = (
    SensorEntityDescription(key='insurance', translation_key='insurance', device_class=SensorDeviceClass.DATE),
    SensorEntityDescription(key='inspection', translation_key='inspection', device_class=SensorDeviceClass.DATE),
    SensorEntityDescription(key='odometer', translation_key='odometer', device_class=SensorDeviceClass.DISTANCE,
                            state_class=SensorStateClass.TOTAL_INCREASING, suggested_display_precision=0),
    SensorEntityDescription(key='last_success', translation_key='last_success', device_class=SensorDeviceClass.TIMESTAMP,
                            entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key='status', translation_key='status', entity_category=EntityCategory.DIAGNOSTIC),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(VehicleSensor(coordinator, entry, description) for description in DESCRIPTIONS)


def _freshness(fresh: bool) -> str:
    return 'aktualne' if fresh else 'zapisane lub nieaktualne'


class VehicleSensor(VehicleEntity, SensorEntity):

    def __init__(self, coordinator, entry, description: SensorEntityDescription) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        key = self.entity_description.key
        data = self.coordinator.data
        if key == 'status':
            return data['problem'] or 'Aktualne'
        if key == 'odometer':
            return data.get('odometer')
        value = data.get(key)
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value) if key == 'last_success' else date.fromisoformat(value)
        except (TypeError, ValueError):
            return None

    @property
    def native_unit_of_measurement(self):
        if self.entity_description.key == 'odometer':
            return self.coordinator.data.get('odometer_unit')
        return None

    @property
    def extra_state_attributes(self):
        key = self.entity_description.key
        data = self.coordinator.data
        if key == 'odometer':
            return {'data_odczytu': data.get('odometer_date'), 'aktualnosc': _freshness(data.get('odometer_fresh'))}
        if key in ('insurance', 'inspection'):
            return {'aktualnosc': _freshness(data.get(f'{key}_fresh'))}
        return None
