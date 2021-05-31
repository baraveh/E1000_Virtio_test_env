from sensors import netperf
from sensors.cpu import get_all_cpu_sensors, get_all_proc_cpu_sensors
from sensors.interrupts import InterruptSensor
from sensors.kvm_exits import KvmExitsSensor, KvmHaltExitsSensor
from sensors.packet_num2 import PacketTxBytesSensor, PacketTxPacketsSensor, PacketRxBytesSensor, PacketRxPacketsSensor
from utils.sensors import DummySensor
from utils.test_base import TestBase
from utils.vms import Qemu, VM, QemuE1000Max
from sensors.netperf import NetPerfTCP
from utils.graphs import Graph, GraphErrorBarsGnuplot, RatioGraph

from os import path

# Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build_normal/x86_64-softmmu/qemu-system-x86_64"
Qemu.QEMU_EXE = r"../qemu/build/qemu-system-x86_64"
# Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build-trace/x86_64-softmmu/qemu-system-x86_64"


class QemuLargeRing(QemuE1000Max):
    def configure_guest(self):
        super(QemuLargeRing, self).configure_guest()
        self.remote_command("sudo ethtool -G eth0 rx 4096")
        self.remote_command("sudo ethtool -G eth0 tx 4096")


class QemuTest(TestBase):

    def __init__(self, netperf_runtime, *args, dir_name=None, **kargs):
        if not dir_name:
            self.DIR = r"../tmp/results"
        else:
            self.Dir = dir_name
        self.netperf_runtime = netperf_runtime
        super(QemuTest, self).__init__(*args, **kargs)
        # self._stop_after_test = True

    def get_x_categories(self):
        return [
                # (65160, "65K"),
                # (64*2**10, "64K"),
                # (32*2**10, "32K"),
                # (16*2**10, "16K"),
                # (8*2**10, "8K"),
                # (4*2**10, "4K"),
                # (2*2**10, "2K"),
                # (1*2**10, "1K"),
                # (512, "512"),
                # (256, "256"),
                # (128, "128"),
                (64, "64"),
                ]

    def get_sensors(self):
        self.netperf = netperf.NetPerfLatency(
            Graph("Message size [bytes]", "Transactions/Sec",
                                  path.join(self.DIR, "latency"),
                                  graph_title="Latency"),
            runtime=self.netperf_runtime
        )
        # self.netperf.graph.script_filename = "gnuplot/plot_columns_latency"

        interrupt_sensor = InterruptSensor(
            Graph("msg size", "interrupt count (per sec)",
                  path.join(self.DIR, "latency-interrupts"),
                  normalize=self.netperf_runtime)
        )

        kvm_exits = KvmExitsSensor(
            Graph("msg size", "exits count (per sec)",
                  path.join(self.DIR, "latency-kvm_exits"),
                  normalize=self.netperf_runtime)
        )

        kvm_exits_ratio = DummySensor(
            RatioGraph(kvm_exits.graph, self.netperf.graph,
                       "msg size", "Exits per transaction",
                       path.join(self.DIR, "latency-kvm_exits-ratio"),
                       graph_title="KVM exits per transaction")
        )

        kvm_halt_exits = KvmHaltExitsSensor(
            GraphErrorBarsGnuplot("msg size", "Halt exits count (per sec)",
                                  path.join(self.DIR, "latency-kvm_halt_exits"),
                                  normalize=self.netperf_runtime)
        )

        kvm_halt_exits_ratio = DummySensor(
            RatioGraph(kvm_halt_exits.graph, self.netperf.graph,
                       "msg size", "Halt Exits per transaction",
                       path.join(self.DIR, "latency-kvm_halt_exits-ratio"),
                       graph_title="KVM Haly exits per transaction")
        )

        packet_sensor_tx_bytes = PacketRxBytesSensor(
            Graph("msg size", "Total TX size",
                  path.join(self.DIR, "latency-tx_bytes"),
                  normalize=self.netperf_runtime)
        )
        packet_sensor_tx_packets = PacketRxPacketsSensor(
            Graph("msg size", "Total TX packets",
                  path.join(self.DIR, "latency-tx_packets"),
                  normalize=self.netperf_runtime)
        )

        packet_sensor_avg_size = DummySensor(
            RatioGraph(packet_sensor_tx_bytes.graph, packet_sensor_tx_packets.graph,
                       "msg size", "TX Packet Size",
                       path.join(self.DIR, "latency-tx_packet-size")))

        interrupt_ratio = DummySensor(
            RatioGraph(interrupt_sensor.graph, self.netperf.graph,
                       "msg size", "Interrupts per transaction",
                       path.join(self.DIR, "latency-interrupts-ratio"))
        )

        cpu_sensors = get_all_cpu_sensors(self.DIR, "latency", self.netperf_runtime)
        proc_cpu_sensors = get_all_proc_cpu_sensors(self.DIR, "latency", self.netperf.graph, self.netperf_runtime)

        return [self.netperf,
                interrupt_sensor,

                kvm_exits,
                kvm_halt_exits,
                kvm_exits_ratio,
                kvm_halt_exits_ratio,

                packet_sensor_tx_bytes,
                packet_sensor_tx_packets,
                packet_sensor_avg_size,

                interrupt_ratio
                ] + cpu_sensors + proc_cpu_sensors

    def get_vms(self):
        # ***********************
        qemu_virtio = Qemu(disk_path=r"../vms/ubuntu-20.img",
                           guest_ip="10.10.0.43",
                           host_ip="10.10.0.44")
        qemu_virtio.ethernet_dev = Qemu.QEMU_VIRTIO
        # ***********************
        qemu_virtio_latency = Qemu(disk_path=r"../vms/ubuntu-20.img",
                                   guest_ip="10.10.0.43",
                                   host_ip="10.10.0.44")
        qemu_virtio_latency.ethernet_dev = Qemu.QEMU_VIRTIO
        qemu_virtio_latency.qemu_config["latency_itr"] = 2
        # ***********************
        qemu_e1000_baseline = Qemu(disk_path=r"../vms/ubuntu-20.img",
                                   guest_ip="10.10.0.43",
                                   host_ip="10.10.0.44")
        qemu_e1000_baseline.ethernet_dev = Qemu.QEMU_E1000
        # ***********************
        qemu_e1000_arthur = QemuE1000Max(disk_path=r"../vms/ubuntu-20.img",
                                         guest_ip="10.10.0.43",
                                         host_ip="10.10.0.44")
        qemu_e1000_arthur.qemu_config["latency_itr"] = 0
        # ***********************
        qemu_smart_itr3 = QemuE1000Max(disk_path=r"../vms/ubuntu-20.img",
                                       guest_ip="10.10.0.43",
                                       host_ip="10.10.0.44")
        qemu_smart_itr3.qemu_config["latency_itr"] = 2
        qemu_smart_itr3.ethernet_dev = 'e1000-82545em'
        qemu_smart_itr3.addiotional_guest_command = 'sudo ethtool -C eth0 rx-usecs 3000'
        # ***********************
        return [
                (qemu_virtio, "virtio-net_baseline"),
                (qemu_virtio_latency, "virito-net_smart_latency"),

                (qemu_e1000_baseline, "e1000_baseline"),

                (qemu_e1000_arthur, "e1000_10x"),
                (qemu_smart_itr3, "e1000_smart_latency"),

                ]

    def test_func(self, vm: VM, vm_name: str, x_value: int):
        self.netperf.run_netperf(vm, vm_name, x_value, msg_size=x_value)

if __name__ == "__main__":
    import sys
    dirname = None
    if len(sys.argv) > 1:
        dirname = sys.argv[1]
    test = QemuTest(30, retries=1, dir_name=dirname)
    test.pre_run()
    test.run()
    test.post_run()
