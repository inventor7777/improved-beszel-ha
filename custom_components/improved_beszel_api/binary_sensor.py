from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, LOGGER


def _normalize_smart_attribute_name(name: str) -> str:
    return (
        name.strip()
        .lower()
        .replace(" ", "_")
        .replace(".", "")
        .replace("-", "_")
        .replace("/", "_")
    )


def _format_smart_device_label(disk_name: str) -> str:
    label = disk_name or "disk"
    return label.lower()


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    entities = []

    try:
        systems = coordinator.data["systems"]
        smart_devices = coordinator.data.get("smart_devices", {})

        for system in systems:
            entities.append(BeszelStatusBinarySensor(coordinator, system))
            for device in smart_devices.get(system.id, []):
                entities.append(BeszelSmartBinarySensor(coordinator, system, device))

        async_add_entities(entities)
    except Exception as e:
        LOGGER.error(f"Failed to setup binary sensors: {e}")
        raise


class BeszelBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, system):
        super().__init__(coordinator)
        self._system_id = system.id

    @property
    def system(self):
        systems = self.coordinator.data['systems']
        for s in systems:
            if s.id == self._system_id:
                return s
        return None

    @property
    def device_info(self):
        sys = self.system
        if sys is None:
            return None
        info = getattr(sys, "info", {})
        return {
            "identifiers": {(DOMAIN, sys.id)},
            "name": sys.name,
            "manufacturer": "Beszel",
            "model": info.get("m"),
            "sw_version": info.get("v"),
            "hw_version": info.get("k"),
        }


class BeszelStatusBinarySensor(BeszelBaseBinarySensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_status"

    @property
    def name(self):
        return f"{self.system.name} Status" if self.system else None

    @property
    def is_on(self):
        return self.system.status == "up" if self.system else False

    @property
    def device_class(self):
        return BinarySensorDeviceClass.CONNECTIVITY

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC


class BeszelSmartBinarySensor(BeszelBaseBinarySensor):
    def __init__(self, coordinator, system, device_data):
        super().__init__(coordinator, system)
        self._device_id = device_data.get("id", "")
        self._device_name = device_data.get("name", "")
        self._disk_name = self._device_name.replace("/dev/", "")

    @property
    def smart_device_data(self):
        for device in self.coordinator.data.get("smart_devices", {}).get(self._system_id, []):
            if device.get("id") == self._device_id:
                return device
        return {}

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_{self._disk_name}_smart_v2"

    @property
    def name(self):
        label = _format_smart_device_label(self._disk_name)
        return f"{self.system.name} {label} S.M.A.R.T." if self.system else None

    @property
    def is_on(self):
        device_data = self.smart_device_data
        if not device_data:
            return None
        return device_data.get("state") != "PASSED"

    @property
    def device_class(self):
        return BinarySensorDeviceClass.PROBLEM

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    @property
    def icon(self):
        device_data = self.smart_device_data
        disk_type = (device_data.get("type") or "").lower()
        if self.is_on:
            return "mdi:harddisk-remove"
        if "nvme" in self._disk_name.lower() or disk_type == "nvme":
            return "mdi:expansion-card"
        return "mdi:harddisk"

    @property
    def extra_state_attributes(self):
        device_data = self.smart_device_data
        if not device_data:
            return {}

        attributes = {"device": self._device_name, "health_state": device_data.get("state", "")}

        temp = device_data.get("temp")
        if temp is not None:
            attributes["temperature_c"] = temp

        capacity = device_data.get("capacity", 0)
        if capacity:
            attributes["capacity_gib"] = round(capacity / (1024**3), 2)
            attributes["capacity_tib"] = round(capacity / (1024**4), 2)

        hours = device_data.get("hours")
        if hours is not None:
            attributes["power_on_hours"] = hours
            attributes["power_on_days"] = round(hours / 24, 1)

        cycles = device_data.get("cycles")
        if cycles is not None:
            attributes["power_cycles"] = cycles

        for key in ("model", "serial", "firmware", "type"):
            value = device_data.get(key)
            if value:
                attributes[key] = value

        raw_attributes = device_data.get("attributes") or []
        if raw_attributes:
            attributes["smart_attributes"] = raw_attributes

        for attribute in raw_attributes:
            name = attribute.get("n")
            if not name:
                continue
            normalized = _normalize_smart_attribute_name(name)
            if "rs" in attribute and attribute.get("rs") not in (None, ""):
                attributes[f"smart_{normalized}"] = attribute.get("rs")
            elif "rv" in attribute:
                attributes[f"smart_{normalized}"] = attribute.get("rv")

            raw_value = attribute.get("rv")
            if raw_value is not None:
                attributes[f"smart_{normalized}_raw"] = raw_value

        return attributes
