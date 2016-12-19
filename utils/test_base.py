from utils.vms import VM
from utils.sensors import Sensor
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class TestBase:
    def __init__(self, retries: int):
        self._retries = retries

        self._vms = self.get_vms()
        self._sensors = self.get_sensors()

        self._msg_sizes = self.get_msg_sizes()

    def test_func(self, vm: VM, vm_name: str, msg_size: int, retry: int):
        raise NotImplementedError()

    def get_vms(self): # -> list[(VM, str)]:
        raise NotImplementedError()

    def get_sensors(self): # -> list[Sensor]:
        raise NotImplementedError()

    def get_msg_sizes(self): # -> list[(int, str)]:
        raise NotImplementedError()

    def pre_run(self):
        for sensor in self._sensors:
            sensor.set_column_names([vm_name for _, vm_name in self._vms])
            sensor.set_x_tics(labels=[size_name for _, size_name in self._msg_sizes],
                              values=[size for size, _ in self._msg_sizes])

    def run(self):
        for vm, vm_name in self._vms:
            vm.setup()
            vm.run()

            for msg_size, msg_size_name in self._msg_sizes:
                for i in range(self._retries):
                    for sensor in self._sensors:
                        sensor.test_before(vm)

                    logger.info("Runing vm=%s, msg size=%s", vm_name, msg_size_name)
                    self.test_func(vm, vm_name, msg_size, i)

                    for sensor in self._sensors:
                        sensor.test_after(vm, vm_name, msg_size)

            vm.teardown()

    def post_run(self):
        for sensor in self._sensors:
            sensor.create_graph(self._retries)
