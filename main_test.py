from utils.test_base import TestBase
from utils.vms import Qemu, VM
from sensors.netperf import NetPerfTCP
from utils.graphs import Graph


class MainTest(TestBase):
    def __init__(self, *args, **kargs):
        super(MainTest, self).__init__(*args, **kargs)

    def get_msg_sizes(self):
        return [(65160, "65K")]

    def get_sensors(self):
        self.netperf_graph = Graph("msg size", "throughput", r"/tmp/throughput.pdf", r"/tmp/throughput.txt")
        self.netperf = NetPerfTCP(self.netperf_graph)
        return [self.netperf]

    def get_vms(self):
        self.qemu_virtio = Qemu(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                                guest_ip="10.10.0.43",
                                host_ip="10.10.0.44")
        self.qemu_virtio.ethernet_dev = Qemu.QEMU_VIRTIO

        return [(self.qemu_virtio, "qemu_virtio")]

    def test_func(self, vm: VM, vm_name: str, msg_size: int, retry: int):
        self.netperf.run_netperf(vm, vm_name, msg_size, msg_size)

if __name__ == "__main__":
    test = MainTest(1)
    test.pre_run()
    test.run()
    test.post_run()