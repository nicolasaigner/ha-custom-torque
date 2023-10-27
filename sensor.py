import logging
import re
import voluptuous as vol
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_EMAIL, CONF_NAME, CONF_SENSORS
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

# logging.basicConfig(filename='torque2.log', level=logging.DEBUG)

# _LOGGER = logging.getLogger(__name__)

API_PATH = "/api/torque2"
DEFAULT_NAME = "vehicle"
DOMAIN = "torque2"
_DEFAULT_SENSORS = []

ENTITY_NAME_FORMAT = "{0} {1}"

SENSOR_EMAIL_FIELD = "eml"
SENSOR_NAME_KEY = r"userFullName(\w+)"
SENSOR_UNIT_KEY = r"userUnit(\w+)"
SENSOR_VALUE_KEY = r"k(\w+)"

NAME_KEY = re.compile(SENSOR_NAME_KEY)
UNIT_KEY = re.compile(SENSOR_UNIT_KEY)
VALUE_KEY = re.compile(SENSOR_VALUE_KEY)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SENSORS, default=_DEFAULT_SENSORS): cv.ensure_list,
    }
)

def setup_platform(hass, config, add_entities, discovery_info=None):
    vehicle = config.get(CONF_NAME)
    email = config.get(CONF_EMAIL)
    sensors = {}
    for sensor in config.get(CONF_SENSORS):
        try:
            for key, value in sensor.items():
                try:
                    if isinstance(key, str):
                        sensors[int(key, 16)] = TorqueSensor(
                            ENTITY_NAME_FORMAT.format(vehicle, value.get('name', 'Unknown')),
                            value.get('unit', 'Unknown'),
                        )
                    else:
                        _LOGGER.warning(f'Key is not a string, skipping: {key}')
                except Exception as e:
                    _LOGGER.error(f'An error occurred while processing key {key}: {e}')
        except Exception as e:
            _LOGGER.error(f'An error occurred while processing sensor: {e}')
    
    try:
        hass.http.register_view(
            TorqueReceiveDataView(email, vehicle, sensors, add_entities)
        )
    except Exception as e:
        _LOGGER.error(f'An error occurred while registering view: {e}')

    return True

class TorqueReceiveDataView(HomeAssistantView):
    url = API_PATH
    name = "api:torque2"

    def __init__(self, email, vehicle, sensors, add_entities):
        self.email = email
        self.vehicle = vehicle
        self.sensors = sensors
        self.add_entities = add_entities
        _LOGGER.debug('Torque data listener started')

    @callback
    def get(self, request):
        _LOGGER.debug('REQUEST')
        _LOGGER.debug(request.query)
        _LOGGER.debug(request.headers)
        _LOGGER.debug(request)
        _LOGGER.debug('TRY AND EXCEPT')
        try:
            data = request.query
            if self.email and self.email != data.get(SENSOR_EMAIL_FIELD, ''):
                return

            for key in data.keys():
                try:
                    is_name = NAME_KEY.match(key)
                    is_unit = UNIT_KEY.match(key)
                    is_value = VALUE_KEY.match(key)

                    pid = None
                    if is_name or is_unit or is_value:
                        pid = int(is_name.group(1) if is_name else is_unit.group(1) if is_unit else is_value.group(1), 16)

                    if pid in self.sensors:
                        self.sensors[pid].async_on_update(data[key])
                except Exception as e:
                    _LOGGER.error(f'An error occurred while processing data: {e}')
        except Exception as e:
            _LOGGER.error(f'An error occurred in get method: {e}')
        
        return "OK!"

class TorqueSensor(Entity):
    def __init__(self, name, unit):
        self._name = name
        self._unit = unit
        self._state = None

    @property
    def name(self):
        return self._name

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return "mdi:car"

    @callback
    def async_on_update(self, value):
        try:
            self._state = value
            self.async_schedule_update_ha_state()
        except Exception as e:
            _LOGGER.error(f'An error occurred while updating sensor: {e}')
