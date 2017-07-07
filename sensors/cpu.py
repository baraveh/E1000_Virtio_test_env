from enum import Enum

from os import path

from utils.graphs import Graph, RatioGraph
from utils.sensors import Sensor, SensorBeforeAfter, DummySensor
from utils.vms import VM, Qemu

"""
http://man7.org/linux/man-pages/man5/proc.5.html
"""


class CpuUtilizationEnum(Enum):
    USER = 1
    NICE = 2
    SYSTEM = 3
    IDLE = 4
    IOWAIT = 5
    IRQ = 6
    SOFTIRQ = 7
    STEAL = 8
    GUEST = 9
    GUEST_NICE = 10


class CpuUtilization:
    def __init__(self, typ: CpuUtilizationEnum):
        self._type = typ

    def read_value(self):
        with open("/proc/stat") as f:
            line = f.readline()
            split = line.split()
            assert split[0] == "cpu"
            return int(split[self._type.value])


class CpuUserSensor(SensorBeforeAfter):
    def __init__(self, typ: CpuUtilizationEnum, *args, **kargs):
        super(CpuUserSensor, self).__init__(*args, **kargs)
        self.cpu = CpuUtilization(typ)

    def _get_value(self, vm: VM):
        return self.cpu.read_value()

    def _delta(self, value1, value2):
        return value2 - value1


def get_all_cpu_sensors(directory, prefix, normalize=None):
    result = list()
    for utilType in CpuUtilizationEnum:
        sensor = CpuUserSensor(utilType,
                               Graph("Msg Size", "CPU Util {}".format(utilType.name),
                                     path.join(directory,
                                               "{prefix}-cpu-{name}".format(prefix=prefix, name=utilType.name)),
                                     normalize=normalize
                                     )
                               )
        result.append(sensor)
    return result


class ProcCpuUtilizationEnum(Enum):
    USER = 13  # utime (including guest_time)
    KERNEL = 14  # stime
    GUEST = 42  # guest time


class ProcCpuUtilization:
    def __init__(self, typ: ProcCpuUtilizationEnum):
        self._type = typ

    def read_value(self, vm: Qemu):
        with open("/proc/{pid}/stat".format(pid=vm.get_pid())) as f:
            line = f.readline()
            split = line.split()
            return int(split[self._type.value])


class ProcKernelUsegeSensor(SensorBeforeAfter):
    def __init__(self, *args, **kargs):
        super(ProcKernelUsegeSensor, self).__init__(*args, **kargs)
        self.cpu = ProcCpuUtilization(ProcCpuUtilizationEnum.KERNEL)

    def _get_value(self, vm: VM):
        return self.cpu.read_value(vm)

    def _delta(self, value1, value2):
        return value2 - value1


class ProcGuestUsegeSensor(SensorBeforeAfter):
    def __init__(self, *args, **kargs):
        super(ProcGuestUsegeSensor, self).__init__(*args, **kargs)
        self.cpu = ProcCpuUtilization(ProcCpuUtilizationEnum.GUEST)

    def _get_value(self, vm: VM):
        return self.cpu.read_value(vm)

    def _delta(self, value1, value2):
        return value2 - value1


class ProcUserUsegeSensor(SensorBeforeAfter):
    def __init__(self, *args, **kargs):
        super(ProcUserUsegeSensor, self).__init__(*args, **kargs)
        self.guest = ProcCpuUtilization(ProcCpuUtilizationEnum.GUEST)
        self.user = ProcCpuUtilization(ProcCpuUtilizationEnum.USER)

    def _get_value(self, vm: VM):
        return self.user.read_value(vm) - self.guest.read_value(vm)

    def _delta(self, value1, value2):
        return value2 - value1


def get_all_proc_cpu_sensors(directory, prefix, netperf_graph: Graph, normalize=None):
    result = list()

    for proc_sensor, name in ((ProcKernelUsegeSensor, "Kernel"),
                              (ProcGuestUsegeSensor, "Guest"),
                              (ProcUserUsegeSensor, "User")):
        sensor = proc_sensor(
            Graph("Msg Size", "{name} Time".format(name=name),
                  path.join(directory,
                            "{prefix}-proc-cpu-{name}".format(prefix=prefix, name=name)),
                  normalize=normalize
                  )
        )
        result.append(sensor)

        ratio_sensor = DummySensor(
            RatioGraph(sensor.graph, netperf_graph,
                       "msg size", "{name} time".format(name=name),
                       path.join(directory,
                                 "{prefix}-proc-cpu-{name}-ratio".format(prefix=prefix, name=name))
                       )
        )
        result.append(ratio_sensor)
    return result
