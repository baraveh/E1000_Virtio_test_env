import logging

from sensors.packet_num import PacketNumberSensor
from utils.test_base import TestBase
from utils.vms import Qemu, VM, QemuE1000Max, VMware
from sensors.netperf import NetPerfTCP
from utils.graphs import Graph, GraphErrorBars
from utils.shell_utils import run_command

Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build/x86_64-softmmu/qemu-system-x86_64"

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class MainTest(TestBase):
    def __init__(self, netperf_runtime, *args, **kargs):
        super(MainTest, self).__init__(*args, **kargs)

    def get_x_categories(self):
        return [
                # (65160, "65K"),
                # (64*2**10, "64K"),
                # (32*2**10, "32K"),
                # (16*2**10, "16K"),
                # (8*2**10, "8K"),
                (4*2**10, "4K"),
                # (2*2**10, "2K"),
                (1*2**10, "1K"),
                # (512, "512"),
                # (256, "256"),
                # (128, "128"),
                (64, "64"),
                ]

    def get_runtimes(self):
        return [
            2, 4, 8, 16, 32, 64
        ]

    def get_sensors(self):
        netperf_graph = GraphErrorBars("runtime", "throughput", r"/tmp/runtime.pdf", r"/tmp/runtime.txt")
        self.netperf = NetPerfTCP(netperf_graph, runtime=0)

        # packet_sensor = PacketNumberSensor(
        #     Graph("msg size", "packet number", r"/tmp/packet_num.pdf", r"/tmp/packet_num.txt"),
        #     Graph("msg size", "average packet size", r"/tmp/packet_size.pdf", r"/tmp/packet_size.txt")
        # )
        return [self.netperf] # , packet_sensor]

    def get_vms(self):
        qemu_virtio = Qemu(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                           guest_ip="10.10.0.43",
                           host_ip="10.10.0.44")
        qemu_virtio.ethernet_dev = Qemu.QEMU_VIRTIO

        return [
            (qemu_virtio, "qemu_virtio"),
        ]

    def test_func(self, vm: VM, msg_size_name: str, runtime: int, x_value):
        self.netperf.runtime = runtime
        self.netperf.run_netperf(vm, msg_size_name, x_value, msg_size=x_value)

    def pre_run(self):
        for sensor in self._sensors:
            sensor.set_column_names([msg_size_name for _, msg_size_name in self._x_categories])
            sensor.set_x_tics(labels=[str(times) for times in self.get_runtimes()],
                              values=[times for times in self.get_runtimes()])

    def run(self):
        for vm, vm_name in self._vms:
            vm.setup()
            vm.run()

            for msg_size, msg_size_name in self._x_categories:
                for runtime in self.get_runtimes():
                    for i in range(self._retries):
                        for sensor in self._sensors:
                            sensor.test_before(vm)

                        logger.info("Runing msg_size=%s, runtime=%s", msg_size_name, runtime)
                        self.test_func(vm, msg_size_name, runtime, msg_size)

                        for sensor in self._sensors:
                            sensor.test_after(vm, msg_size_name, runtime)

            vm.teardown()

if __name__ == "__main__":
    test = MainTest(netperf_runtime=15, retries=3)
    test.pre_run()
    test.run()
    test.post_run()
