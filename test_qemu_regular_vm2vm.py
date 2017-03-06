from sensors.packet_num import PacketNumberSensor
from utils.test_base import TestBase, TestBase2VM
from utils.vms import Qemu, VM, QemuE1000Max
from sensors.netperf import NetPerfTCP
from utils.graphs import Graph
from utils.shell_utils import run_command, run_command_check

Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build/x86_64-softmmu/qemu-system-x86_64"


class QemuE1000GuestOnly(QemuE1000Max):
    def __init__(self, *args, **kwargs):
        super(QemuE1000GuestOnly, self).__init__(*args, **kwargs)
        del self.qemu_config["no_tcp_csum_on"]

    def _configure_host(self):
        pass

    def _reset_host_configuration(self):
        pass


class MainTest(TestBase2VM):
    def __init__(self, netperf_runtime, *args, **kargs):
        self.netperf_runtime = netperf_runtime
        super(MainTest, self).__init__(*args, **kargs)

    def get_msg_sizes(self):
        return [
            # (65160, "65K"),
            (64 * 2 ** 10, "64K"),
            (32 * 2 ** 10, "32K"),
            (16 * 2 ** 10, "16K"),
            (8 * 2 ** 10, "8K"),
            (4 * 2 ** 10, "4K"),
            (2 * 2 ** 10, "2K"),
            (1 * 2 ** 10, "1K"),
            (512, "512"),
            (256, "256"),
            (128, "128"),
            (64, "64"),
        ]

    def get_sensors(self):
        netperf_graph = Graph("msg size", "throughput", r"/tmp/throughput_qemu_vm2vm.pdf",
                              r"/tmp/throughput_qemu_vm2vm.txt")
        self.netperf = NetPerfTCP(netperf_graph, runtime=self.netperf_runtime)

        packet_sensor = PacketNumberSensor(
            Graph("msg size", "packet number", r"/tmp/packet_num_vm2vm.pdf", r"/tmp/packet_num_vm2vm.txt"),
            Graph("msg size", "average packet size", r"/tmp/packet_size_vm2vm.pdf", r"/tmp/packet_size_vm2vm.txt")
        )
        return [self.netperf, packet_sensor]

    def test_func(self, vm: VM, vm_name: str, msg_size: int, remote_ip=None):
        self.netperf.run_netperf(vm, vm_name, msg_size, remote_ip=remote_ip, msg_size=msg_size)

    def get_vms(self):
        qemu_virtio1 = Qemu(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                            guest_ip="10.10.0.43",
                            host_ip="10.10.0.44")
        qemu_virtio1.ethernet_dev = Qemu.QEMU_VIRTIO
        qemu_virtio2 = Qemu(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm-copy.img",
                            guest_ip="10.10.0.42",
                            host_ip="10.10.0.44")
        qemu_virtio2.vnc_number = 11
        qemu_virtio2.ethernet_dev = Qemu.QEMU_VIRTIO
        qemu_virtio2.mac_address = "52:54:00:a0:e5:1d"
        qemu_virtio2.cpu_to_pin = 3

        qemu_e1000_1 = Qemu(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                            guest_ip="10.10.0.43",
                            host_ip="10.10.0.44")
        qemu_e1000_1.ethernet_dev = Qemu.QEMU_E1000
        qemu_e1000_2 = Qemu(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm-copy.img",
                            guest_ip="10.10.0.42",
                            host_ip="10.10.0.44")
        qemu_e1000_2.ethernet_dev = Qemu.QEMU_E1000
        qemu_e1000_2.vnc_number = 11
        qemu_e1000_2.mac_address = "52:54:00:a0:e5:1d"
        qemu_e1000_2.cpu_to_pin = 3

        qemu_e1000_best1 = QemuE1000GuestOnly(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                                              guest_ip="10.10.0.43",
                                              host_ip="10.10.0.44")
        qemu_e1000_best2 = QemuE1000GuestOnly(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm-copy.img",
                                              guest_ip="10.10.0.42",
                                              host_ip="10.10.0.44")
        qemu_e1000_best2.vnc_number = 11
        qemu_e1000_best2.mac_address = "52:54:00:a0:e5:1d"
        qemu_e1000_best2.cpu_to_pin = 3

        for vm in (qemu_virtio1, qemu_virtio2, qemu_e1000_1, qemu_e1000_2, qemu_e1000_best1,
                   qemu_e1000_best2):
            vm.bridge = "br-vms"
            # vm.cpu_to_pin = "0-3"

        return [
            (qemu_e1000_1, qemu_e1000_2, "qemu_e1000_base"),
            (qemu_virtio1, qemu_virtio2, "qemu_virtio_base"),
            (qemu_e1000_best1, qemu_e1000_best2, "qemu_e1000_tcp_checksum"),
        ]

    def configure_bride(self):
        run_command("sudo brctl addbr br-vms")
        run_command("sudo  ip link set {tap} up".format(tap="br-vms"))
        run_command("sudo ip a a {host_ip}/24 dev {tap}".format(host_ip="10.10.0.44",
                                                                tap="br-vms"))

    def teardown_bridge(self):
        run_command_check("sudo  ip link set {tap} down".format(tap="br-vms"))
        run_command_check("sudo brctl delbr br-vms")

if __name__ == "__main__":
    test = MainTest(15, retries=3)
    test.configure_bride()
    test.pre_run()
    test.run()
    test.post_run()
    test.teardown_bridge()
