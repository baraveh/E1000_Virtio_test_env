from sensors.cpu import get_all_cpu_sensors
from sensors.interrupts import InterruptSensor
from sensors.kvm_exits import KvmExitsSensor, KvmHaltExitsSensor
from sensors.packet_num import PacketNumberSensor
from sensors.packet_num2 import PacketTxBytesSensor, PacketTxPacketsSensor, PacketRxBytesSensor, PacketRxPacketsSensor
from sensors.qemu_batch import QemuBatchSizeSensor, QemuBatchCountSensor, QemuBatchDescriptorsSizeSensor
from utils.sensors import DummySensor
from utils.test_base import TestBase, TestBaseNetperf
from utils.vms import Qemu, VM, QemuE1000Max, QemuE1000NG, QemuLargeRingNG
from sensors.netperf import NetPerfTCP
from utils.graphs import Graph, GraphErrorBarsGnuplot, RatioGraph

from os import path

# Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build_normal/x86_64-softmmu/qemu-system-x86_64"
# Qemu.QEMU_EXE = r"qemu-system-x86_64"


# Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build-trace/x86_64-softmmu/qemu-system-x86_64"
Qemu.QEMU_EXE = r"qemu-system-x86_64"


class QemuLargeRing(QemuE1000Max):
    def configure_guest(self):
        super(QemuLargeRing, self).configure_guest()
        self.remote_command("sudo ethtool -G eth0 rx 4096")
        self.remote_command("sudo ethtool -G eth0 tx 4096")


class QemuRegularTest(TestBaseNetperf):
    DIR = r"../tmp/results"

    def __init__(self, netperf_runtime, *args, **kargs):
        self.netperf_runtime = netperf_runtime
        super(QemuRegularTest, self).__init__(*args, **kargs)
        # self._stop_after_test = True

    def get_x_categories(self):
        return [
            (64, "64"),
            (128, "128"),
            (256, "256"),
            (512, "512"),
            (1 * 2 ** 10, "1K"),
            (2 * 2 ** 10, "2K"),
            (4 * 2 ** 10, "4K"),
            (8 * 2 ** 10, "8K"),
            (16 * 2 ** 10, "16K"),
            (32 * 2 ** 10, "32K"),
            (64 * 2 ** 10, "64K"),
        ]

    def get_sensors(self):
        netperf_graph = GraphErrorBarsGnuplot("msg size", "throughput",
                                              path.join(self.DIR, "throughput"),
                                              graph_title="Throughput")
        self.netperf = NetPerfTCP(netperf_graph, runtime=self.netperf_runtime)

        # packet_sensor = PacketNumberSensor(
        #     Graph("msg size", "packet number", r"../tmp/packet_num.pdf", r"../tmp/packet_num.txt"),
        #     Graph("msg size", "average packet size", r"../tmp/packet_size.pdf", r"../tmp/packet_size.txt")
        # )

        packet_sensor_tx_bytes = PacketRxBytesSensor(
            Graph("msg size", "Total TX size",
                  path.join(self.DIR, "throughput-tx_bytes"),
                  normalize=self.netperf_runtime
                  )
        )
        packet_sensor_tx_packets = PacketRxPacketsSensor(
            Graph("msg size", "Total TX packets",
                  path.join(self.DIR, "throughput-tx_packets"),
                  normalize=self.netperf_runtime)
        )

        packet_sensor_avg_size = DummySensor(
            RatioGraph(packet_sensor_tx_bytes.graph, packet_sensor_tx_packets.graph,
                       "msg size", "TX Packet Size",
                       path.join(self.DIR, "throughput-tx_packet_size")
                       )
        )

        interrupt_sensor = InterruptSensor(
            Graph("msg size", "interrupt count (per sec)",
                  path.join(self.DIR, "throughput-interrupts"),
                  normalize=self.netperf_runtime)
        )

        kvm_exits = KvmExitsSensor(
            Graph("msg size", "exits count (per sec)",
                  path.join(self.DIR, "throughput-kvm_exits"),
                  normalize=self.netperf_runtime)
        )

        kvm_exits_ratio = DummySensor(
            RatioGraph(kvm_exits.graph, packet_sensor_tx_packets.graph,
                       "msg size", "Exits per Packet",
                       path.join(self.DIR, "throughput-kvm_exits-ratio")
                       )
        )

        interrupt_ratio = DummySensor(
            RatioGraph(interrupt_sensor.graph, packet_sensor_tx_packets.graph,
                       "msg size", "Interrupts per Packet",
                       path.join(self.DIR, "throughput-interrupts-ratio")
                       )
        )

        kvm_halt_exits = KvmHaltExitsSensor(
            GraphErrorBarsGnuplot("msg size", "Halt exits count (per sec)",
                                  path.join(self.DIR, "throughput-kvm_halt_exits"),
                                  normalize=self.netperf_runtime)
        )

        batch_size = QemuBatchSizeSensor(
            Graph("msg size", "Average batch size (in packets)",
                  path.join(self.DIR, "throughput-batch_size"))
        )

        batch_descriptos_size = QemuBatchDescriptorsSizeSensor(
            Graph("msg size", "Average batch size (in descriptors)",
                  path.join(self.DIR, "throughput-batch_descriptors_size"))
        )

        batch_count = QemuBatchCountSensor(
            Graph("msg size", "Average batch Count (per Sec)",
                  path.join(self.DIR, "throughput-batch_count"),
                  normalize=self.netperf_runtime)
        )

        batch_halt_ratio = DummySensor(
            RatioGraph(batch_count.graph, kvm_halt_exits.graph,
                       "msg size", "batch count / kvm halt",
                       path.join(self.DIR, "throughtput-batchCount_kvmHalt"))
        )

        cpu_sensors = get_all_cpu_sensors(self.DIR, "throughput", self.netperf_runtime)

        return [
                   self.netperf,
                   packet_sensor_tx_bytes,
                   packet_sensor_tx_packets,
                   packet_sensor_avg_size,

                   interrupt_sensor,
                   kvm_exits,

                   kvm_exits_ratio,
                   kvm_halt_exits,

                   interrupt_ratio,

                   batch_size,
                   batch_descriptos_size,
                   batch_count,
                   batch_halt_ratio,

               ] + cpu_sensors

    def get_vms(self):
        qemu_virtio = Qemu(disk_path=r"../vms/ubuntu-20.img",
                           guest_ip="10.10.0.43",
                           host_ip="10.10.0.44")
        qemu_virtio.ethernet_dev = Qemu.QEMU_VIRTIO

        qemu_virtio_latency = Qemu(disk_path=r"../vms/ubuntu-20.img",
                                   guest_ip="10.10.0.43",
                                   host_ip="10.10.0.44")
        qemu_virtio_latency.ethernet_dev = Qemu.QEMU_VIRTIO
        qemu_virtio_latency.qemu_config["latency_itr"] = 2

        qemu_e1000_baseline = Qemu(disk_path=r"../vms/ubuntu-20.img",
                                   guest_ip="10.10.0.43",
                                   host_ip="10.10.0.44")
        qemu_e1000_baseline.ethernet_dev = Qemu.QEMU_E1000

        qemu_e1000_arthur = QemuE1000Max(disk_path=r"../vms/ubuntu-20.img",
                                         guest_ip="10.10.0.43",
                                         host_ip="10.10.0.44")
        qemu_e1000_arthur.qemu_config["latency_itr"] = 0
        qemu_e1000_arthur.is_io_thread_nice = False

        qemu_e1000_arthur_nice = QemuE1000Max(disk_path=r"../vms/ubuntu-20.img",
                                         guest_ip="10.10.0.43",
                                         host_ip="10.10.0.44")
        qemu_e1000_arthur_nice.qemu_config["latency_itr"] = 0


        qemu_large_queue = QemuLargeRing(disk_path=r"../vms/ubuntu-20.img",
                               guest_ip="10.10.0.43",
                               host_ip="10.10.0.44")
        qemu_large_queue.is_io_thread_nice = True

        qemu_large_queue_itr = list()
        for i in range(1, 5, 1):
            v = QemuE1000NG(disk_path=r"../vms/ubuntu-20.img",
                            guest_ip="10.10.0.43",
                            host_ip="10.10.0.44")
            v.is_io_thread_nice = True
            v.qemu_config["interrupt_mode"] = 1
            v.qemu_config["drop_packet_every"] = 0
            v.qemu_config["interrupt_mitigation_multiplier"] = 1000
            v.io_nice = i

            qemu_large_queue_itr.append((v, "qemu_ng_%d" % (i,)))

        for i in range(1, 5, 1):
            v = QemuLargeRingNG(disk_path=r"../vms/ubuntu-20.img",
                                guest_ip="10.10.0.43",
                                host_ip="10.10.0.44")
            v.is_io_thread_nice = True
            v.qemu_config["interrupt_mode"] = 1
            v.qemu_config["drop_packet_every"] = 0
            v.qemu_config["interrupt_mitigation_multiplier"] = 1000
            v.io_nice = i

            qemu_large_queue_itr.append((v, "qemu_large_ng_%d" % (i,)))

        return [
            # (qemu_virtio, "virtio-net_baseline"),
            # (qemu_e1000_baseline, "e1000_baseline"),

            # (qemu_e1000_arthur, "e1000_10x_arthur"),
            # (qemu_large_queue, "qemu_large_queue"),
        ] + qemu_large_queue_itr

    def test_func(self, vm: VM, vm_name: str, x_value: int):
        self.netperf.run_netperf(vm, vm_name, x_value, msg_size=x_value)


if __name__ == "__main__":
    test = QemuRegularTest(5, retries=1)
    test.pre_run()
    test.run()
    test.post_run()
