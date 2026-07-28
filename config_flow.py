"""Config flow for BYD China."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .pybyd_china.client import BydClient
from .pybyd_china.config import BydConfig, DeviceProfile
from .pybyd_china.exceptions import (
    BydApiError,
    BydAuthenticationError,
    BydDecryptionError,
    BydTransportError,
)

from .const import (
    CONF_BASE_URL,
    CONF_CONTROL_PIN,
    CONF_COUNTRY_CODE,
    CONF_DEBUG_DUMPS,
    CONF_DEVICE_PROFILE,
    CONF_GPS_POLL_INTERVAL,
    CONF_LANGUAGE,
    CONF_POLL_INTERVAL,
    CONF_TARGET_BRAND,
    COUNTRY_OPTIONS,
    DEFAULT_BASE_URL,
    DEFAULT_COUNTRY_CODE,
    DEFAULT_DEBUG_DUMPS,
    DEFAULT_GPS_POLL_INTERVAL,
    DEFAULT_LANGUAGE,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_TARGET_BRAND,
    DOMAIN,
    BRAND_OPTIONS,
    get_country_connection_settings,
)
from .device_fingerprint import async_generate_device_profile

_LOGGER = logging.getLogger(__name__)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    session = async_get_clientsession(hass)
    country_code, language, base_url = get_country_connection_settings("China")
    time_zone = hass.config.time_zone or "UTC"
    target_brand = data.get(CONF_TARGET_BRAND, DEFAULT_TARGET_BRAND)

    device_profile_dict = data.get(CONF_DEVICE_PROFILE)
    if device_profile_dict:
        device_profile = DeviceProfile(**device_profile_dict)
    else:
        device_profile = DeviceProfile()

    config = BydConfig(
        username=data["username"],
        password=data["password"],
        base_url=base_url,
        country_code=country_code,
        language=language,
        time_zone=time_zone,
        target_brand=target_brand,
    )
    async with BydClient(config, device_profile, session=session) as client:
        await client.login()
        vehicles = await client.get_vehicles()


class BydVehicleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BYD China."""

    VERSION = 5

    _reauth_entry: config_entries.ConfigEntry | None = None

    def _build_user_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = defaults or {}

        return vol.Schema(
            {
                vol.Required("username", default=defaults.get("username", "")): str,
                vol.Required("password", default=defaults.get("password", "")): str,
                vol.Required(
                    CONF_CONTROL_PIN,
                    default=defaults.get(CONF_CONTROL_PIN, ""),
                ): str,
                vol.Required(
                    CONF_TARGET_BRAND,
                    default=defaults.get(CONF_TARGET_BRAND, DEFAULT_TARGET_BRAND),
                ): vol.In(BRAND_OPTIONS),
                vol.Optional(
                    CONF_DEBUG_DUMPS,
                    default=defaults.get(
                        CONF_DEBUG_DUMPS,
                        DEFAULT_DEBUG_DUMPS,
                    ),
                ): bool,
            }
        )

    def _reauth_defaults(self) -> dict[str, Any]:
        if self._reauth_entry is None:
            return {}

        options = self._reauth_entry.options
        return {
            "username": self._reauth_entry.data.get("username", ""),
            "password": self._reauth_entry.data.get("password", ""),
            CONF_CONTROL_PIN: self._reauth_entry.data.get(CONF_CONTROL_PIN, ""),
            CONF_TARGET_BRAND: self._reauth_entry.data.get(
                CONF_TARGET_BRAND, DEFAULT_TARGET_BRAND
            ),
            CONF_DEBUG_DUMPS: options.get(
                CONF_DEBUG_DUMPS,
                DEFAULT_DEBUG_DUMPS,
            ),
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user step of the config flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            pin_value = user_input.get(CONF_CONTROL_PIN, "")
            if not pin_value or not pin_value.isdigit() or len(pin_value) != 6:
                errors["base"] = "invalid_pin_format"
            else:
                try:
                    device_profile = await async_generate_device_profile(self.hass)
                    user_input[CONF_DEVICE_PROFILE] = device_profile
                    await _validate_input(self.hass, user_input)
                except BydAuthenticationError:
                    _LOGGER.warning("Authentication failed - check username/password")
                    errors["base"] = "invalid_auth"
                except BydDecryptionError as exc:
                    _LOGGER.warning("Decryption error during validation: %s", exc)
                    errors["base"] = "decryption_error"
                except BydApiError as exc:
                    code = getattr(exc, 'code', '')
                    _LOGGER.warning("BYD API error during validation: code=%s %s", code, exc)
                    if code in ('1001', '1002', '1003'):
                        errors["base"] = "invalid_auth"
                    elif code == '1004':
                        errors["base"] = "account_locked"
                    else:
                        errors["base"] = "cannot_connect"
                except BydTransportError as exc:
                    _LOGGER.warning("Network error during validation: %s", exc)
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error during validation")
                    errors["base"] = "unknown"
                else:
                    country_code, language, base_url = get_country_connection_settings("China")
                    await self.async_set_unique_id(f"{user_input['username']}@{base_url}")
                    if self._reauth_entry is None:
                        self._abort_if_unique_id_configured()
                    else:
                        self._abort_if_unique_id_mismatch(reason="wrong_account")

                        existing_device_profile = self._reauth_entry.data.get(
                            CONF_DEVICE_PROFILE
                        )
                        if existing_device_profile is None:
                            existing_device_profile = await async_generate_device_profile(
                                self.hass
                            )
                        updated_data = {
                            **self._reauth_entry.data,
                            "username": user_input["username"],
                            "password": user_input["password"],
                            CONF_CONTROL_PIN: user_input.get(CONF_CONTROL_PIN, ""),
                            CONF_BASE_URL: base_url,
                            CONF_COUNTRY_CODE: country_code,
                            CONF_LANGUAGE: language,
                            CONF_TARGET_BRAND: user_input.get(CONF_TARGET_BRAND, DEFAULT_TARGET_BRAND),
                            CONF_DEVICE_PROFILE: existing_device_profile,
                        }
                        updated_options = {
                            **self._reauth_entry.options,
                            CONF_DEBUG_DUMPS: user_input[CONF_DEBUG_DUMPS],
                        }

                        self.hass.config_entries.async_update_entry(
                            self._reauth_entry,
                            data=updated_data,
                            options=updated_options,
                        )
                        await self.hass.config_entries.async_reload(
                            self._reauth_entry.entry_id
                        )
                        return self.async_abort(reason="reauth_successful")

                    return self.async_create_entry(
                        title=user_input["username"],
                        data={
                            "username": user_input["username"],
                            "password": user_input["password"],
                            CONF_CONTROL_PIN: user_input.get(CONF_CONTROL_PIN, ""),
                            CONF_BASE_URL: base_url,
                            CONF_COUNTRY_CODE: country_code,
                            CONF_LANGUAGE: language,
                            CONF_TARGET_BRAND: user_input.get(CONF_TARGET_BRAND, DEFAULT_TARGET_BRAND),
                            CONF_DEVICE_PROFILE: await async_generate_device_profile(
                                self.hass
                            ),
                        },
                        options={
                            CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
                            CONF_GPS_POLL_INTERVAL: DEFAULT_GPS_POLL_INTERVAL,
                            CONF_DEBUG_DUMPS: user_input[CONF_DEBUG_DUMPS],
                        },
                    )

        data_schema = self._build_user_schema(self._reauth_defaults())

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_reauth(
        self, _: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle re-authentication flow."""
        self._reauth_entry = self._get_reauth_entry()
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                device_profile = reconfigure_entry.data.get(CONF_DEVICE_PROFILE)
                if device_profile:
                    user_input[CONF_DEVICE_PROFILE] = device_profile
                await _validate_input(self.hass, user_input)
            except BydAuthenticationError:
                _LOGGER.warning("Authentication failed during reconfigure")
                errors["base"] = "invalid_auth"
            except BydDecryptionError as exc:
                _LOGGER.warning("Decryption error during reconfigure: %s", exc)
                errors["base"] = "decryption_error"
            except BydApiError as exc:
                code = getattr(exc, 'code', '')
                _LOGGER.warning("BYD API error during reconfigure: code=%s %s", code, exc)
                if code in ('1001', '1002', '1003'):
                    errors["base"] = "invalid_auth"
                elif code == '1004':
                    errors["base"] = "account_locked"
                else:
                    errors["base"] = "cannot_connect"
            except BydTransportError as exc:
                _LOGGER.warning("Network error during reconfigure: %s", exc)
                _LOGGER.warning("BYD API error during reconfigure: %s", exc)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during reconfigure")
                errors["base"] = "unknown"
            else:
                country_code, language, base_url = get_country_connection_settings("China")
                existing_device_profile = reconfigure_entry.data.get(
                    CONF_DEVICE_PROFILE
                )
                if existing_device_profile is None:
                    existing_device_profile = await async_generate_device_profile(
                        self.hass
                    )

                updated_data = {
                    **reconfigure_entry.data,
                    "username": user_input["username"],
                    "password": user_input["password"],
                    CONF_CONTROL_PIN: user_input.get(CONF_CONTROL_PIN, ""),
                    CONF_BASE_URL: base_url,
                    CONF_COUNTRY_CODE: country_code,
                    CONF_LANGUAGE: language,
                    CONF_TARGET_BRAND: user_input.get(CONF_TARGET_BRAND, DEFAULT_TARGET_BRAND),
                    CONF_DEVICE_PROFILE: existing_device_profile,
                }
                updated_options = {
                    **reconfigure_entry.options,
                    CONF_DEBUG_DUMPS: user_input[CONF_DEBUG_DUMPS],
                }

                self.hass.config_entries.async_update_entry(
                    reconfigure_entry,
                    data=updated_data,
                    options=updated_options,
                )
                await self.hass.config_entries.async_reload(reconfigure_entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        defaults = {
            "username": reconfigure_entry.data.get("username", ""),
            "password": reconfigure_entry.data.get("password", ""),
            CONF_CONTROL_PIN: reconfigure_entry.data.get(CONF_CONTROL_PIN, ""),
            CONF_TARGET_BRAND: reconfigure_entry.data.get(
                CONF_TARGET_BRAND, DEFAULT_TARGET_BRAND
            ),
            CONF_DEBUG_DUMPS: reconfigure_entry.options.get(
                CONF_DEBUG_DUMPS,
                DEFAULT_DEBUG_DUMPS,
            ),
        }
        data_schema = self._build_user_schema(defaults)

        return self.async_show_form(
            step_id="reconfigure", data_schema=data_schema, errors=errors
        )
