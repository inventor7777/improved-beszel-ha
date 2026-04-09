from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.icon import icon_for_battery_level

from .const import DOMAIN, LOGGER

NAMED_TEMPERATURE_SENSOR_ENABLE_THRESHOLD = 4

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    entities = []

    try:
        # Get systems and stats from coordinator data
        systems = coordinator.data['systems']
        stats_data = coordinator.data.get('stats', {})
        smart_devices_data = coordinator.data.get("smart_devices", {})

        for system in systems:
            try:
                entities.append(BeszelCPUSensor(coordinator, system))
                entities.append(BeszelRAMSensor(coordinator, system))
                entities.append(BeszelRAMTotalSensor(coordinator, system))
                entities.append(BeszelDiskSensor(coordinator, system))
                entities.append(BeszelDiskTotalSensor(coordinator, system))
                entities.append(BeszelBandwidthSensor(coordinator, system))
                entities.append(BeszelNetworkReceiveSensor(coordinator, system))
                entities.append(BeszelNetworkSendSensor(coordinator, system))
                entities.append(BeszelTemperatureSensor(coordinator, system))
                entities.append(BeszelUptimeSensor(coordinator, system))
                entities.append(BeszelGPUSensor(coordinator, system))
                entities.append(BeszelMemoryUsedSensor(coordinator, system))
                entities.append(BeszelDiskUsedSensor(coordinator, system))
                entities.append(BeszelLoadAverageSensor(coordinator, system, 0, "1m"))
                entities.append(BeszelLoadAverageSensor(coordinator, system, 1, "5m"))
                entities.append(BeszelLoadAverageSensor(coordinator, system, 2, "15m"))

                # Get stats for this system
                system_stats = stats_data.get(system.id, {})

                if system_stats.get("s") is not None or system_stats.get("su") is not None:
                    entities.append(BeszelSwapTotalSensor(coordinator, system))
                    entities.append(BeszelSwapUsedSensor(coordinator, system))

                # Create EFS sensors if EFS data is available
                if system_stats and 'efs' in system_stats and isinstance(system_stats['efs'], dict):
                    for disk_name in system_stats['efs'].keys():
                        entities.append(BeszelEFSDiskSensor(coordinator, system, disk_name))
                        entities.append(BeszelDiskUsedSensor(coordinator, system, disk_name))
                        entities.append(BeszelDiskTotalSensor(coordinator, system, disk_name))
                        LOGGER.info(f"Created EFS sensors for {system.name} - {disk_name}")

                # Create battery sensor if data is available
                if system_stats and 'bat' in system_stats and isinstance(system_stats['bat'], list):
                    entities.append(BeszelBatterySensor(coordinator, system))

                for device in smart_devices_data.get(system.id, []):
                    temp = device.get("temp")
                    if temp not in (None, 0):
                        entities.append(BeszelSmartTemperatureSensor(coordinator, system, device))
                    if device.get("hours") is not None:
                        entities.append(BeszelSmartPowerOnHoursSensor(coordinator, system, device))
                        entities.append(BeszelSmartPowerOnDaysSensor(coordinator, system, device))

                for temp_name in system_stats.get("t", {}):
                    entities.append(BeszelNamedTemperatureSensor(coordinator, system, temp_name))

                for interface_name in system_stats.get("ni", {}):
                    entities.append(
                        BeszelInterfaceBandwidthSensor(
                            coordinator, system, interface_name, "rx"
                        )
                    )
                    entities.append(
                        BeszelInterfaceBandwidthSensor(
                            coordinator, system, interface_name, "tx"
                        )
                    )
                    entities.append(
                        BeszelInterfaceCounterSensor(
                            coordinator, system, interface_name, "rx"
                        )
                    )
                    entities.append(
                        BeszelInterfaceCounterSensor(
                            coordinator, system, interface_name, "tx"
                        )
                    )

            except Exception as e:
                LOGGER.error(f"Failed to create sensors for system {system.name if hasattr(system, 'name') else 'unknown'}: {e}")
                continue

        LOGGER.info(f"Created {len(entities)} sensors total")
        async_add_entities(entities)
    except Exception as e:
        LOGGER.error(f"Failed to setup sensors: {e}")
        raise

class BeszelBaseSensor(CoordinatorEntity, SensorEntity):
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
    def stats_data(self):
        return self.coordinator.data.get('stats', {}).get(self._system_id, {})

    @property
    def system_info(self):
        sys = self.system
        return getattr(sys, "info", {}) if sys else {}

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
class BeszelSmartBaseSensor(BeszelBaseSensor):
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
    def smart_device_label(self):
        label = self._disk_name or "disk"
        return label.lower()

class BeszelCPUSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_cpu"

    @property
    def name(self):
        return f"{self.system.name} CPU" if self.system else None

    @property
    def icon(self):
        return "mdi:memory"

    @property
    def native_value(self):
        return self.system_info.get("cpu")

    @property
    def native_unit_of_measurement(self):
        return PERCENTAGE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


class BeszelGPUSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_gpu"

    @property
    def name(self):
        return f"{self.system.name} GPU" if self.system else None

    @property
    def icon(self):
        return "mdi:expansion-card"

    @property
    def native_value(self):
        return self.system_info.get("g", 0.0) if self.system else None

    @property
    def native_unit_of_measurement(self):
        return PERCENTAGE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


class BeszelRAMSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_ram"

    @property
    def name(self):
        return f"{self.system.name} RAM" if self.system else None

    @property
    def icon(self):
        return "mdi:chip"

    @property
    def native_value(self):
        return self.system_info.get("mp")

    @property
    def native_unit_of_measurement(self):
        return PERCENTAGE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


class BeszelDiskSensor(BeszelBaseSensor):

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_disk"

    @property
    def name(self):
        return f"{self.system.name} Disk" if self.system else None

    @property
    def icon(self):
        return "mdi:harddisk"

    @property
    def native_value(self):
        return self.system_info.get("dp")

    @property
    def native_unit_of_measurement(self):
        return PERCENTAGE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


class BeszelBandwidthSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_bandwidth"

    @property
    def name(self):
        return f"{self.system.name} Bandwidth" if self.system else None

    @property
    def icon(self):
        return "mdi:network"

    @property
    def native_value(self):
        bandwidth = self.system_info.get("bb")
        return bandwidth / 1_000_000 if bandwidth is not None else None

    @property
    def native_unit_of_measurement(self):
        return UnitOfDataRate.MEGABYTES_PER_SECOND

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_RATE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT
    
    @property
    def suggested_display_precision(self):
        return 2


class BeszelNetworkReceiveSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_network_receive"

    @property
    def name(self):
        return f"{self.system.name} Bandwidth RX" if self.system else None

    @property
    def icon(self):
        return "mdi:download-network"

    @property
    def native_value(self):
        bandwidth = self.stats_data.get("b")
        return bandwidth[1] / 1_000_000 if bandwidth and len(bandwidth) > 1 else None

    @property
    def native_unit_of_measurement(self):
        return UnitOfDataRate.MEGABYTES_PER_SECOND

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_RATE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT
        
    @property
    def suggested_display_precision(self):
        return 2
        
class BeszelNetworkSendSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_network_send"

    @property
    def name(self):
        return f"{self.system.name} Bandwidth TX" if self.system else None

    @property
    def icon(self):
        return "mdi:upload-network"

    @property
    def native_value(self):
        bandwidth = self.stats_data.get("b")
        return bandwidth[0] / 1_000_000 if bandwidth and len(bandwidth) > 0 else None

    @property
    def native_unit_of_measurement(self):
        return UnitOfDataRate.MEGABYTES_PER_SECOND

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_RATE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def suggested_display_precision(self):
        return 2


class BeszelTemperatureSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_temperature"

    @property
    def name(self):
        return f"{self.system.name} temperature" if self.system else None

    @property
    def native_value(self):
        return self.system_info.get("dt")

    @property
    def device_class(self):
        return SensorDeviceClass.TEMPERATURE

    @property
    def native_unit_of_measurement(self):
        return UnitOfTemperature.CELSIUS

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


class BeszelSmartTemperatureSensor(BeszelSmartBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_{self._disk_name}_smart_temperature_v2"

    @property
    def name(self):
        return (
            f"{self.system.name} {self.smart_device_label} S.M.A.R.T. Temperature"
            if self.system
            else None
        )

    @property
    def icon(self):
        return "mdi:thermometer-lines"

    @property
    def native_value(self):
        return self.smart_device_data.get("temp")

    @property
    def device_class(self):
        return SensorDeviceClass.TEMPERATURE

    @property
    def native_unit_of_measurement(self):
        return UnitOfTemperature.CELSIUS

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC


class BeszelSmartPowerOnHoursSensor(BeszelSmartBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_{self._disk_name}_smart_power_on_hours_v2"

    @property
    def name(self):
        return (
            f"{self.system.name} {self.smart_device_label} S.M.A.R.T. Power On Time"
            if self.system
            else None
        )

    @property
    def native_value(self):
        return self.smart_device_data.get("hours")

    @property
    def native_unit_of_measurement(self):
        return UnitOfTime.HOURS

    @property
    def device_class(self):
        return SensorDeviceClass.DURATION

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    @property
    def entity_registry_enabled_default(self) -> bool:
        smart_device_count = len(
            self.coordinator.data.get("smart_devices", {}).get(self._system_id, [])
        )
        return smart_device_count <= 2


class BeszelSmartPowerOnDaysSensor(BeszelSmartBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_{self._disk_name}_smart_power_on_days_v2"

    @property
    def name(self):
        return (
            f"{self.system.name} {self.smart_device_label} S.M.A.R.T. Power On Days"
            if self.system
            else None
        )

    @property
    def native_value(self):
        hours = self.smart_device_data.get("hours")
        return round(hours / 24, 1) if hours is not None else None

    @property
    def native_unit_of_measurement(self):
        return UnitOfTime.DAYS

    @property
    def device_class(self):
        return SensorDeviceClass.DURATION

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False


class BeszelNamedTemperatureSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, temperature_name):
        super().__init__(coordinator, system)
        self._temperature_name = temperature_name

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_temperature_{self._temperature_name}_v2"

    @property
    def name(self):
        return (
            f"{self.system.name} {self._temperature_name.lower()} Temperature"
            if self.system
            else None
        )

    @property
    def icon(self):
        return "mdi:thermometer-plus"

    @property
    def native_value(self):
        temperatures = self.stats_data.get("t", {})
        return temperatures.get(self._temperature_name)

    @property
    def device_class(self):
        return SensorDeviceClass.TEMPERATURE

    @property
    def native_unit_of_measurement(self):
        return UnitOfTemperature.CELSIUS

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def entity_registry_enabled_default(self) -> bool:
        temperature_count = len(self.stats_data.get("t", {}))
        return temperature_count <= NAMED_TEMPERATURE_SENSOR_ENABLE_THRESHOLD


class BeszelLoadAverageSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, index, label):
        super().__init__(coordinator, system)
        self._index = index
        self._label = label

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_load_average_{self._label}"

    @property
    def name(self):
        return f"{self.system.name} Load Average {self._label}" if self.system else None

    @property
    def icon(self):
        return "mdi:chart-line"

    @property
    def native_value(self):
        load_avg = self.stats_data.get("la") or self.system_info.get("la")
        if load_avg and len(load_avg) > self._index:
            return load_avg[self._index]
        return None

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def suggested_display_precision(self):
        return 2

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False


class BeszelMemoryUsedSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_memory_used"

    @property
    def name(self):
        return f"{self.system.name} RAM Used" if self.system else None

    @property
    def icon(self):
        return "mdi:chip"

    @property
    def native_value(self):
        return self.stats_data.get("mu")

    @property
    def native_unit_of_measurement(self):
        return UnitOfInformation.GIBIBYTES

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


class BeszelDiskUsedSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, disk_name=None):
        super().__init__(coordinator, system)
        self._disk_name = disk_name

    @property
    def unique_id(self):
        if self._disk_name:
            return f"beszel_{self._system_id}_{self._disk_name}_used_v2"
        return f"beszel_{self._system_id}_disk_used"

    @property
    def name(self):
        if not self.system:
            return None
        if self._disk_name:
            return f"{self.system.name} {self._disk_name.lower()} Used"
        return f"{self.system.name} Disk Used"

    @property
    def icon(self):
        if self._disk_name:
            return "mdi:harddisk-plus"
        return "mdi:harddisk"

    @property
    def native_value(self):
        if self._disk_name:
            disk_data = self.stats_data.get("efs", {}).get(self._disk_name, {})
            if isinstance(disk_data, dict):
                return disk_data.get("du")
            return None
        return self.stats_data.get("du")

    @property
    def native_unit_of_measurement(self):
        return UnitOfInformation.GIBIBYTES

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


class BeszelSwapTotalSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_swap_total"

    @property
    def name(self):
        return f"{self.system.name} Swap Total" if self.system else None

    @property
    def icon(self):
        return "mdi:swap-horizontal"

    @property
    def native_value(self):
        return self.stats_data.get("s")

    @property
    def native_unit_of_measurement(self):
        return UnitOfInformation.GIBIBYTES

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


class BeszelSwapUsedSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_swap_used"

    @property
    def name(self):
        return f"{self.system.name} Swap Used" if self.system else None

    @property
    def icon(self):
        return "mdi:swap-horizontal"

    @property
    def native_value(self):
        swap_used = self.stats_data.get("su")
        if swap_used is not None:
            return swap_used
        if self.stats_data.get("s") is not None:
            return 0
        return None

    @property
    def native_unit_of_measurement(self):
        return UnitOfInformation.GIBIBYTES

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


class BeszelInterfaceCounterSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, interface_name, direction):
        super().__init__(coordinator, system)
        self._interface_name = interface_name
        self._direction = direction

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_{self._interface_name}_{self._direction}_bytes_v2"

    @property
    def name(self):
        label = "RX" if self._direction == "rx" else "TX"
        return (
            f"{self.system.name} {self._interface_name.lower()} {label}"
            if self.system
            else None
        )

    @property
    def icon(self):
        return "mdi:download-network" if self._direction == "rx" else "mdi:upload-network"

    @property
    def native_value(self):
        interface_data = self.stats_data.get("ni", {}).get(self._interface_name)
        if not interface_data or len(interface_data) < 4:
            return None
        bytes_total = interface_data[2] if self._direction == "rx" else interface_data[3]
        return bytes_total / 1_000_000_000

    @property
    def native_unit_of_measurement(self):
        return UnitOfInformation.GIBIBYTES

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def state_class(self):
        return SensorStateClass.TOTAL_INCREASING

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False


class BeszelInterfaceBandwidthSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, interface_name, direction):
        super().__init__(coordinator, system)
        self._interface_name = interface_name
        self._direction = direction

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_{self._interface_name}_{self._direction}_bandwidth_v2"

    @property
    def name(self):
        label = "Bandwidth RX" if self._direction == "rx" else "Bandwidth TX"
        return (
            f"{self.system.name} {self._interface_name.lower()} {label}"
            if self.system
            else None
        )

    @property
    def icon(self):
        return "mdi:download-network" if self._direction == "rx" else "mdi:upload-network"

    @property
    def native_value(self):
        interface_data = self.stats_data.get("ni", {}).get(self._interface_name)
        if not interface_data or len(interface_data) < 2:
            return None
        rate = interface_data[0] if self._direction == "rx" else interface_data[1]
        return rate / 1_000_000

    @property
    def native_unit_of_measurement(self):
        return UnitOfDataRate.MEGABYTES_PER_SECOND

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_RATE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def suggested_display_precision(self):
        return 2

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False


class BeszelUptimeSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_uptime"

    @property
    def name(self):
        return f"{self.system.name} uptime" if self.system else None

    @property
    def icon(self):
        return "mdi:sort-clock-descending"

    @property
    def native_value(self):
        uptime = self.system_info.get("u")
        return uptime / 86400 if uptime is not None else None

    @property
    def suggested_display_precision(self):
        return 2

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self):
        return UnitOfTime.DAYS

    @property
    def device_class(self):
        return SensorDeviceClass.DURATION

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

class BeszelEFSDiskSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, disk_name):
        super().__init__(coordinator, system)
        self._disk_name = disk_name

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_{self._disk_name}_v2"

    @property
    def name(self):
        return f"{self.system.name} {self._disk_name.lower()}" if self.system else None

    @property
    def icon(self):
        return "mdi:harddisk-plus"

    @property
    def native_value(self):
        if not self.stats_data:
            return None

        efs_data = self.stats_data.get('efs', {})
        disk_data = efs_data.get(self._disk_name, {})

        total_space = disk_data.get('d')
        used_space = disk_data.get('du')

        # Calculate disk usage percentage
        if total_space is not None and used_space is not None and total_space > 0:
            return round((used_space / total_space) * 100, 2)
        return None

    @property
    def native_unit_of_measurement(self):
        return PERCENTAGE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        """Return additional state attributes for the EFS disk."""
        if not self.stats_data:
            return {}

        efs_data = self.stats_data.get('efs', {})
        disk_data = efs_data.get(self._disk_name, {})

        return {
            "total_disk_space_gib": disk_data.get('d'),
            "disk_used_gib": disk_data.get('du'),
            "read_mb_s": disk_data.get('r'),
            "write_mb_s": disk_data.get('w'),
        }



class BeszelBatterySensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_battery"

    @property
    def name(self):
        return f"{self.system.name} Battery" if self.system else None

    @property
    def icon(self):
        if not self.stats_data and "bat" not in self.stats_data:
            return "mdi:battery-unknown"
        level, state = self.stats_data.get("bat")
        # https://github.com/henrygd/beszel/blob/4d05bfdff0ec90b68e820ad5dc32a5c4bccf8f0f/internal/site/src/lib/enums.ts#L41-L48
        charging = state == 3

        return icon_for_battery_level(level, charging)

    @property
    def device_class(self):
        return SensorDeviceClass.BATTERY

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if not self.stats_data:
            return None
        return self.stats_data.get("bat")[0]

    @property
    def native_unit_of_measurement(self):
        return PERCENTAGE


class BeszelRAMTotalSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_ram_total"

    @property
    def name(self):
        return f"{self.system.name} RAM Total" if self.system else None

    @property
    def icon(self):
        return "mdi:chip"

    @property
    def native_value(self):
        if not self.stats_data:
            return None
        return self.stats_data.get("m")

    @property
    def native_unit_of_measurement(self):
        return UnitOfInformation.GIBIBYTES

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT


class BeszelDiskTotalSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, disk_name=None):
        super().__init__(coordinator, system)
        self._disk_name = disk_name

    @property
    def unique_id(self):
        if self._disk_name:
            return f"beszel_{self._system_id}_{self._disk_name}_total_v2"
        return f"beszel_{self._system_id}_disk_total"

    @property
    def name(self):
        if not self.system:
            return None
        if self._disk_name:
            return f"{self.system.name} {self._disk_name.lower()} Total"
        return f"{self.system.name} Disk Total"

    @property
    def icon(self):
        if self._disk_name:
            return "mdi:harddisk-plus"
        return "mdi:harddisk"

    @property
    def native_value(self):
        if not self.stats_data:
            return None

        if self._disk_name:
            disk_data = self.stats_data.get("efs", {}).get(self._disk_name, {})
            if isinstance(disk_data, dict):
                return disk_data.get("d")
            return None

        return self.stats_data.get("d")

    @property
    def native_unit_of_measurement(self):
        return UnitOfInformation.GIBIBYTES

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT
