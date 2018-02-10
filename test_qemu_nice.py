from sensors.cpu import get_all_cpu_sensors
from sensors.interrupts import InterruptSensor
from sensors.kvm_exits import KvmExitsSensor, KvmHaltExitsSensor
from sensors.packet_num import PacketNumberSensor
from sensors.packet_num2 import PacketTxBytesSensor, PacketTxPacketsSensor, PacketRxBytesSensor, PacketRxPacketsSensor
from sensors.qemu_batch import QemuBatchSizeSensor, QemuBatchCountSensor, QemuBatchDescriptorsSizeSensor
from test_qemu_throughput import QemuThroughputTest
from utils.sensors import DummySensor
from utils.test_base import TestBase
from utils.vms import Qemu, VM, QemuE1000Max
from sensors.netperf import NetPerfTCP
from utils.graphs import Graph, GraphErrorBarsGnuplot, RatioGraph

from os import path

# Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build_normal/x86_64-softmmu/qemu-system-x86_64"
Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build/x86_64-softmmu/qemu-system-x86_64"


# Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build-trace/x86_64-softmmu/qemu-system-x86_64"


class QemuLargeRing(QemuE1000Max):
    def configure_guest(self):
        super(QemuLargeRing, self).configure_guest()
        self.remote_command("sudo ethtool -G eth0 rx 4096")
        self.remote_command("sudo ethtool -G eth0 tx 4096")


class QemuNiceTest(QemuThroughputTest):
    DIR = r"/home/bdaviv/tmp/results"

    def __init__(self, netperf_runtime, *args, **kargs):
        super(QemuNiceTest, self).__init__(netperf_runtime, *args, **kargs)
        self.msg_size = 8 * 2 ** 10  # 64K
        # self._stop_after_test = True
        for sensor in self._sensors:
            sensor.graph.log_scale_x = 0

    def get_x_categories(self):
        categories = range(-10, 11)
        return [(x, str(x)) for x in categories]

    def test_func(self, vm: VM, vm_name: str, x_value: int):
        vm.set_iothread_nice(x_value)
        self.netperf.run_netperf(vm, vm_name, x_value, msg_size=self.msg_size)

    def get_vms(self):
        qemu_virtio = Qemu(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                           guest_ip="10.10.0.43",
                           host_ip="10.10.0.44")
        qemu_virtio.ethernet_dev = Qemu.QEMU_VIRTIO

        qemu_e1000_arthur = QemuE1000Max(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                                         guest_ip="10.10.0.43",
                                         host_ip="10.10.0.44")
        qemu_large_queue = QemuLargeRing(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                                         guest_ip="10.10.0.43",
                                         host_ip="10.10.0.44")
        qemu_large_queue_batch_itr = QemuLargeRing(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                                                   guest_ip="10.10.0.43",
                                                   host_ip="10.10.0.44")
        qemu_large_queue_batch_itr.is_io_thread_nice = True
        qemu_large_queue_batch_itr.qemu_config["interrupt_mode"] = 1
        qemu_large_queue_batch_itr.qemu_config["drop_packet_every"] = 0
        qemu_large_queue_batch_itr.qemu_config["interrupt_mitigation_multiplier"] = 1000

        return [
                # (qemu_virtio, "qemu_virtio"),
                # (qemu_e1000_arthur, "qemu_e1000_arthur"),
                # (qemu_large_queue, "qemu_e1000_large_queue"),
                (qemu_large_queue_batch_itr, "qemu_large_queue_batch_itr")
                ]

if __name__ == "__main__":
    test = QemuNiceTest(5, retries=1)
    test.pre_run()
    test.run()
    test.post_run()
