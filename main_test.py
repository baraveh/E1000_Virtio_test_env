from sensors.packet_num import PacketNumberSensor
from utils.test_base import TestBase
from utils.vms import Qemu, VM, QemuE1000Max
from sensors.netperf import NetPerfTCP
from utils.graphs import Graph
from utils.shell_utils import run_command

Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build/x86_64-softmmu/qemu-system-x86_64" 


class MainTest(TestBase):
    def __init__(self, netperf_runtime, *args, **kargs):
        super(MainTest, self).__init__(*args, **kargs)
        self.netperf_runtime = netperf_runtime

    def get_msg_sizes(self):
        return [
                (65160, "65K"),
                (64*2**10, "64K"),
                (32*2**10, "32K"),
                (16*2**10, "16K"),
                (8*2**10, "8K"),
                (4*2**10, "4K"),
                (2*2**10, "2K"),
                (1*2**10, "1K"),
                (512, "512"),
                (256, "256"),
                (128, "128"),
                (64, "64"),
                ]

    def get_sensors(self):
        netperf_graph = Graph("msg size", "throughput", r"/tmp/throughput.pdf", r"/tmp/throughput.txt")
        self.netperf = NetPerfTCP(netperf_graph, runtime=self.netperf_runtime)

        packet_sensor = PacketNumberSensor(
            Graph("msg size", "packet number", r"/tmp/packet_num.pdf", r"/tmp/packet_num.txt"),
            Graph("msg size", "average packet size", r"/tmp/packet_size.pdf", r"/tmp/packet_size.txt")
        )
        return [self.netperf, packet_sensor]

    def get_vms(self):
        qemu_virtio = Qemu(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                                guest_ip="10.10.0.43",
                                host_ip="10.10.0.44")
        qemu_virtio.ethernet_dev = Qemu.QEMU_VIRTIO

        qemu_e1000 = Qemu(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                                guest_ip="10.10.0.43",
                                host_ip="10.10.0.44")
        qemu_e1000.ethernet_dev = Qemu.QEMU_E1000

        qemu_e1000_best = QemuE1000Max(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                               guest_ip="10.10.0.43",
                               host_ip="10.10.0.44")

        # self.qemu_virtio_1g = Qemu(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
        #                            guest_ip="10.10.0.43",
        #                            host_ip="10.10.0.44")
        # self.qemu_virtio_1g.ethernet_dev = Qemu.QEMU_VIRTIO
        # self.qemu_virtio_1g.mem=1024
        #
        # self.qemu_e1000_1g = Qemu(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
        #                           guest_ip="10.10.0.43",
        #                           host_ip="10.10.0.44")
        # self.qemu_e1000_1g.ethernet_dev = Qemu.QEMU_E1000
        # self.qemu_e1000_1g.mem=1024

        return [
                (qemu_virtio, "qemu_virtio_base"),
                (qemu_e1000, "qemu_e1000_base"),
                (qemu_e1000_best, "qemu_e1000"),
                # (self.qemu_virtio_1g, "qemu_virtio_1G"),
                # (self.qemu_e1000_1g, "qemu_e1000_1G"),
                ]

    def test_func(self, vm: VM, vm_name: str, msg_size: int, retry: int):
        self.netperf.run_netperf(vm, vm_name, msg_size, msg_size)

if __name__ == "__main__":
    test = MainTest(retries=3, netperf_runtime=60)
    test.pre_run()
    test.run()
    test.post_run()
