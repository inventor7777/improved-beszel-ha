import re

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.icon import icon_for_battery_level

from .const import DOMAIN, LOGGER

NAMED_TEMPERATURE_SENSOR_ENABLE_THRESHOLD = 3
SMART_ATTRIBUTE_RENAMES = {
    "criticalwarning": "critical_warning",
    "availablespare": "available_spare",
    "availablesparethreshold": "available_spare_threshold",
    "percentageused": "percentage_used",
    "dataunitsread": "data_units_read",
    "dataunitswritten": "data_units_written",
    "hostreads": "host_reads",
    "hostwrites": "host_writes",
    "controllerbusytime": "controller_busy_time",
    "powercycles": "power_cycles",
    "poweronhours": "power_on_hours",
    "unsafeshutdowns": "unsafe_shutdowns",
    "mediaerrors": "media_errors",
    "numerrlogentries": "num_err_log_entries",
    "warningtemptime": "warning_temp_time",
    "criticalcomptime": "critical_comp_time",
}
SMART_COUNT_SENSOR_ALIASES = {
    "reallocated_sectors": ("reallocated_sector_ct", "reallocated_sectors_count"),
    "pending_sectors": ("current_pending_sector", "pending_sector_count"),
    "offline_uncorrectable": ("offline_uncorrectable",),
    "load_cycle_count": ("load_cycle_count",),
    "start_stop_count": ("start_stop_count",),
    "percentage_used": ("percentage_used",),
}


def _format_disk_label(disk_name: str) -> str:
    if disk_name.lower().startswith("nvme"):
        return f"NVMe{disk_name[4:]}"
    return disk_name.upper()


def _normalize_smart_attribute_name(name: str) -> str:
    normalized = name.strip()
    normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", normalized)
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", normalized)
    normalized = (
        normalized.lower()
        .replace(" ", "_")
        .replace(".", "")
        .replace("-", "_")
        .replace("/", "_")
    )
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return SMART_ATTRIBUTE_RENAMES.get(normalized, normalized)


def _single_interface_enabled_default(stats_data: dict) -> bool:
    interfaces = stats_data.get("ni", {})
    return isinstance(interfaces, dict) and len(interfaces) == 1


def _disk_io_mbps(read_value, write_value):
    if read_value is None and write_value is None:
        return None
    return round(((read_value or 0) + (write_value or 0)) / 1_000_000, 3)


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
                # Get stats for this system
                system_stats = stats_data.get(system.id, {})
                system_info = getattr(system, "info", {})
                entities.append(BeszelMemoryUsedSensor(coordinator, system))
                entities.append(BeszelMemoryCacheUsedSensor(coordinator, system))
                if system_stats.get("mz") is not None:
                    entities.append(BeszelMemoryZFSARCUsedSensor(coordinator, system))
                entities.append(BeszelDiskUsedSensor(coordinator, system))

                entities.append(BeszelAggregateDiskIOSensor(coordinator, system, "read"))
                entities.append(BeszelAggregateDiskIOSensor(coordinator, system, "write"))
                entities.append(BeszelAggregateCombinedDiskIOSensor(coordinator, system))
                entities.append(BeszelCombinedDiskIOSensor(coordinator, system))
                entities.append(BeszelDiskIOSensor(coordinator, system, "read"))
                entities.append(BeszelDiskIOSensor(coordinator, system, "write"))
                entities.append(BeszelLoadAverageSensor(coordinator, system, 0, "1m"))
                entities.append(BeszelLoadAverageSensor(coordinator, system, 1, "5m"))
                entities.append(BeszelLoadAverageSensor(coordinator, system, 2, "15m"))
                for cpu_index, _ in enumerate(system_stats.get("cpus", []), start=1):
                    entities.append(BeszelPerCPUSensor(coordinator, system, cpu_index))

                if system_info.get("g") is not None or system_stats.get("g") is not None:
                    entities.append(BeszelGPUSensor(coordinator, system))
                    gpu_stats = system_stats.get("g", {})
                    primary_gpu = gpu_stats.get("i0") if isinstance(gpu_stats, dict) else None
                    if isinstance(primary_gpu, dict):
                        if primary_gpu.get("pp") is not None:
                            entities.append(BeszelGPUPowerSensor(coordinator, system))
                        engines = primary_gpu.get("e", {})
                        if isinstance(engines, dict):
                            for engine_name in ("Render/3D", "Video", "VideoEnhance", "Blitter"):
                                if engine_name in engines:
                                    entities.append(
                                        BeszelGPUEngineSensor(coordinator, system, engine_name)
                                    )

                if isinstance(system_info.get("sv"), list) and len(system_info["sv"]) >= 2:
                    entities.append(BeszelTotalServicesSensor(coordinator, system))
                    entities.append(BeszelFailedServicesSensor(coordinator, system))

                if system_stats.get("s") is not None or system_stats.get("su") is not None:
                    if system_stats.get("s") is not None:
                        entities.append(BeszelSwapSensor(coordinator, system))
                    entities.append(BeszelSwapTotalSensor(coordinator, system))
                    entities.append(BeszelSwapUsedSensor(coordinator, system))

                # Create EFS sensors if EFS data is available
                if system_stats and 'efs' in system_stats and isinstance(system_stats['efs'], dict):
                    for disk_name in system_stats['efs'].keys():
                        entities.append(BeszelEFSDiskSensor(coordinator, system, disk_name))
                        entities.append(BeszelDiskUsedSensor(coordinator, system, disk_name))
                        entities.append(BeszelDiskTotalSensor(coordinator, system, disk_name))
                        entities.append(BeszelCombinedDiskIOSensor(coordinator, system, disk_name))
                        entities.append(BeszelDiskIOSensor(coordinator, system, "read", disk_name))
                        entities.append(BeszelDiskIOSensor(coordinator, system, "write", disk_name))
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
                    for metric_key in SMART_COUNT_SENSOR_ALIASES:
                        if BeszelSmartCountSensor.has_metric(device, metric_key):
                            entities.append(
                                BeszelSmartCountSensor(
                                    coordinator, system, device, metric_key
                                )
                            )

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
    def available(self) -> bool:
        sys = self.system
        return super().available and sys is not None and getattr(sys, "status", None) == "up"

    def _cpu_family_attributes(self):
        attributes = {"cpu_percent": self.system_info.get("cpu")}

        cpub = self.stats_data.get("cpub")
        if isinstance(cpub, list) and len(cpub) >= 5:
            user, system, iowait, steal, idle = cpub[:5]
            other = round(
                max(0, 100 - sum(value for value in (user, system, iowait, steal, idle) if value is not None)),
                2,
            )
            attributes.update(
                {
                    "user_percent": user,
                    "system_percent": system,
                    "iowait_percent": iowait,
                    "steal_percent": steal,
                    "idle_percent": idle,
                    "other_percent": other,
                }
            )

        cpus = self.stats_data.get("cpus")
        if isinstance(cpus, list) and cpus:
            for index, value in enumerate(cpus, start=1):
                attributes[f"cpu_{index}_percent"] = value

        return attributes

    def _ram_family_attributes(self):
        attributes = {
            "ram_percent": self.system_info.get("mp"),
            "total_gib": self.stats_data.get("m"),
            "used_gib": self.stats_data.get("mu"),
            "cache_gib": self.stats_data.get("mb"),
            "zfs_arc_gib": self.stats_data.get("mz"),
        }

        swap_total = self.stats_data.get("s")
        swap_used = self.stats_data.get("su")
        swap_used_effective = 0 if swap_used is None and swap_total is not None else swap_used
        attributes["swap_total_gib"] = swap_total
        attributes["swap_used_gib"] = swap_used_effective
        attributes["swap_percent"] = (
            round((swap_used_effective / swap_total) * 100, 2)
            if swap_total not in (None, 0) and swap_used_effective is not None
            else None
        )
        return attributes

    def _disk_family_attributes(self, disk_name=None):
        if disk_name:
            disk_data = self.stats_data.get("efs", {}).get(disk_name, {})
            if not isinstance(disk_data, dict):
                disk_data = {}
            total = disk_data.get("d")
            used = disk_data.get("du")
            read = disk_data.get("r")
            write = disk_data.get("w")
            percent = (
                round((used / total) * 100, 2)
                if total not in (None, 0) and used is not None
                else None
            )
            io = None if read is None and write is None else round((read or 0) + (write or 0), 3)
            return {
                "disk_percent": percent,
                "total_gib": total,
                "used_gib": used,
                "read_mb_s": read,
                "write_mb_s": write,
                "io_mb_s": io,
            }

        disk_io = self.stats_data.get("dio")
        read_mb_s = None
        write_mb_s = None
        io_mb_s = None
        if isinstance(disk_io, list) and len(disk_io) >= 2:
            read_value = disk_io[0]
            write_value = disk_io[1]
            read_mb_s = round(read_value / 1_000_000, 3) if read_value is not None else None
            write_mb_s = round(write_value / 1_000_000, 3) if write_value is not None else None
            io_mb_s = _disk_io_mbps(read_value, write_value)

        return {
            "disk_percent": self.system_info.get("dp"),
            "total_gib": self.stats_data.get("d"),
            "used_gib": self.stats_data.get("du"),
            "read_mb_s": read_mb_s,
            "write_mb_s": write_mb_s,
            "io_mb_s": io_mb_s,
        }

    def _swap_family_attributes(self):
        swap_total = self.stats_data.get("s")
        swap_used = self.stats_data.get("su")
        swap_used_effective = 0 if swap_used is None and swap_total is not None else swap_used
        return {
            "swap_percent": (
                round((swap_used_effective / swap_total) * 100, 2)
                if swap_total not in (None, 0) and swap_used_effective is not None
                else None
            ),
            "swap_total_gib": swap_total,
            "swap_used_gib": swap_used_effective,
        }

    def _bandwidth_family_attributes(self):
        attributes = {}
        bandwidth = self.stats_data.get("b")
        if isinstance(bandwidth, list) and len(bandwidth) >= 2:
            attributes["tx_mb_s"] = (
                round(bandwidth[0] / 1_000_000, 3) if bandwidth[0] is not None else None
            )
            attributes["rx_mb_s"] = (
                round(bandwidth[1] / 1_000_000, 3) if bandwidth[1] is not None else None
            )

        interfaces = self.stats_data.get("ni", {})
        if isinstance(interfaces, dict) and interfaces:
            attributes["interfaces"] = {
                name: {
                    "bandwidth_rx_mb_s": round(values[1] / 1_000_000, 3)
                    if len(values) > 1 and values[1] is not None
                    else None,
                    "bandwidth_tx_mb_s": round(values[0] / 1_000_000, 3)
                    if len(values) > 0 and values[0] is not None
                    else None,
                    "rx_gib": round(values[3] / 1_000_000_000, 3)
                    if len(values) > 3 and values[3] is not None
                    else None,
                    "tx_gib": round(values[2] / 1_000_000_000, 3)
                    if len(values) > 2 and values[2] is not None
                    else None,
                }
                for name, values in interfaces.items()
                if isinstance(values, list)
            }

        return attributes

    def _gpu_stats(self):
        gpu_stats = self.stats_data.get("g", {})
        if not isinstance(gpu_stats, dict):
            return {}
        primary_gpu = gpu_stats.get("i0")
        return primary_gpu if isinstance(primary_gpu, dict) else {}

    def _gpu_family_attributes(self):
        gpu_stats = self._gpu_stats()
        attributes = {}
        gpu_name = gpu_stats.get("n")
        if gpu_name:
            attributes["gpu_name"] = gpu_name
        usage = gpu_stats.get("u")
        if usage is not None:
            attributes["gpu_percent"] = usage
        power = gpu_stats.get("pp")
        if power is not None:
            attributes["gpu_package_power_w"] = power
        engines = gpu_stats.get("e", {})
        if isinstance(engines, dict):
            engine_map = {
                "Render/3D": "gpu_render_3d_percent",
                "Video": "gpu_video_percent",
                "VideoEnhance": "gpu_video_enhance_percent",
                "Blitter": "gpu_blitter_percent",
            }
            for source_name, attr_name in engine_map.items():
                if source_name in engines:
                    attributes[attr_name] = engines.get(source_name)
        return attributes

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
        if label.lower().startswith("nvme"):
            return f"NVMe{label[4:]}"
        return label.upper()

    @property
    def smart_attribute_map(self):
        attribute_map = {}
        for attribute in self.smart_device_data.get("attributes") or []:
            name = attribute.get("n")
            if not name:
                continue
            normalized = _normalize_smart_attribute_name(name)
            value = attribute.get("rv")
            if value is None and attribute.get("rs") not in (None, ""):
                value = attribute.get("rs")
            attribute_map[normalized] = value
        return attribute_map

    def _smart_family_attributes(self):
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

        for attribute in device_data.get("attributes") or []:
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

    @property
    def extra_state_attributes(self):
        return self._cpu_family_attributes()


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
        gpu_stats = self._gpu_stats()
        if gpu_stats.get("u") is not None:
            return gpu_stats.get("u")
        return self.system_info.get("g") if self.system else None

    @property
    def native_unit_of_measurement(self):
        return PERCENTAGE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def suggested_display_precision(self):
        return 2

    @property
    def extra_state_attributes(self):
        return self._gpu_family_attributes()


class BeszelPerCPUSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, cpu_index):
        super().__init__(coordinator, system)
        self._cpu_index = cpu_index

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_cpu_{self._cpu_index}_v2"

    @property
    def name(self):
        return f"{self.system.name} CPU {self._cpu_index}" if self.system else None

    @property
    def icon(self):
        return "mdi:memory"

    @property
    def native_value(self):
        cpus = self.stats_data.get("cpus")
        if not isinstance(cpus, list) or len(cpus) < self._cpu_index:
            return None
        return cpus[self._cpu_index - 1]

    @property
    def native_unit_of_measurement(self):
        return PERCENTAGE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        return self._cpu_family_attributes()


class BeszelGPUPowerSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_gpu_package_power"

    @property
    def name(self):
        return f"{self.system.name} GPU Package Power" if self.system else None

    @property
    def icon(self):
        return "mdi:expansion-card"

    @property
    def native_value(self):
        return self._gpu_stats().get("pp")

    @property
    def native_unit_of_measurement(self):
        return UnitOfPower.WATT

    @property
    def device_class(self):
        return SensorDeviceClass.POWER

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def suggested_display_precision(self):
        return 2

    @property
    def extra_state_attributes(self):
        return self._gpu_family_attributes()

class BeszelGPUEngineSensor(BeszelBaseSensor):
    ENGINE_LABELS = {
        "Render/3D": "Render/3D",
        "Video": "Video",
        "VideoEnhance": "Video Enhance",
        "Blitter": "Blitter",
    }

    def __init__(self, coordinator, system, engine_name):
        super().__init__(coordinator, system)
        self._engine_name = engine_name

    @property
    def unique_id(self):
        normalized = (
            self._engine_name.lower().replace("/", "_").replace(" ", "_")
        )
        return f"beszel_{self._system_id}_gpu_{normalized}"

    @property
    def name(self):
        label = self.ENGINE_LABELS.get(self._engine_name, self._engine_name)
        return f"{self.system.name} GPU {label}" if self.system else None

    @property
    def icon(self):
        return "mdi:expansion-card"

    @property
    def native_value(self):
        engines = self._gpu_stats().get("e", {})
        if not isinstance(engines, dict):
            return None
        return engines.get(self._engine_name)

    @property
    def native_unit_of_measurement(self):
        return PERCENTAGE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        return self._gpu_family_attributes()

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False


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

    @property
    def extra_state_attributes(self):
        return self._ram_family_attributes()


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

    @property
    def extra_state_attributes(self):
        return self._disk_family_attributes()


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

    @property
    def extra_state_attributes(self):
        return self._bandwidth_family_attributes()


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

    @property
    def extra_state_attributes(self):
        return self._bandwidth_family_attributes()

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

    @property
    def extra_state_attributes(self):
        temperatures = self.stats_data.get("t", {})
        if not isinstance(temperatures, dict) or not temperatures:
            return {}
        return {
            f"{zone_name}_c": value
            for zone_name, value in temperatures.items()
            if value is not None
        }


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
    def extra_state_attributes(self):
        return self._smart_family_attributes()

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

    @property
    def extra_state_attributes(self):
        return self._smart_family_attributes()


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

    @property
    def extra_state_attributes(self):
        return self._smart_family_attributes()


class BeszelSmartCountSensor(BeszelSmartBaseSensor):
    METRIC_NAMES = {
        "reallocated_sectors": "Reallocated Sectors",
        "pending_sectors": "Pending Sectors",
        "offline_uncorrectable": "Offline Uncorrectable",
        "load_cycle_count": "Load Cycle Count",
        "start_stop_count": "Start Stop Count",
        "percentage_used": "Percentage Used",
    }

    def __init__(self, coordinator, system, device_data, metric_key):
        super().__init__(coordinator, system, device_data)
        self._metric_key = metric_key

    @classmethod
    def has_metric(cls, device_data, metric_key):
        aliases = SMART_COUNT_SENSOR_ALIASES.get(metric_key, ())
        for attribute in device_data.get("attributes") or []:
            name = attribute.get("n")
            if not name:
                continue
            if _normalize_smart_attribute_name(name) in aliases:
                return True
        return False

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_{self._disk_name}_smart_{self._metric_key}_v2"

    @property
    def name(self):
        return (
            f"{self.system.name} {self.smart_device_label} S.M.A.R.T. {self.METRIC_NAMES[self._metric_key]}"
            if self.system
            else None
        )

    @property
    def icon(self):
        if self._metric_key in {"load_cycle_count", "start_stop_count"}:
            return "mdi:harddisk-plus"
        if self._metric_key == "percentage_used":
            return "mdi:harddisk"
        return "mdi:harddisk-remove"

    @property
    def native_value(self):
        for alias in SMART_COUNT_SENSOR_ALIASES[self._metric_key]:
            value = self.smart_attribute_map.get(alias)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return value
        return None

    @property
    def native_unit_of_measurement(self):
        if self._metric_key == "percentage_used":
            return PERCENTAGE
        return None

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False

    @property
    def extra_state_attributes(self):
        return self._smart_family_attributes()


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
    def extra_state_attributes(self):
        return self._bandwidth_family_attributes()

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

    @property
    def extra_state_attributes(self):
        return self._ram_family_attributes()


class BeszelMemoryCacheUsedSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_memory_cache_used"

    @property
    def name(self):
        return f"{self.system.name} RAM Cache Used" if self.system else None

    @property
    def icon(self):
        return "mdi:memory"

    @property
    def native_value(self):
        return self.stats_data.get("mb")

    @property
    def native_unit_of_measurement(self):
        return UnitOfInformation.GIBIBYTES

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False

    @property
    def extra_state_attributes(self):
        return self._ram_family_attributes()


class BeszelMemoryZFSARCUsedSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_memory_zfs_arc_used"

    @property
    def name(self):
        return f"{self.system.name} RAM ZFS ARC Used" if self.system else None

    @property
    def icon(self):
        return "mdi:chip"

    @property
    def native_value(self):
        return self.stats_data.get("mz")

    @property
    def native_unit_of_measurement(self):
        return UnitOfInformation.GIBIBYTES

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        return self._ram_family_attributes()


class BeszelTotalServicesSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_total_services"

    @property
    def name(self):
        return f"{self.system.name} Total Services" if self.system else None

    @property
    def icon(self):
        return "mdi:check-circle"

    @property
    def native_value(self):
        services = self.system_info.get("sv")
        return services[0] if isinstance(services, list) and len(services) >= 1 else None

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC


class BeszelFailedServicesSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_failed_services"

    @property
    def name(self):
        return f"{self.system.name} Failed Services" if self.system else None

    @property
    def icon(self):
        return "mdi:alert-circle"

    @property
    def native_value(self):
        services = self.system_info.get("sv")
        return services[1] if isinstance(services, list) and len(services) >= 2 else None

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC


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
            label = _format_disk_label(self._disk_name)
            return f"{self.system.name} {label} Used"
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

    @property
    def extra_state_attributes(self):
        return self._disk_family_attributes(self._disk_name)


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

    @property
    def extra_state_attributes(self):
        return self._swap_family_attributes()


class BeszelSwapSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_swap"

    @property
    def name(self):
        return f"{self.system.name} Swap" if self.system else None

    @property
    def icon(self):
        return "mdi:swap-horizontal"

    @property
    def native_value(self):
        swap_total = self.stats_data.get("s")
        if swap_total is None or swap_total <= 0:
            return None

        swap_used = self.stats_data.get("su")
        if swap_used is None:
            swap_used = 0

        return round((swap_used / swap_total) * 100, 2)

    @property
    def native_unit_of_measurement(self):
        return PERCENTAGE

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def extra_state_attributes(self):
        return self._swap_family_attributes()


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

    @property
    def extra_state_attributes(self):
        return self._swap_family_attributes()


class BeszelDiskIOSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, direction, disk_name=None):
        super().__init__(coordinator, system)
        self._direction = direction
        self._disk_name = disk_name

    @property
    def unique_id(self):
        if self._disk_name:
            return f"beszel_{self._system_id}_{self._disk_name}_{self._direction}_v2"
        return f"beszel_{self._system_id}_disk_{self._direction}_v2"

    @property
    def name(self):
        if not self.system:
            return None
        action = "IO Read" if self._direction == "read" else "IO Write"
        if self._disk_name:
            return f"{self.system.name} {_format_disk_label(self._disk_name)} {action}"
        return f"{self.system.name} Disk {action}"

    @property
    def icon(self):
        if self._direction == "read":
            return "mdi:database-arrow-down"
        return "mdi:database-arrow-up"

    @property
    def native_value(self):
        if self._disk_name:
            disk_data = self.stats_data.get("efs", {}).get(self._disk_name, {})
            if isinstance(disk_data, dict):
                key = "r" if self._direction == "read" else "w"
                return disk_data.get(key)
            return None

        disk_io = self.stats_data.get("dio")
        if not isinstance(disk_io, list) or len(disk_io) < 2:
            return None

        value = disk_io[0] if self._direction == "read" else disk_io[1]
        return value / 1_000_000 if value is not None else None

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
        return 3

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False

    @property
    def extra_state_attributes(self):
        return self._disk_family_attributes(self._disk_name)


class BeszelAggregateDiskIOSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, direction):
        super().__init__(coordinator, system)
        self._direction = direction

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_aggregate_{self._direction}s_v2"

    @property
    def name(self):
        if not self.system:
            return None
        action = "IO Reads" if self._direction == "read" else "IO Writes"
        return f"{self.system.name} {action}"

    @property
    def icon(self):
        if self._direction == "read":
            return "mdi:database-arrow-down"
        return "mdi:database-arrow-up"

    @property
    def native_value(self):
        disk_io = self.stats_data.get("dio")
        if not isinstance(disk_io, list) or len(disk_io) < 2:
            return None
        value = disk_io[0] if self._direction == "read" else disk_io[1]
        return value / 1_000_000 if value is not None else None

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
        return 3

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False

    @property
    def extra_state_attributes(self):
        return self._disk_family_attributes()


class BeszelCombinedDiskIOSensor(BeszelBaseSensor):
    def __init__(self, coordinator, system, disk_name=None):
        super().__init__(coordinator, system)
        self._disk_name = disk_name

    @property
    def unique_id(self):
        if self._disk_name:
            return f"beszel_{self._system_id}_{self._disk_name}_io_v2"
        return f"beszel_{self._system_id}_disk_io_v2"

    @property
    def name(self):
        if not self.system:
            return None
        if self._disk_name:
            return f"{self.system.name} {_format_disk_label(self._disk_name)} IO"
        return f"{self.system.name} Disk IO"

    @property
    def icon(self):
        return "mdi:database-sync"

    @property
    def native_value(self):
        if self._disk_name:
            disk_data = self.stats_data.get("efs", {}).get(self._disk_name, {})
            if not isinstance(disk_data, dict):
                return None
            read_value = disk_data.get("r")
            write_value = disk_data.get("w")
            if read_value is None and write_value is None:
                return None
            return (read_value or 0) + (write_value or 0)

        disk_io = self.stats_data.get("dio")
        if not isinstance(disk_io, list) or len(disk_io) < 2:
            return None
        read_value = disk_io[0]
        write_value = disk_io[1]
        if read_value is None and write_value is None:
            return None
        return ((read_value or 0) + (write_value or 0)) / 1_000_000

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
        return 3

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False

    @property
    def extra_state_attributes(self):
        return self._disk_family_attributes(self._disk_name)


class BeszelAggregateCombinedDiskIOSensor(BeszelBaseSensor):
    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_io_v2"

    @property
    def name(self):
        return f"{self.system.name} IO" if self.system else None

    @property
    def icon(self):
        return "mdi:database-sync"

    @property
    def native_value(self):
        disk_io = self.stats_data.get("dio")
        if not isinstance(disk_io, list) or len(disk_io) < 2:
            return None
        read_value = disk_io[0]
        write_value = disk_io[1]
        if read_value is None and write_value is None:
            return None
        return ((read_value or 0) + (write_value or 0)) / 1_000_000

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
        return 3

    @property
    def entity_registry_enabled_default(self) -> bool:
        return False

    @property
    def extra_state_attributes(self):
        return self._disk_family_attributes()


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
        bytes_total = interface_data[3] if self._direction == "rx" else interface_data[2]
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
        return _single_interface_enabled_default(self.stats_data)

    @property
    def extra_state_attributes(self):
        return self._bandwidth_family_attributes()


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
        rate = interface_data[1] if self._direction == "rx" else interface_data[0]
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
        return _single_interface_enabled_default(self.stats_data)

    @property
    def extra_state_attributes(self):
        return self._bandwidth_family_attributes()


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
        if not self.system:
            return None
        label = _format_disk_label(self._disk_name)
        return f"{self.system.name} {label}"

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
        return self._disk_family_attributes(self._disk_name)



class BeszelBatterySensor(BeszelBaseSensor):
    @property
    def battery_data(self):
        battery = self.stats_data.get("bat")
        return battery if isinstance(battery, list) and len(battery) >= 2 else None

    @property
    def unique_id(self):
        return f"beszel_{self._system_id}_battery"

    @property
    def name(self):
        return f"{self.system.name} Battery" if self.system else None

    @property
    def icon(self):
        battery = self.battery_data
        if battery is None:
            return "mdi:battery-unknown"
        level, state = battery
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
        battery = self.battery_data
        if battery is None:
            return None
        return battery[0]

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

    @property
    def extra_state_attributes(self):
        return self._ram_family_attributes()


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
            label = _format_disk_label(self._disk_name)
            return f"{self.system.name} {label} Total"
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

    @property
    def extra_state_attributes(self):
        return self._disk_family_attributes(self._disk_name)
