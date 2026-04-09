import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from pocketbase.client import ClientResponseError

from .api import BeszelApiClient
from .const import DOMAIN, CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_VERIFY_SSL, CONF_UPDATE_CHECK


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/").lower()


async def _validate_input(hass: HomeAssistant, data: dict) -> dict:
    client = BeszelApiClient(
        data[CONF_URL],
        data.get(CONF_USERNAME),
        data.get(CONF_PASSWORD),
        data.get(CONF_VERIFY_SSL, True),
    )

    try:
        systems = await hass.async_add_executor_job(client.get_systems)
    except ClientResponseError as err:
        status = getattr(err, "status", None) or getattr(err, "status_code", None)
        if status in (400, 401, 403):
            raise InvalidAuth from err
        raise CannotConnect from err
    except Exception as err:
        raise CannotConnect from err

    return {
        "title": "Improved Beszel API",
        "systems": len(systems or []),
    }

class BeszelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            normalized_url = _normalize_url(user_input[CONF_URL])
            user_input = {**user_input, CONF_URL: normalized_url}

            await self.async_set_unique_id(normalized_url)
            self._abort_if_unique_id_configured()

            try:
                info = await _validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_URL): str,
                vol.Optional(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Optional(CONF_VERIFY_SSL, default=True): bool,
                vol.Optional(CONF_UPDATE_CHECK, default=False): bool,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BeszelOptionsFlow(config_entry)


class BeszelOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        super().__init__()
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            normalized_url = _normalize_url(user_input[CONF_URL])
            user_input = {**user_input, CONF_URL: normalized_url}

            try:
                await _validate_input(self.hass, user_input)
            except CannotConnect:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._build_schema(user_input),
                    errors={"base": "cannot_connect"},
                )
            except InvalidAuth:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._build_schema(user_input),
                    errors={"base": "invalid_auth"},
                )
            except Exception:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._build_schema(user_input),
                    errors={"base": "unknown"},
                )

            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data={**self._config_entry.data, **user_input},
                unique_id=normalized_url,
            )
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=self._build_schema(self._config_entry.data),
        )

    def _build_schema(self, data):
        return vol.Schema({
            vol.Required(
                CONF_URL,
                default=data.get(CONF_URL)
            ): str,
            vol.Optional(
                CONF_USERNAME,
                default=data.get(CONF_USERNAME)
            ): str,
            vol.Optional(
                CONF_PASSWORD,
                default=data.get(CONF_PASSWORD)
            ): str,
            vol.Optional(
                CONF_UPDATE_CHECK,
                default=data.get(CONF_UPDATE_CHECK, False)
            ): bool,
            vol.Optional(
                CONF_VERIFY_SSL,
                default=data.get(CONF_VERIFY_SSL, True)
            ): bool,
        })


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
