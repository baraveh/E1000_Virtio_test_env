import json
import os
from collections import defaultdict
from time import sleep

from utils.machine import localRoot
from utils.vms import VM
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TestBase:
    DIR = ""

    def __init__(self, retries: int, directory=None, all_x=True, additional_x=None, ):
        self.dir = self.DIR
        if directory:
            self.dir = directory
        assert self.dir

        self._retries = retries

        self._vms = self.get_vms()
        self._sensors = self.get_sensors()

        if all_x:
            self._x_categories = self.get_x_categories()
        else:
            self._x_categories = list()
        self._stop_after_test = False

        if additional_x:
            self._x_categories += additional_x

    def test_func(self, vm: VM, vm_name: str, x_value: int):
        raise NotImplementedError()

    def get_vms(self):  # -> list[(VM, str)]:
        raise NotImplementedError()

    def get_sensors(self):  # -> list[Sensor]:
        raise NotImplementedError()

    def get_x_categories(self):  # -> list[(int, str)]:
        raise NotImplementedError()

    def create_testinfo(self):
        VMS = "VMs"
        HOST = "Host"
        TEST = "Test"
        testinfo_filename = os.path.join(self.dir, "testinfo.json")

        old_info = dict()
        if os.path.exists(testinfo_filename):
            with open(testinfo_filename, "r") as f:
                old_info = json.load(f)

        if VMS not in old_info:
            old_info[VMS] = defaultdict(lambda: None)

        info = dict()
        info[HOST] = localRoot.get_info()
        info[VMS] = dict()
        for vm, name in self._vms:
            if vm.enabled:
                info[VMS][name] = vm.get_info()
            else:
                info[VMS][name] = vm.get_info(old_info[VMS][name])

        info[TEST] = dict()
        info[TEST]["name"] = self.__class__.__name__
        info[TEST]["runtime"] = getattr(self, "netperf_runtime", 0)

        with open(testinfo_filename, "w") as f:
            json.dump(info, f, sort_keys=True, indent=4)

    def pre_run(self):
        self.create_testinfo()
        for sensor in self._sensors:
            sensor.set_column_names([vm_name for _, vm_name in self._vms])
            sensor.set_x_tics(labels=[size_name for _, size_name in self._x_categories],
                              values=[size for size, _ in self._x_categories])

    def run(self):
        for vm, vm_name in self._vms:
            if vm.enabled:
                self.run_vm(vm, vm_name)
            else:
                self.load_old_vm_data(vm, vm_name)

    def run_vm(self, vm, vm_name):
        vm.setup()
        vm.run()
        try:
            for x_value, x_value_name in self._x_categories:
                for i in range(self._retries):
                    for sensor in self._sensors:
                        try:
                            sensor.test_before(vm)
                        except:
                            logger.error("Sensor Exception: ", exc_info=True)

                    logger.info("Running vm=%s, msg size=%s", vm_name, x_value_name)
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

    def load_old_vm_data(self, vm, vm_name):
        for sensor in self._sensors:
            sensor.load_old_data(vm_name)

    def post_run(self):
        self.create_sensor_graphs()

    def create_sensor_graphs(self, vm_names_to_include=None, folder=None):
        for sensor in self._sensors:
            try:
                sensor.create_graph(self._retries, vm_names_to_include=vm_names_to_include, folder=folder)
            except:
                logger.exception("Failed to create graph %s", sensor)


class TestBaseNetperf(TestBase):
    NETPERF_CORE = '0'

    def __init__(self, *args, netperf_core=None, **kargs):
        super().__init__(*args, **kargs)
        self.netperf_core = netperf_core
        if netperf_core is None:
            self.netperf_core = self.NETPERF_CORE

    def pre_run(self):
        super().pre_run()

    def post_run(self):
        super().post_run()


class TestBase2VM(TestBaseNetperf):
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

