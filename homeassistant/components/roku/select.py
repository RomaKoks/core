"""Support for Roku selects."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from rokuecp import Roku
from rokuecp.models import Device as RokuDevice

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import roku_exception_handler
from .const import DOMAIN
from .coordinator import RokuDataUpdateCoordinator
from .entity import RokuEntity


@dataclass
class RokuSelectEntityDescriptionMixin:
    """Mixin for required keys."""

    options_fn: Callable[[RokuDevice], list[str]]
    value_fn: Callable[[RokuDevice], str | None]
    set_fn: Callable[[RokuDevice, Roku, str], Awaitable[None]]


def _get_application_name(device: RokuDevice) -> str | None:
    if device.app is None or device.app.name is None:
        return None

    if device.app.name == "Roku":
        return "Home"

    return device.app.name


def _get_applications(device: RokuDevice) -> list[str]:
    return ["Home"] + sorted(app.name for app in device.apps if app.name is not None)


async def _launch_application(device: RokuDevice, roku: Roku, value: str) -> None:
    if value == "Home":
        await roku.remote("home")

    appl = next(
        (app for app in device.apps if value == app.name),
        None,
    )

    if appl is not None and appl.app_id is not None:
        await roku.launch(appl.app_id)


@dataclass
class RokuSelectEntityDescription(
    SelectEntityDescription, RokuSelectEntityDescriptionMixin
):
    """Describes Roku select entity."""


ENTITIES: tuple[RokuSelectEntityDescription, ...] = (
    RokuSelectEntityDescription(
        key="application",
        name="Application",
        icon="mdi:application",
        set_fn=_launch_application,
        value_fn=_get_application_name,
        options_fn=_get_applications,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roku select based on a config entry."""
    coordinator: RokuDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    unique_id = coordinator.data.info.serial_number
    async_add_entities(
        RokuSelectEntity(
            device_id=unique_id,
            coordinator=coordinator,
            description=description,
        )
        for description in ENTITIES
    )


class RokuSelectEntity(RokuEntity, SelectEntity):
    """Defines a Roku select entity."""

    entity_description: RokuSelectEntityDescription

    @property
    def current_option(self) -> str | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return self.entity_description.options_fn(self.coordinator.data)

    @roku_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        await self.entity_description.set_fn(
            self.coordinator.data,
            self.coordinator.roku,
            option,
        )
        await self.coordinator.async_request_refresh()
