"""Support for interfacing with NAD receivers"""

from __future__ import annotations

from . import NADReceiver, NADReceiverTCP, NADReceiverTelnet
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.helpers import config_validation as cv, entity_platform, service
from homeassistant.helpers.entity_component import EntityComponent
#from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DOMAIN = "nadt765"

ZONE2_MUTE = 4194304
ZONE2_ON = 8388608
ZONE2_OFF = 16777216
ZONE2_VOLUME_SET = 33554432
ZONE3_MUTE = 67108864
ZONE3_ON = 134217728
ZONE3_OFF = 268435456
ZONE3_VOLUME_SET = 536870912

DEFAULT_TYPE = "RS232"
DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"
DEFAULT_PORT = 53
DEFAULT_NAME = "NAD Receiver"
DEFAULT_MIN_VOLUME = -92
DEFAULT_MAX_VOLUME = -20
DEFAULT_VOLUME_STEP = 4

SUPPORT_NAD = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | ZONE2_MUTE
    | ZONE2_ON
    | ZONE2_OFF
    | ZONE2_VOLUME_SET
    | ZONE3_MUTE
    | ZONE3_ON
    | ZONE3_OFF
    | ZONE3_VOLUME_SET
)

CONF_SERIAL_PORT = "serial_port"  # for NADReceiver
CONF_MIN_VOLUME = "min_volume"
CONF_MAX_VOLUME = "max_volume"
CONF_VOLUME_STEP = "volume_step"  # for NADReceiverTCP
CONF_SOURCE_DICT = "sources"  # for NADReceiver
CONF_UNIQUE_ID = "unique_id"

# Max value based on a C658 with an MDC HDM-2 card installed
SOURCE_DICT_SCHEMA = vol.Schema({vol.Range(min=1, max=12): cv.string})

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_TYPE, default=DEFAULT_TYPE): vol.In(
            ["RS232", "Telnet", "TCP"]
        ),
        vol.Optional(CONF_SERIAL_PORT, default=DEFAULT_SERIAL_PORT): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MIN_VOLUME, default=DEFAULT_MIN_VOLUME): int,
        vol.Optional(CONF_MAX_VOLUME, default=DEFAULT_MAX_VOLUME): int,
        vol.Optional(CONF_SOURCE_DICT, default={}): SOURCE_DICT_SCHEMA,
        vol.Optional(CONF_VOLUME_STEP, default=DEFAULT_VOLUME_STEP): int,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the NAD platform."""

    nadobject = None
    if config.get(CONF_TYPE) in ("RS232", "Telnet"):
        nadobject = NAD(config)
    else:
        nadobject = NADtcp(config)
    add_entities([nadobject],True,)

    hass.services.register(DOMAIN,"Turn_on_Zone2",nadobject.zone2_turn_on,)
    hass.services.register(DOMAIN,"Turn_off_Zone2",nadobject.zone2_turn_off,)
#    hass.services.register(DOMAIN,"Mute/unmute Zone2 volume",zone2_mute_volume)
#    hass.services.register(DOMAIN,"Turn down Zone2 volume",zone2_volume_down)
#    hass.services.register(DOMAIN,"Set Zone2 volume",zone2_set_volume_level)
#    hass.services.register(DOMAIN,"Turn up Zone2 volume",zone2_volume_up)
#    hass.services.register(DOMAIN,"Turn on Zone3",zone3_turn_on)
#    hass.services.register(DOMAIN,"Turn off Zone3",zone3_turn_off)
#    hass.services.register(DOMAIN,"Mute/unmute Zone3 volume",zone3_mute_volume)
#    hass.services.register(DOMAIN,"Turn down Zone3 volume",zone3_volume_down)
#    hass.services.register(DOMAIN,"Set Zone3 volume",zone3_set_volume_level)
#    hass.services.register(DOMAIN,"Turn up Zone3 volume",zone3_volume_up)


class NAD(MediaPlayerEntity):
    """Representation of a NAD Receiver."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_icon = "mdi:audio-video"
    _attr_supported_features = SUPPORT_NAD

    def __init__(self, config):
        """Initialize the NAD Receiver device."""
        self.config = config
        self._instantiate_nad_receiver()
        self._attr_unique_id = self.config[CONF_UNIQUE_ID]
        self._attr_name = self.config[CONF_NAME]
        self._min_volume = config[CONF_MIN_VOLUME]
        self._max_volume = config[CONF_MAX_VOLUME]
        self._source_dict = config[CONF_SOURCE_DICT]
        self._reverse_mapping = {value: key for key, value in self._source_dict.items()}

        self._zone2_state = None
        self._is_zone2_volume_muted = False
        self._zone2_volume_level = None
        self._zone3_state = None
        self._is_zone3_volume_muted = False
        self._zone3_volume_level = None

    def _instantiate_nad_receiver(self) -> NADReceiver:
        if self.config[CONF_TYPE] == "RS232":
            self._nad_receiver = NADReceiver(self.config[CONF_SERIAL_PORT])
        else:
            host = self.config.get(CONF_HOST)
            port = self.config[CONF_PORT]
            self._nad_receiver = NADReceiverTelnet(host, port)

    def turn_off(self) -> None:
        """Turn the media player off."""
        self._nad_receiver.main_power("=", "Off")

    def turn_on(self) -> None:
        """Turn the media player on."""
        self._nad_receiver.main_power("=", "On")

    def volume_up(self) -> None:
        """Volume up the media player."""
        self._nad_receiver.main_volume("+")

    def volume_down(self) -> None:
        """Volume down the media player."""
        self._nad_receiver.main_volume("-")

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._nad_receiver.main_volume("=", self.calc_db(volume))

    def mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        if mute:
            self._nad_receiver.main_mute("=", "On")
        else:
            self._nad_receiver.main_mute("=", "Off")

    def select_source(self, source: str) -> None:
        """Select input source."""
        self._nad_receiver.main_source("=", self._reverse_mapping.get(source))

    def zone2_turn_on(self) -> None:
        """Turn the zone2 on."""
        self._nad_receiver.zone2_power("=", "On")

    def zone2_turn_off(self) -> None:
        """Turn the zone2 off."""
        self._nad_receiver.zone2_power("=", "Off")

    def zone2_volume_up(self) -> None:
        """Volume up Zone2."""
        self._nad_receiver.zone2_volume("+")

    def zone2_volume_down(self) -> None:
        """Volume down Zone2."""
        self._nad_receiver.zone2_volume("-")

    def zone2_set_volume_level(self, volume: float) -> None:
        """Set volume level Zone2, range 0..1."""
        self._nad_receiver.zone2_volume("=", self.calc_db(volume))

    def zone2_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) Zone2."""
        if mute:
            self._nad_receiver.zone2_mute("=", "On")
        else:
            self._nad_receiver.zone2_mute("=", "Off")

    def zone3_turn_on(self) -> None:
        """Turn the zone3 on."""
        self._nad_receiver.zone3_power("=", "On")

    def zone3_turn_off(self) -> None:
        """Turn the zone3 off."""
        self._nad_receiver.zone3_power("=", "Off")

    def zone3_volume_up(self) -> None:
        """Volume up Zone3."""
        self._nad_receiver.zone3_volume("+")

    def zone3_volume_down(self) -> None:
        """Volume down Zone3."""
        self._nad_receiver.zone3_volume("-")

    def zone3_set_volume_level(self, volume: float) -> None:
        """Set volume level Zone3, range 0..1."""
        self._nad_receiver.zone3_volume("=", self.calc_db(volume))

    def zone3_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) Zone3."""
        if mute:
            self._nad_receiver.zone3_mute("=", "On")
        else:
            self._nad_receiver.zone3_mute("=", "Off")

    @property
    def source_list(self):
        """List of available input sources."""
        return sorted(self._reverse_mapping)

    @property
    def available(self) -> bool:
        """Return if device is available."""
        return self.state is not None

    def update(self) -> None:
        """Retrieve latest state."""
        power_state = self._nad_receiver.main_power("?")
        if not power_state:
            self._attr_state = None
            return
        self._attr_state = (
            MediaPlayerState.ON
            if self._nad_receiver.main_power("?") == "On"
            else MediaPlayerState.OFF
        )

        if self.state == MediaPlayerState.ON:
            self._attr_is_volume_muted = self._nad_receiver.main_mute("?") == "On"
            volume = self._nad_receiver.main_volume("?")
            # Some receivers cannot report the volume, e.g. C 356BEE,
            # instead they only support stepping the volume up or down
            self._attr_volume_level = (
                self.calc_volume(volume) if volume is not None else None
            )
            self._attr_source = self._source_dict.get(
                self._nad_receiver.main_source("?")
            )
        else:
            self._attr_is_volume_muted = None
            self._attr_volume_level = None
            self._attr_source = None

        # Custom attributes
        self._zone2_state = self._nad_receiver.zone2_power("?")
        if self._zone2_state == "On":
            self._is_zone2_volume_muted = self._nad_receiver.zone2_mute("?") == "On"
            volume = self._nad_receiver.zone2_volume("?")
            self._zone2_volume_level = (
                self.calc_volume(volume) if volume is not None else None
            )
        else:
            self._is_zone2_volume_muted = False
            self._zone2_volume_level = None
            
        self._zone3_state = self._nad_receiver.zone3_power("?")
        if self._zone3_state == "On":
            self._is_zone3_volume_muted = self._nad_receiver.zone3_mute("?") == "On"
            volume = self._nad_receiver.zone3_volume("?")
            self._zone3_volume_level = (
                self.calc_volume(volume) if volume is not None else None
            )
        else:
            self._is_zone3_volume_muted = False
            self._zone3_volume_level = None

        self.custom_attributes = {}
        self.custom_attributes['zone2_state'] = self._zone2_state
        self.custom_attributes['is_zone2_volume_muted'] = self._is_zone2_volume_muted
        self.custom_attributes['zone2_volume_level'] = self._zone2_volume_level
        self.custom_attributes['zone3_state'] = self._zone3_state
        self.custom_attributes['is_zone3_volume_muted'] = self._is_zone3_volume_muted
        self.custom_attributes['zone3_volume_level'] = self._zone3_volume_level

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self.custom_attributes


    def calc_volume(self, decibel):
        """Calculate the volume given the decibel.

        Return the volume (0..1).
        """
        return abs(self._min_volume - decibel) / abs(
            self._min_volume - self._max_volume
        )

    def calc_db(self, volume):
        """Calculate the decibel given the volume.

        Return the dB.
        """
        return self._min_volume + round(
            abs(self._min_volume - self._max_volume) * volume
        )


class NADtcp(MediaPlayerEntity):
    """Representation of a NAD Digital amplifier."""

    _addr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_icon = "mdi:audio-video"
    _attr_supported_features = SUPPORT_NAD

    def __init__(self, config):
        """Initialize the amplifier."""
        self._attr_unique_id = self.config[CONF_UNIQUE_ID]
        self._attr_name = config[CONF_NAME]
        self._nad_receiver = NADReceiverTCP(config.get(CONF_HOST))
        self._min_vol = (config[CONF_MIN_VOLUME] + 90) * 2  # from dB to nad vol (0-200)
        self._max_vol = (config[CONF_MAX_VOLUME] + 90) * 2  # from dB to nad vol (0-200)
        self._volume_step = config[CONF_VOLUME_STEP]
        self._nad_volume = None
        self._source_list = self._nad_receiver.available_sources()

    def turn_off(self) -> None:
        """Turn the media player off."""
        self._nad_receiver.power_off()

    def turn_on(self) -> None:
        """Turn the media player on."""
        self._nad_receiver.power_on()

    def volume_up(self) -> None:
        """Step volume up in the configured increments."""
        self._nad_receiver.set_volume(self._nad_volume + 2 * self._volume_step)

    def volume_down(self) -> None:
        """Step volume down in the configured increments."""
        self._nad_receiver.set_volume(self._nad_volume - 2 * self._volume_step)

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        nad_volume_to_set = int(
            round(volume * (self._max_vol - self._min_vol) + self._min_vol)
        )
        self._nad_receiver.set_volume(nad_volume_to_set)

    def mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        if mute:
            self._nad_receiver.mute()
        else:
            self._nad_receiver.unmute()

    def select_source(self, source: str) -> None:
        """Select input source."""
        self._nad_receiver.select_source(source)

    @property
    def source_list(self):
        """List of available input sources."""
        return self._nad_receiver.available_sources()

    def update(self) -> None:
        """Get the latest details from the device."""
        try:
            nad_status = self._nad_receiver.status()
        except OSError:
            return
        if nad_status is None:
            return

        # Update on/off state
        if nad_status["power"]:
            self._attr_state = MediaPlayerState.ON
        else:
            self._attr_state = MediaPlayerState.OFF

        # Update current volume
        self._attr_volume_level = self.nad_vol_to_internal_vol(nad_status["volume"])
        self._nad_volume = nad_status["volume"]

        # Update muted state
        self._attr_is_volume_muted = nad_status["muted"]

        # Update current source
        self._attr_source = nad_status["source"]

    def nad_vol_to_internal_vol(self, nad_volume):
        """Convert nad volume range (0-200) to internal volume range.

        Takes into account configured min and max volume.
        """
        if nad_volume < self._min_vol:
            volume_internal = 0.0
        elif nad_volume > self._max_vol:
            volume_internal = 1.0
        else:
            volume_internal = (nad_volume - self._min_vol) / (
                self._max_vol - self._min_vol
            )
        return volume_internal
