from sensors.packet_num import PacketNumberSensor
from utils.test_base import TestBase, TestBase2VM
from utils.vms import Qemu, VM, QemuE1000Max, VMware, VirtualBox
from sensors.netperf import NetPerfTCP
from utils.graphs import Graph
from utils.shell_utils import run_command

Qemu.QEMU_EXE = r"../qemu/build/x86_64-softmmu/qemu-system-x86_64" 


class MainTest(TestBase2VM):
    def __init__(self, netperf_runtime, *args, **kargs):
        self.netperf_runtime = netperf_runtime
        super(MainTest, self).__init__(*args, **kargs)

    def get_x_categories(self):
        return [
                # (65160, "65K"),
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
        netperf_graph = Graph("msg size", "throughput", r"/tmp/throughput_virtualbox_vm2vm.pdf", r"/tmp/throughput_virtualbox_vm2vm.txt")
        self.netperf = NetPerfTCP(netperf_graph, runtime=self.netperf_runtime)

        # packet_sensor = PacketNumberSensor(
        #     Graph("msg size", "packet number", r"/tmp/packet_num.pdf", r"/tmp/packet_num.txt"),
        #     Graph("msg size", "average packet size", r"/tmp/packet_size.pdf", r"/tmp/packet_size.txt")
        # )
        return [self.netperf] # , packet_sensor]

    def get_vms(self):
        virtualbox_e1000 = VirtualBox(r"e1000", "192.168.56.103", "192.168.56.1")
        virtualbox_e1000_1 = VirtualBox(r"e1000_cp", "192.168.56.101", "192.168.56.1")
        virtualbox_virtio = VirtualBox(r"virtio", "192.168.56.102", "192.168.56.1")
        virtualbox_virtio_1 = VirtualBox(r"virtio_cp", "192.168.56.104", "192.168.56.1")

        return [
            (virtualbox_e1000, virtualbox_e1000_1, "virtualbox_e1000"),
            (virtualbox_virtio, virtualbox_virtio_1, "virtualbox_virtio"),
        ]

    def test_func(self, vm: VM, vm_name: str, x_value: int, remote_ip=None):
        self.netperf.run_netperf(vm, vm_name, x_value, remote_ip=remote_ip, msg_size=x_value)

if __name__ == "__main__":
    test = MainTest(netperf_runtime=15, retries=3)
    test.pre_run()
    test.run()
    test.post_run()
