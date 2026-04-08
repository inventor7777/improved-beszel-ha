# Installation
As this repository is not yet added in the default HACS repository you have to add the repository beforehand.

1. Go to the HACS Tab
2. Click on the three dot menu in the top right and select Custom repositories
3. Add `https://github.com/inventor7777/improved-beszel-ha`
4. Restart HomeAssistant
5. Go to integrations, press Add integration and search for `Improved Beszel API`
6. In the Setup Dialog use the following values
    - *URL*: The root url / IP of your Beszel instance, like http://beszel.example.com or https://beszel.example.com
    - *user*: Either your default admin username / email or (recommended) create another user with the role user and assigning the agents you want to expose to it.
    - *password*: The password to the user
7. Improved Beszel API will pull the data and reload every 2 minutes

Currently all machines are added, selection will be added later (you can change this yourself by creating a new user in Beszel's PocketBase and adding this user only to the machines you want to be monitored).

# Usage
After installing the following entities will exposed as sensors (more to come):
- Status (Connection)
- Uptime (Hours)
- CPU (Percentage)
- Disk usage (Percentage)
- Temperature (°C)
- Bandwidth (Mbit/s)
- RAM (Percentage)
- Battery (Percentage)

For example if your machine is named *test*, CPU will be available as ```sensor.test_cpu```
