from time import sleep

from utils.vms import VM, Qemu
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

        self._x_categories = self.get_x_categories()
        self._stop_after_test = False

    def test_func(self, vm: VM, vm_name: str, x_value: int):
        raise NotImplementedError()

    def get_vms(self): # -> list[(VM, str)]:
        raise NotImplementedError()

    def get_sensors(self): # -> list[Sensor]:
        raise NotImplementedError()

    def get_x_categories(self): # -> list[(int, str)]:
        raise NotImplementedError()

    def pre_run(self):
        for sensor in self._sensors:
            sensor.set_column_names([vm_name for _, vm_name in self._vms])
            sensor.set_x_tics(labels=[size_name for _, size_name in self._x_categories],
                              values=[size for size, _ in self._x_categories])

    def run(self):
        for vm, vm_name in self._vms:
            vm.setup()
            vm.run()
            try:
                for x_value, x_value_name in self._x_categories:
                    for i in range(self._retries):
                        for sensor in self._sensors:
                            try:
                                sensor.test_before(vm)
                            except:
                                logger.error("Exception: ", exc_info=True)

                        logger.info("Runing vm=%s, msg size=%s", vm_name, x_value_name)
                        self.test_func(vm, vm_name, x_value)

                        for sensor in self._sensors:
                            try:
                                sensor.test_after(vm, vm_name, x_value)
                            except:
                                logger.error("Exception: ", exc_info=True)
            except KeyboardInterrupt:
                pass
            except:
                import traceback
                traceback.print_exc()
            finally:
                if self._stop_after_test:
                    input("Press Enter to continue")
                vm.teardown()

    def post_run(self):
        for sensor in self._sensors:
            sensor.create_graph(self._retries)


class TestBase2VM(TestBase):
    def get_vms(self): # -> list[(VM, VM, str)]
        raise NotImplementedError()

    def test_func(self, vm: VM, vm_name: str, x_value: int, remote_ip=None):
        pass

    def pre_run(self):
        for sensor in self._sensors:
            sensor.set_column_names([vm_name for _, _, vm_name in self._vms])
            sensor.set_x_tics(labels=[size_name for _, size_name in self._x_categories],
                              values=[size for size, _ in self._x_categories])

    def run(self):
        for vm1, vm2, vm_name in self._vms:
            vm1.setup()
            vm1.run()
            vm2.setup()
            vm2.run()
            try:
                for msg_size, msg_size_name in self._x_categories:
                    for i in range(self._retries):
                        for sensor in self._sensors:
                            sensor.test_before(vm1)

                        logger.info("Runing vm=%s, msg size=%s", vm_name, msg_size_name)
                        self.test_func(vm1, vm_name, msg_size, remote_ip=vm2.ip_guest)

                        for sensor in self._sensors:
                            sensor.test_after(vm1, vm_name, msg_size)
            except KeyboardInterrupt:
                raise
            except:
                import traceback
                traceback.print_exc()
                input("press enter to continue")
                raise
            finally:
                vm2.teardown()
                vm1.teardown()
                sleep(10)
