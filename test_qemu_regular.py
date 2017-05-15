from sensors.interrupts import InterruptSensor
from sensors.kvm_exits import KvmExitsSensor
from sensors.packet_num import PacketNumberSensor
from sensors.packet_num2 import PacketTxBytesSensor, PacketTxPacketsSensor, PacketRxBytesSensor, PacketRxPacketsSensor
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


class QemuRegularTest(TestBase):
    DIR = r"/home/bdaviv/tmp/"

    def __init__(self, netperf_runtime, *args, **kargs):
        self.netperf_runtime = netperf_runtime
        super(QemuRegularTest, self).__init__(*args, **kargs)
        # self._stop_after_test = True

    def get_msg_sizes(self):
        return [
                # (65160, "65K"),
                (64*2**10, "64K"),
                # (32*2**10, "32K"),
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
        netperf_graph = GraphErrorBarsGnuplot("msg size", "throughput", r"/home/bdaviv/tmp/throughput.pdf", r"/home/bdaviv/tmp/throughput.txt",
                              graph_title="Throughput")
        self.netperf = NetPerfTCP(netperf_graph, runtime=self.netperf_runtime)

        # packet_sensor = PacketNumberSensor(
        #     Graph("msg size", "packet number", r"/home/bdaviv/tmp/packet_num.pdf", r"/home/bdaviv/tmp/packet_num.txt"),
        #     Graph("msg size", "average packet size", r"/home/bdaviv/tmp/packet_size.pdf", r"/home/bdaviv/tmp/packet_size.txt")
        # )

        packet_sensor_tx_bytes = PacketRxBytesSensor(
            Graph("msg size", "Total TX size", path.join(self.DIR, "throughput-tx_bytes.pdf"), path.join(self.DIR, "throughput-tx_bytes.txt"))
        )
        packet_sensor_tx_packets = PacketRxPacketsSensor(
            Graph("msg size", "Total TX packets", path.join(self.DIR, "throughput-tx_packets.pdf"), path.join(self.DIR, "throughput-tx_packets.txt"))
        )

        packet_sensor_avg_size = DummySensor(
            RatioGraph(packet_sensor_tx_bytes.graph, packet_sensor_tx_packets.graph,
                       "msg size", "TX Packet Size",
                       path.join(self.DIR, "throughput-tx_packet_size.pdf"), path.join(self.DIR, "throughput-tx_packet_size.txt"))
        )

        interrupt_sensor = InterruptSensor(
            Graph("msg size", "interrupt count (per sec)", r"/home/bdaviv/tmp/throughput-interrupts.pdf", r"/home/bdaviv/tmp/throughput-interrupts.txt",
                  normalize=self.netperf_runtime)
        )

        kvm_exits = KvmExitsSensor(
            Graph("msg size", "exits count (per sec)", r"/home/bdaviv/tmp/throughput-kvm_exits.pdf", r"/home/bdaviv/tmp/throughput-kvm_exits.txt",
                  normalize=self.netperf_runtime)
        )

        kvm_exits_ratio = DummySensor(
            RatioGraph(kvm_exits.graph, packet_sensor_tx_packets.graph,
                       "msg size", "Exits per Packet",
                       path.join(self.DIR, "throughput-kvm_exits-ratio.pdf"), path.join(self.DIR, "throughput-kvm_exits-ratio.txt"))
        )

        interrupt_ratio = DummySensor(
            RatioGraph(interrupt_sensor.graph, packet_sensor_tx_packets.graph,
                       "msg size", "Interrupts per Packet",
                       path.join(self.DIR, "throughput-interrupts-ratio.pdf"),
                       path.join(self.DIR, "throughput-interrupts-ratio.txt"))
        )

        return [
                self.netperf,
                packet_sensor_tx_bytes,
                packet_sensor_tx_packets,
                packet_sensor_avg_size,

                interrupt_sensor,
                kvm_exits,

                kvm_exits_ratio,
                interrupt_ratio,
                ]

    def get_vms(self):
        qemu_virtio = Qemu(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                                guest_ip="10.10.0.43",
                                host_ip="10.10.0.44")
        qemu_virtio.ethernet_dev = Qemu.QEMU_VIRTIO

        qemu_e1000_baseline = Qemu(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                                guest_ip="10.10.0.43",
                                host_ip="10.10.0.44")
        qemu_e1000_baseline.ethernet_dev = Qemu.QEMU_E1000

        qemu_e1000_newest = QemuE1000Max(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                               guest_ip="10.10.0.43",
                               host_ip="10.10.0.44")
        qemu_e1000_newest.qemu_config["tx_packets_per_batch"] = 20
        qemu_e1000_newest.qemu_config["latency_itr"] = 1
        qemu_e1000_newest.qemu_config["no_mit_timer_on"] = 0

        qemu_e1000_arthur = QemuE1000Max(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                                       guest_ip="10.10.0.43",
                                       host_ip="10.10.0.44")
        qemu_e1000_arthur.qemu_config["latency_itr"] = 0
        qemu_e1000_arthur.qemu_config["tx_packets_per_batch"] = 0

        qemu_smart_itr = QemuE1000Max(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                                         guest_ip="10.10.0.43",
                                         host_ip="10.10.0.44")
        qemu_smart_itr.qemu_config["latency_itr"] = 1
        qemu_smart_itr.qemu_config["tx_packets_per_batch"] = 0
        qemu_smart_itr.qemu_config["dynamic_latency_mode"] = 0

        qemu_smart_itr2 = QemuE1000Max(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                                      guest_ip="10.10.0.43",
                                      host_ip="10.10.0.44")
        qemu_smart_itr2.qemu_config["latency_itr"] = 1
        qemu_smart_itr2.ethernet_dev = 'e1000-82545em'
        qemu_smart_itr2.addiotional_guest_command = 'sudo ethtool -C eth0 rx-usecs 3000'

        qemu_smart_itr3 = QemuE1000Max(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
                                      guest_ip="10.10.0.43",
                                      host_ip="10.10.0.44")
        qemu_smart_itr3.qemu_config["latency_itr"] = 2
        qemu_smart_itr3.ethernet_dev = 'e1000-82545em'
        qemu_smart_itr3.addiotional_guest_command = 'sudo ethtool -C eth0 rx-usecs 3000'

        # qemu_smart_itr3.ethernet_dev = 'e1000-82545em'
        # qemu_smart_itr3.addiotional_guest_command = 'sudo ethtool -C eth0 rx-usecs 3000'
        # qemu_smart_itr3.qemu_config["drop_packet_every"] = 0

        #
        # qemu_e1000_no_new_improv = QemuE1000Max(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
        #                                      guest_ip="10.10.0.43",
        #                                      host_ip="10.10.0.44")
        # qemu_e1000_no_new_improv.qemu_config["smart_interrupt_mitigation"] = 0
        # qemu_e1000_no_new_improv.qemu_config["drop_packet_every"] = 0
        #
        # qemu_virtio_drop = QemuE1000Max(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
        #                                      guest_ip="10.10.0.43",
        #                                      host_ip="10.10.0.44")
        # qemu_virtio_drop.qemu_config["smart_interrupt_mitigation"] = 0
        # qemu_virtio_drop.qemu_config["drop_packet_every"] = 0
        # qemu_virtio_drop.ethernet_dev = Qemu.QEMU_VIRTIO
        #
        # qemu_large = QemuLargeRing(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
        #                        guest_ip="10.10.0.43",
        #                        host_ip="10.10.0.44")

        # qemu_e1000_best_itr = QemuE1000Max(disk_path=r"/home/bdaviv/repos/e1000-improv/vms/vm.img",
        #                                guest_ip="10.10.0.43",
        #                                host_ip="10.10.0.44")
        # qemu_e1000_best_itr.exe = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build/x86_64-softmmu/qemu-system-x86_64"

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
                # (qemu_e1000_no_new_improv, "qemu_e1000_no_new_improv"),

                (qemu_e1000_baseline, "qemu_e1000_base_line"),
                # (qemu_e1000_newest, "qemu_e1000_newest"),

                (qemu_e1000_arthur, "qemu_e1000_arthur"),
                # (qemu_smart_itr, "qemu_smart_latency1"),
                # (qemu_smart_itr2, "qemu_smart_latency2"),
                (qemu_smart_itr3, "qemu_smart_latency3"),

                # (qemu_e1000_no_new_improv, "qemu_e1000_no_new_improv")
                # (qemu_large, "qemu_large_ring"),
                # (qemu_e1000_best_itr, "qemu_e1000_best_itr"),
                # (self.qemu_virtio_1g, "qemu_virtio_1G"),
                # (self.qemu_e1000_1g, "qemu_e1000_1G"),
                ]

    def test_func(self, vm: VM, vm_name: str, msg_size: int):
        self.netperf.run_netperf(vm, vm_name, msg_size, msg_size=msg_size)

if __name__ == "__main__":
    test = QemuRegularTest(5, retries=1)
    test.pre_run()
    test.run()
    test.post_run()
