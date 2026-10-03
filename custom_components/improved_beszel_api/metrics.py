"""Small conversions for Beszel's compact stats payload."""


def disk_total_gib(stats, direction):
    totals = stats.get("diot")
    if not isinstance(totals, list) or len(totals) < 2:
        return None
    value = totals[0 if direction == "read" else 1]
    return value / (1024**3) if isinstance(value, (int, float)) else None


def pool_usage_percent(stats, name):
    pool = (stats.get("z") or {}).get(name, {})
    if not isinstance(pool, dict):
        return None
    size, used = pool.get("d"), pool.get("du")
    return (
        round(used / size * 100, 2)
        if isinstance(size, (int, float)) and size > 0 and isinstance(used, (int, float))
        else None
    )


def pool_io_mbps(stats, name, direction):
    pool = (stats.get("z") or {}).get(name)
    if not isinstance(pool, dict):
        return None
    value = pool.get("rb" if direction == "read" else "wb")
    return value / 1_000_000 if isinstance(value, (int, float)) else None


def pool_attributes(data, system_id, name):
    pool = (data.get("stats", {}).get(system_id, {}).get("z") or {}).get(name)
    if not isinstance(pool, dict):
        return {}
    attributes = {
        "health": pool.get("h"),
        "total_gib": pool.get("d"),
        "used_gib": pool.get("du"),
        "raw_capacity": pool.get("raw"),
    }
    scrub = data.get("zfs_pools", {}).get((system_id, name))
    if isinstance(scrub, dict):
        attributes["scrub_state"] = scrub.get("state")
        attributes["scrub_errors"] = scrub.get("errors", 0)
        if scrub.get("progress"):
            attributes["scrub_progress"] = scrub["progress"]
    return attributes


def container_updates_by_system(records):
    updates = {}
    for record in records:
        if hasattr(record, "updatable") and getattr(record, "system", None):
            names = updates.setdefault(record.system, [])
            if record.updatable:
                names.append(record.name)
    return updates


def monitor_response_ms(value):
    return round(value / 1000, 3) if isinstance(value, (int, float)) and value > 0 else None


def monitor_loss_percent(monitor):
    loss = monitor.get("loss1h")
    return loss if (monitor.get("res") or loss) and isinstance(loss, (int, float)) else None


def wifi_interface(info, name):
    interfaces = info.get("wf")
    value = interfaces.get(name) if isinstance(interfaces, dict) else None
    return value if isinstance(value, dict) else {}


def package_update_count(info, index):
    counts = info.get("pu")
    if not isinstance(counts, list) or len(counts) <= index:
        return None
    value = counts[index]
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
