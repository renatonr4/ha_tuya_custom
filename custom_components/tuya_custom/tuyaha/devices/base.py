import time
from datetime import datetime
import logging

_LOGGER = logging.getLogger(__name__)


class TuyaDevice:

    def __init__(self, data, api):
        self.api = api
        self.data = data.get("data")
        self.obj_id = data.get("id")
        self.obj_type = data.get("ha_type")
        self.obj_name = data.get("name")
        self.dev_type = data.get("dev_type")
        self.icon = data.get("icon")
        self._first_update = True
        self._last_update = datetime.min
        self._last_query = datetime.min

    def _update_data(self, key, value, force_val=False):
        if self.data:
            if not force_val and self.data.get(key) is None:
                return
            self.data[key] = value
            self.api.update_device_data(self.obj_id, self.data)

    def _control_device(self, action, param=None):
        success, response = self.api.device_control(self.obj_id, action, param)
        if not success:
            self._update_data("online", False)
        else:
            self._last_update = datetime.now()
        return success

    def _update(self, use_discovery):

        """Avoid get cache value after control."""
        difference = (datetime.now() - self._last_update).total_seconds()
        wait_delay = difference < 0.5

        data = None
        if use_discovery or self._first_update:
            if wait_delay:
                time.sleep(0.5)
            # workaround for https://github.com/PaulAnnekov/tuyaha/issues/3
            self._first_update = False
            devices = self.api.discovery()
            if not devices:
                return
            for device in devices:
                if device["id"] == self.obj_id:
                    data = device["data"]
                    break

        else:
            # query can be called once every 60 seconds
            difference = (datetime.now() - self._last_query).total_seconds()
            if difference < self.api.query_interval:
                return
            if difference == self.api.query_interval:
                wait_delay = True
            if wait_delay:
                time.sleep(0.5)

            success, response = self.api.device_control(
                self.obj_id, "QueryDevice", namespace="query"
            )
            self._last_query = datetime.now()
            if success:
                data = response["payload"]["data"]

            # Logging FrequentlyInvoke
            else:
                def get_result_code():
                    if not response:
                        return ""
                    return response["header"]["code"]

                result_code = get_result_code()
                if result_code == "FrequentlyInvoke":
                    _LOGGER.info(
                        "Method [Query] for device %s fails using poll interval %s - error: %s",
                        self.obj_id,
                        self.api.query_interval,
                        response["header"].get("msg", result_code),
                    )

        if data:
            if not self.data:
                self.data = data
            else:
                self.data.update(data)
            return True

        return

    def __repr__(self):
        module = self.__class__.__module__
        if module is None or module == str.__class__.__module__:
            module = ""
        else:
            module += "."
        return '<{module}{clazz}: "{name}" ({obj_id})>'.format(
            module=module,
            clazz=self.__class__.__name__,
            name=self.obj_name,
            obj_id=self.obj_id
        )

    def name(self):
        return self.obj_name

    def state(self):
        state = self.data.get("state")
        if state is None:
            return None
        elif isinstance(state, str):
            if state == "true":
                return True
            return False
        else:
            return bool(state)

    def device_type(self):
        return self.dev_type

    def object_id(self):
        return self.obj_id

    def object_type(self):
        return self.obj_type

    def available(self):
        return self.data.get("online")

    def iconurl(self):
        return self.icon

    def update(self, use_discovery=True):
        return self._update(use_discovery)
