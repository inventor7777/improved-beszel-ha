"""S.M.A.R.T. device naming helpers."""

import re


_SAFE_DEVICE_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,98}[A-Za-z0-9])?$")


def smart_device_key(name: str, device_id: str) -> str:
    """Keep ordinary disk names; use the PocketBase record ID for unsafe ones."""
    disk_name = name.replace("/dev/", "")
    if _SAFE_DEVICE_NAME.fullmatch(disk_name):
        return disk_name
    return device_id or "disk"
