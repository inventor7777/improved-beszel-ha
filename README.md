# Improved Beszel API

Improved Beszel API is a Home Assistant custom integration for [Beszel](https://www.beszel.dev/).

This project is a maintained fork of the original [`Ronjar/beszel-ha`](https://github.com/Ronjar/beszel-ha). The original integration great but this fork exists to keep development moving, merge fixes faster, and expose more of the useful data already available in the Beszel backend.

## Disclaimer

- This is a fork, not the original upstream integration. Credit goes fully to @Ronjar for creation and initial development.
- All development after the original fork was dome by GPT 5.4 Codex under close supervision and testing.
- It is intended to work with normal Beszel / Beszel Hub.
- The Home Assistant integration name is `Improved Beszel API`.
- The custom component domain/install path is `improved_beszel_api`.

## What It Does

The integration connects to Beszel Hub through its PocketBase-backed API and creates Home Assistant entities for your monitored systems.

It currently exposes:

- System connectivity / status
- CPU usage
- RAM usage percent
- RAM total
- RAM used
- Disk usage percent
- Disk total
- Disk used
- Additional disk usage / used / total sensors for extra disks reported by Beszel, such as `SDA`, `SDA Used`, and `SDA Total`
- Uptime
- Main system temperature
- Additional named temperatures from Beszel when available
- Aggregate bandwidth
- Bandwidth RX / TX rate
- Per-interface bandwidth RX / TX rate
- Per-interface RX/TX byte counters
- Swap total / used when the system reports swap
- GPU usage when reported by Beszel
- Battery when reported by Beszel
- Beszel Hub update status
- S.M.A.R.T. disk health entities and attributes
- S.M.A.R.T. temperature / power-on-hours sensors

Some noisier or less universally useful entities are disabled by default, such as:

- Load average sensors
- Named temperature sensors when a system reports more than 4 named temperature zones
- Per-interface bandwidth and byte-counter sensors
- S.M.A.R.T. diagnostic sensors when a system has more disks

## Installation

Because this repository is not part of the default HACS lists, add it as a custom repository first.

1. Open HACS.
2. Open the menu in the top right and select `Custom repositories`.
3. Add `https://github.com/inventor7777/improved-beszel-ha`.
4. Select category `Integration`.
5. Restart Home Assistant if needed.
6. Install `Improved Beszel API` from HACS.
7. Add the integration from the Home Assistant integrations page.

## Setup

When adding the integration, use:

- `URL`: The root URL / IP of your Beszel Hub, for example `http://beszel.example.com` or `https://beszel.example.com`
- `Username`: Your Beszel user email/username
- `Password`: Your Beszel password
- `Verify SSL`: Whether to verify the Beszel SSL certificate
- `Check for updates`: Enables the Beszel Hub update entity

Improved Beszel API polls Beszel every 2 minutes by default.

## Notes

- Right now the integration adds all systems visible to the configured Beszel user.
- If you want to limit which systems show up in Home Assistant, the easiest approach is to create a Beszel user that only has access to the systems you want exposed.
- Beszel Hub branding and product references remain Beszel/Beszel Hub; `Improved Beszel API` is the name of this integration project.

## Entity Naming

Entities follow your Beszel system names. For example, if your system is named `test`, CPU usage will show up as something like `sensor.test_cpu`.

S.M.A.R.T. entities use disk-oriented names such as:

- `test SDA S.M.A.R.T.`
- `test SDA S.M.A.R.T. Temperature`
- `test NVMe0 S.M.A.R.T. Power On Hours`

Additional non-primary disks reported by Beszel follow the same disk-first pattern, for example:

- `test SDA`
- `test SDA Used`
- `test SDA Total`

Per-interface network entities follow the interface name and direction, for example:

- `test enp0s31f6 Bandwidth RX`
- `test enp0s31f6 Bandwidth TX`
- `test enp0s31f6 RX`
- `test enp0s31f6 TX`

## Licensing

This project remains MIT-licensed and preserves attribution to the original project while adding attribution for this fork.
