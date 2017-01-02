from sensors.packet_num import PacketNumberSensor
from utils.test_base import TestBase
from utils.vms import Qemu, VM, QemuE1000Max, VMware
from sensors.netperf import NetPerfTCP
from utils.graphs import Graph, GraphMatplotlib
from utils.shell_utils import run_command

Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build/x86_64-softmmu/qemu-system-x86_64" 


class MainTest(TestBase):
    def __init__(self, netperf_runtime, *args, **kargs):
        self.netperf_runtime = netperf_runtime
        super(MainTest, self).__init__(*args, **kargs)

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
        # netperf_graph = Graph("msg size", "throughput", r"/tmp/vmware-throughput.pdf", r"/tmp/vmware-throughput.txt")
        netperf_graph = Graph("msg size", "throughput", r"/tmp/vmware-throughput.pdf", r"/tmp/vmware-throughput.txt")
        self.netperf = NetPerfTCP(netperf_graph, runtime=self.netperf_runtime)

        # packet_sensor = PacketNumberSensor(
        #     Graph("msg size", "packet number", r"/tmp/packet_num.pdf", r"/tmp/packet_num.txt"),
        #     Graph("msg size", "average packet size", r"/tmp/packet_size.pdf", r"/tmp/packet_size.txt")
        # )
        return [self.netperf] # , packet_sensor]

    def get_vms(self):
        vmware_e1000 = VMware(r"/homes/bdaviv/Shared\ VMs/Ubuntu\ Linux\ -\ e1000/Ubuntu\ Linux\ -\ e1000.vmx",
                              "192.168.221.128", "192.168.221.1")
        vmware_para = VMware(r"/homes/bdaviv/Shared\ VMs/Ubuntu\ Linux\ -\ paravirtual_nic/Ubuntu\ Linux\ -\ paravirtual_nic.vmx",
                             "192.168.221.129", "192.168.221.1")
        return [
                (vmware_e1000, "vmware_e1000"),
                (vmware_para, "vmware_paravirtual"),
                ]

    def test_func(self, vm: VM, vm_name: str, msg_size: int):
        self.netperf.run_netperf(vm, vm_name, msg_size, msg_size)

if __name__ == "__main__":
    test = MainTest(netperf_runtime=1, retries=1)
    test.pre_run()
    test.run()
    test.post_run()
