from sensors.interrupts import InterruptSensor
from sensors.packet_num import PacketNumberSensor
from utils.test_base import TestBase
from utils.vms import Qemu, VM, QemuE1000Max
from sensors.netperf import NetPerfTCP
from utils.graphs import Graph
from utils.shell_utils import run_command

# Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build_normal/x86_64-softmmu/qemu-system-x86_64"
Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build/x86_64-softmmu/qemu-system-x86_64"
# Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build-trace/x86_64-softmmu/qemu-system-x86_64"


class QemuLargeRing(QemuE1000Max):
    def configure_guest(self):
        super(QemuLargeRing, self).configure_guest()
        self.remote_command("sudo ethtool -G eth0 rx 4096")
        self.remote_command("sudo ethtool -G eth0 tx 4096")


class MainTest(TestBase):
    def __init__(self, netperf_runtime, *args, **kargs):
        self.netperf_runtime = netperf_runtime
        super(MainTest, self).__init__(*args, **kargs)
        # self._stop_after_test = True

    def get_x_categories(self):
        return [
                # (65160, "65K"),
                (64*2**10, "64K"),
                (32*2**10, "32K"),
                (16*2**10, "16K"),
                # (8*2**10, "8K"),
                (4*2**10, "4K"),
                # (2*2**10, "2K"),
                (1*2**10, "1K"),
                # (512, "512"),
                (256, "256"),
                # (128, "128"),
                (64, "64"),
                ]

    def get_sensors(self):
        netperf_graph = Graph("msg size", "throughput", r"/home/bdaviv/tmp/throughput.pdf", r"/home/bdaviv/tmp/throughput.txt")
        self.netperf = NetPerfTCP(netperf_graph, runtime=self.netperf_runtime)

        packet_sensor = PacketNumberSensor(
            Graph("msg size", "packet number", r"/home/bdaviv/tmp/packet_num.pdf", r"/home/bdaviv/tmp/packet_num.txt"),
            Graph("msg size", "average packet size", r"/home/bdaviv/tmp/packet_size.pdf", r"/home/bdaviv/tmp/packet_size.txt")
        )

        interrupt_sensor = InterruptSensor(
            Graph("msg size", "interrupt count", r"/home/bdaviv/tmp/interrupts.pdf", r"/home/bdaviv/tmp/interrupts.txt")
        )
        return [
                self.netperf,
                packet_sensor,
                interrupt_sensor,
                ]

    def get_vms(self):
        vms = []
        for i in range(1, 161, 20):
            vm = QemuE1000Max(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                               guest_ip="10.10.0.43",
                               host_ip="10.10.0.44")
            vm.qemu_config["tx_packets_per_batch"] = i
            vm.qemu_config["no_mit_timer_on"] = 1
            vms.append((vm, i))

        return [(vm, "delay_{}".format(d)) for vm, d in vms]

    def test_func(self, vm: VM, vm_name: str, x_value: int):
        self.netperf.run_netperf(vm, vm_name, x_value, msg_size=x_value)

if __name__ == "__main__":
    test = MainTest(5, retries=1)
    test.pre_run()
    test.run()
    test.post_run()
