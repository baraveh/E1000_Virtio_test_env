from time import sleep

from utils.graphs import Graph
from utils.sensors import Sensor, SensorBeforeAfter
from utils.shell_utils import run_command, run_command_output
from utils.vms import Qemu, VM
import re


class KvmExitsSensor(SensorBeforeAfter):
    def _get_value(self, vm: VM):
        kvm_exits = run_command_output("sudo cat /sys/kernel/debug/kvm/exits")
        return int(kvm_exits)


    def _delta(self, value1, value2):
        return value2 - value1
