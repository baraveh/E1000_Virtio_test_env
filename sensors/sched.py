from time import sleep

from utils.graphs import Graph
from utils.sensors import Sensor, SensorBeforeAfter
from utils.vms import Qemu, VM
import re


class SchedSwitchSensor(SensorBeforeAfter):
    def _delta(self, value1, value2):
        return value2 - value1

    def _get_value(self, vm: Qemu):
        with open("/proc/{}/sched".format(vm.get_pid())) as f:
            for line in f:
                if line.count(":") != 1:
                    continue
                k, v = (a.strip() for a in line.split(":"))
                if k == "nr_switches":
                    return int(v)
