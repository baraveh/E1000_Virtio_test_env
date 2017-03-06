from time import sleep

from utils.graphs import Graph
from utils.sensors import Sensor, SensorBeforeAfter
from utils.vms import Qemu, VM
import re


class InterruptSensor(SensorBeforeAfter):
    def _get_value(self, vm: VM):
        interrupts = vm.remote_command("cat /proc/interrupts")
        if isinstance(vm, Qemu):
            if vm.ethernet_dev == vm.QEMU_E1000:
                interrupts_match = re.search("^\s*\d+:\s+(\d+)\s*[a-zA-Z0-9_-]*\s+(eth0).*$",
                                            interrupts, re.MULTILINE
                                            )
                interrupts_count = interrupts_match.group(1)
                return int(interrupts_count)
            elif vm.ethernet_dev == vm.QEMU_VIRTIO:
                interrupts_count = re.search("^\s*\d+:\s+(\d+)\s*[a-zA-Z0-9_-]*\s+(virtio0-input.0).*$",
                                            interrupts, re.MULTILINE
                                            ).group(1)
                return int(interrupts_count)
            else:
                raise NotImplementedError()
        else:
            raise NotImplementedError()

    def _delta(self, value1, value2):
        return value2 - value1
