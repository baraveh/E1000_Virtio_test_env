from copy import deepcopy

from sensors.cpu import get_all_cpu_sensors, get_all_proc_cpu_sensors
from sensors.interrupts import InterruptSensor, QemuInterruptDelaySensor
from sensors.kvm_exits import KvmExitsSensor, KvmHaltExitsSensor
from sensors.packet_num import PacketNumberSensor, NicTxStopSensor, TCPTotalMSgs, TCPFirstMSgs
from sensors.packet_num2 import PacketTxBytesSensor, PacketTxPacketsSensor, PacketRxBytesSensor, PacketRxPacketsSensor
from sensors.qemu_batch import QemuBatchSizeSensor, QemuBatchCountSensor, QemuBatchDescriptorsSizeSensor
from sensors.sched import SchedSwitchSensor
from utils.sensors import DummySensor
from utils.test_base import TestBase, TestBaseNetperf
from utils.vms import Qemu, VM, QemuE1000Max, QemuE1000NG, QemuLargeRingNG, QemuLargeRing, QemuNG
from sensors.netperf import NetPerfTCP, NetPerfTcpTSO
from utils.graphs import Graph, GraphErrorBarsGnuplot, RatioGraph, GraphRatioGnuplot, GraphScatter, FuncGraph, \
    EmptyGraph

from os import path

# Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build_normal/x86_64-softmmu/qemu-system-x86_64"
#Qemu.QEMU_EXE = r"/usr/lib/qemu"


# Qemu.QEMU_EXE = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build-trace/x86_64-softmmu/qemu-system-x86_64"
Qemu.QEMU_EXE = r"/homes/bdaviv/repos/msc-ng/qemu-ng/build/x86_64-softmmu/qemu-system-x86_64"


class QemuThroughputTest(TestBaseNetperf):
    DIR = r"../tmp/results"
    NETPERF_CLS = NetPerfTCP

    def __init__(self, netperf_runtime, *args, **kargs):
        self.netperf_runtime = netperf_runtime
        self.netperf = None
        super().__init__(*args, **kargs)
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
        netperf_graph = Graph("message size",
                              "",
                              path.join(self.dir, "throughput"),
                              graph_title="throughput (mbps)")
        self.netperf = self.NETPERF_CLS(netperf_graph, runtime=self.netperf_runtime)

        # packet_sensor = PacketNumberSensor(
        #     Graph("message size", "packet number", r"../tmp/packet_num.pdf", r"../tmp/packet_num.txt"),
        #     Graph("message size", "average packet size", r"../tmp/packet_size.pdf", r"../tmp/packet_size.txt")
        # )
        netperf_graph_ratio = DummySensor(
            GraphRatioGnuplot(
                netperf_graph,
                "message size",
                "throughput (log ratio to first)",
                path.join(self.dir, "throughput-ratio"),
                graph_title="throughput (%s sec)" % (self.netperf_runtime,)
            )
        )

        packet_sensor_tx_bytes = PacketRxBytesSensor(
            Graph("message size", "TX size per second (Mb)",
                  path.join(self.dir, "throughput-tx_bytes"),
                  normalize=self.netperf_runtime*1000*1000/8
                  )
        )
        packet_sensor_tx_packets = PacketRxPacketsSensor(
            Graph("message size", "total tx packets",
                  path.join(self.dir, "throughput-tx_packets"),
                  normalize=self.netperf_runtime)
        )

        packet_sensor_avg_size = DummySensor(
            RatioGraph(packet_sensor_tx_bytes.graph, packet_sensor_tx_packets.graph,
                       "message size", "tx packet size (KB)",
                       path.join(self.dir, "throughput-tx_packet_size"),
                       normalize=8 * 0.001
                       )
        )

        interrupt_sensor = InterruptSensor(
            Graph("message size", "interrupt count (per sec)",
                  path.join(self.dir, "throughput-interrupts"),
                  normalize=self.netperf_runtime)
        )

        kvm_exits = KvmExitsSensor(
            Graph("message size", "exits count (per sec)",
                  path.join(self.dir, "throughput-kvm_exits"),
                  normalize=self.netperf_runtime)
        )

        kvm_exits_ratio = DummySensor(
            RatioGraph(kvm_exits.graph, packet_sensor_tx_packets.graph,
                       "message size", "exits per Packet",
                       path.join(self.dir, "throughput-kvm_exits-ratio")
                       )
        )

        interrupt_ratio = DummySensor(
            RatioGraph(interrupt_sensor.graph, packet_sensor_tx_packets.graph,
                       "message size", "interrupts per Packet",
                       path.join(self.dir, "throughput-interrupts-ratio")
                       )
        )

        kvm_halt_exits = KvmHaltExitsSensor(
            Graph("message size", "halt exits count (per sec)",
                                  path.join(self.dir, "throughput-kvm_halt_exits"),
                                  normalize=self.netperf_runtime)
        )

        batch_size = QemuBatchSizeSensor(
            Graph("message size", "average batch size (in packets)",
                  path.join(self.dir, "throughput-batch_size"))
        )

        batch_descriptos_size = QemuBatchDescriptorsSizeSensor(
            Graph("message size", "average batch size (in descriptors)",
                  path.join(self.dir, "throughput-batch_descriptors_size"))
        )

        batch_count = QemuBatchCountSensor(
            Graph("message size", "average batch Count (per Sec)",
                  path.join(self.dir, "throughput-batch_count"),
                  normalize=self.netperf_runtime)
        )

        batch_halt_ratio = DummySensor(
            RatioGraph(batch_count.graph, kvm_halt_exits.graph,
                       "message size", "batch count / kvm halt",
                       path.join(self.dir, "throughput-batchCount_kvmHalt"))
        )
        batch_halt_ratio.graph.log_scale_y = 2

        cpu_sensors = get_all_cpu_sensors(self.dir, "throughput", self.netperf_runtime, exits_graph=kvm_exits.graph)
        cpu_proc_sensors = get_all_proc_cpu_sensors(self.dir, "throughput", self.netperf_runtime, exits_graph=kvm_exits.graph)

        throughput2segment_size = DummySensor(
            GraphScatter(packet_sensor_avg_size.graph, netperf_graph,
                         "sent segment size (KB)", "Throughput",
                         path.join(self.dir, "throughput-segment_throughput"))
        )

        interrupt_delay = QemuInterruptDelaySensor(
            Graph("message size", "average interrupt delay",
                  path.join(self.dir, "throughput-interrupt_delay"))
        )

        bytes_per_batch = DummySensor(
            FuncGraph(lambda x, y: x*y,
                      batch_size.graph, packet_sensor_avg_size.graph,
                      "message size", "bytes per batch",
                      path.join(self.dir, "throughput-batch_bytes")
                      )
        )

        sched_switch = SchedSwitchSensor(
            Graph("message size", "num of scheduler switch (per sec)",
                  path.join(self.dir, "throughput-context_switch"),
                  normalize=self.netperf_runtime
                  )
        )
        sched_switch_per_batch = DummySensor(
            RatioGraph(sched_switch.graph, batch_count.graph,
                       "message size", "context switch per batch",
                       path.join(self.dir, "throughput-context_switch-ratio")
                       )
        )

        kvm_exits_batch_ratio = DummySensor(
            RatioGraph(kvm_exits.graph, batch_count.graph,
                       "message size", "exits per batch",
                       path.join(self.dir, "throughput-kvm_exits-batch_ratio")
                       )
        )

        batch_time = DummySensor(
            FuncGraph(lambda x: 1e6 / x,
                      batch_count.graph, EmptyGraph(),
                      "message size", "batch duration [usec]",
                      path.join(self.dir, "throughput-batch_time")
                      )
        )

        interrupt_ratio_batch = DummySensor(
            RatioGraph(interrupt_sensor.graph, batch_count.graph,
                       "message size", "interrupts per batch",
                       path.join(self.dir, "throughput-interrupts-batch")
                       )
        )

        nic_tx_stop = NicTxStopSensor(
            Graph("message size", "num of tx queue stops (per sec)",
                  path.join(self.dir, "throughput-tx_queue_stop"),
                  normalize=self.netperf_runtime
                  )
        )

        nic_tx_stop_ratio_batch = DummySensor(
            RatioGraph(nic_tx_stop.graph, batch_count.graph,
                       "message size", "queue stops per batch",
                       path.join(self.dir, "throughput-tx_queue_stop-batch")
                       )
        )

        tcp_total_msgs = TCPTotalMSgs(
            Graph("message size", "num of transmited msgs per second",
                  path.join(self.dir, "throughput-tcp_msgs_total"),
                  normalize=self.netperf_runtime
                  )
        )

        tcp_first_msgs = TCPFirstMSgs(
            Graph("message size", "num of transmited first msgs per second",
                  path.join(self.dir, "throughput-tcp_msgs_first"),
                  normalize=self.netperf_runtime
                  )
        )

        tcp_msgs_ratio = DummySensor(
            RatioGraph(tcp_first_msgs.graph, tcp_total_msgs.graph,
                       "message size", "queue stops per batch",
                       path.join(self.dir, "throughput-tcp_msgs-ratio")
                       )
        )

        return [
                   self.netperf,
                   netperf_graph_ratio,
                   packet_sensor_tx_bytes,
                   packet_sensor_tx_packets,
                   packet_sensor_avg_size,

                   interrupt_sensor,
                   kvm_exits,

                   kvm_exits_ratio,
                   kvm_halt_exits,

                   interrupt_ratio,
                   interrupt_ratio_batch,

                   batch_size,
                   batch_descriptos_size,
                   batch_count,
                   batch_halt_ratio,
                   bytes_per_batch,
                   batch_time,

                   throughput2segment_size,

                   interrupt_delay,

                   sched_switch,
                   sched_switch_per_batch,

                   kvm_exits_batch_ratio,
                   nic_tx_stop,
                   nic_tx_stop_ratio_batch,

                   tcp_total_msgs,
                   tcp_first_msgs,
                   tcp_msgs_ratio,
               ] + cpu_sensors + cpu_proc_sensors

    def get_vms(self):
        qemu_e1000e = Qemu(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                           guest_ip="10.10.0.43",
                           host_ip="10.10.0.44")
        qemu_e1000e.ethernet_dev = "e1000e"

        qemu_virtio = Qemu(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                           guest_ip="10.10.0.43",
                           host_ip="10.10.0.44")
        qemu_virtio.ethernet_dev = Qemu.QEMU_VIRTIO

        qemu_virtio_drop_packets = QemuNG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                           guest_ip="10.10.0.43",
                           host_ip="10.10.0.44")
        qemu_virtio_drop_packets.ethernet_dev = Qemu.QEMU_VIRTIO
        qemu_virtio_drop_packets.e1000_options["NG_drop_packet"] = "on"

        qemu_virtio_latency = Qemu(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                                   guest_ip="10.10.0.43",
                                   host_ip="10.10.0.44")
        qemu_virtio_latency.ethernet_dev = Qemu.QEMU_VIRTIO
        qemu_virtio_latency.qemu_config["latency_itr"] = 2

        qemu_e1000_baseline = Qemu(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                                   guest_ip="10.10.0.43",
                                   host_ip="10.10.0.44")
        qemu_e1000_baseline.ethernet_dev = Qemu.QEMU_E1000

        qemu_e1000_arthur = QemuE1000Max(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                                         guest_ip="10.10.0.43",
                                         host_ip="10.10.0.44")
        qemu_e1000_arthur.qemu_config["latency_itr"] = 0
        qemu_e1000_arthur_nice = QemuE1000Max(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                                         guest_ip="10.10.0.43",
                                         host_ip="10.10.0.44")
        qemu_e1000_arthur_nice.qemu_config["latency_itr"] = 0
        qemu_e1000_arthur_nice.is_io_thread_nice = True

        qemu_smart_itr = QemuE1000Max(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                                      guest_ip="10.10.0.43",
                                      host_ip="10.10.0.44")
        qemu_smart_itr.qemu_config["latency_itr"] = 1
        qemu_smart_itr.qemu_config["tx_packets_per_batch"] = 0
        qemu_smart_itr.qemu_config["dynamic_latency_mode"] = 0

        qemu_smart_itr2 = QemuE1000Max(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                                       guest_ip="10.10.0.43",
                                       host_ip="10.10.0.44")
        qemu_smart_itr2.qemu_config["latency_itr"] = 1
        qemu_smart_itr2.ethernet_dev = 'e1000-82545em'
        qemu_smart_itr2.addiotional_guest_command = 'sudo ethtool -C eth0 rx-usecs 3000'

        qemu_smart_itr3 = QemuE1000Max(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                                       guest_ip="10.10.0.43",
                                       host_ip="10.10.0.44")
        qemu_smart_itr3.qemu_config["latency_itr"] = 2
        qemu_smart_itr3.ethernet_dev = 'e1000-82545em'
        qemu_smart_itr3.addiotional_guest_command = 'sudo ethtool -C eth0 rx-usecs 3000'

        qemu_e1000_io_thread = QemuE1000Max(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                                            guest_ip="10.10.0.43",
                                            host_ip="10.10.0.44")
        qemu_e1000_io_thread.nic_additionals = ",iothread=iothread0"
        # qemu_smart_itr3.ethernet_dev = 'e1000-82545em'
        # qemu_smart_itr3.addiotional_guest_command = 'sudo ethtool -C eth0 rx-usecs 3000'
        # qemu_smart_itr3.qemu_config["drop_packet_every"] = 0

        #
        # qemu_e1000_no_new_improv = QemuE1000Max(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
        #                                      guest_ip="10.10.0.43",
        #                                      host_ip="10.10.0.44")
        # qemu_e1000_no_new_improv.qemu_config["smart_interrupt_mitigation"] = 0
        # qemu_e1000_no_new_improv.qemu_config["drop_packet_every"] = 0
        #
        # qemu_virtio_drop = QemuE1000Max(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
        #                                      guest_ip="10.10.0.43",
        #                                      host_ip="10.10.0.44")
        # qemu_virtio_drop.qemu_config["smart_interrupt_mitigation"] = 0
        # qemu_virtio_drop.qemu_config["drop_packet_every"] = 0
        # qemu_virtio_drop.ethernet_dev = Qemu.QEMU_VIRTIO
        #
        qemu_large_queue = QemuLargeRing(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                               guest_ip="10.10.0.43",
                               host_ip="10.10.0.44")
        qemu_large_queue.is_io_thread_nice = True
        qemu_large_queue.qemu_config["drop_packet_every"]=0

        qemu_large_queue_itr6 = QemuLargeRing(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                                         guest_ip="10.10.0.43",
                                         host_ip="10.10.0.44")
        qemu_large_queue_itr6.is_io_thread_nice = True
        qemu_large_queue_itr6.qemu_config["interrupt_mitigation_multiplier"] = 6
        qemu_large_queue_itr6.qemu_config["drop_packet_every"] = 0

        qemu_large_queue_batch_itr = QemuLargeRing(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                                              guest_ip="10.10.0.43",
                                              host_ip="10.10.0.44")
        qemu_large_queue_batch_itr.is_io_thread_nice = True
        qemu_large_queue_batch_itr.io_nice = 4
        qemu_large_queue_batch_itr.qemu_config["interrupt_mode"] = 1
        qemu_large_queue_batch_itr.qemu_config["drop_packet_every"] = 0
        qemu_large_queue_batch_itr.qemu_config["interrupt_mitigation_multiplier"] = 1000

        # qemu_e1000_best_itr = QemuE1000Max(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
        #                                guest_ip="10.10.0.43",
        #                                host_ip="10.10.0.44")
        # qemu_e1000_best_itr.exe = r"/homes/bdaviv/repos/e1000-improv/qemu-2.2.0/build/x86_64-softmmu/qemu-system-x86_64"

        # self.qemu_virtio_1g = Qemu(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
        #                            guest_ip="10.10.0.43",
        #                            host_ip="10.10.0.44")
        # self.qemu_virtio_1g.ethernet_dev = Qemu.QEMU_VIRTIO
        # self.qemu_virtio_1g.mem=1024
        #
        # self.qemu_e1000_1g = Qemu(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
        #                           guest_ip="10.10.0.43",
        #                           host_ip="10.10.0.44")
        # self.qemu_e1000_1g.ethernet_dev = Qemu.QEMU_E1000
        # self.qemu_e1000_1g.mem=

        qemu_arthur_arthur = QemuE1000Max(disk_path=r"../vms/ubuntu.img",
                                          guest_ip="10.10.0.43",
                                          host_ip="10.10.0.44")
        qemu_arthur_arthur.ethernet_dev = qemu_arthur_arthur.QEMU_E1000
        qemu_arthur_arthur.qemu_additionals = "-enable-e1000-pcix"
        qemu_arthur_arthur.exe = "/home/bdaviv/repos/e1000-improv/qemu-arthur/build/x86_64-softmmu/qemu-system-x86_64"
        qemu_arthur_arthur.qemu_config = {
            "no_tso_loop_on": 1,
            "no_tcp_csum_on": 1,
            "tdt_handle_on_iothread": 1,
            "interrupt_mitigation_multiplier": 10,
            "drop_packet_every": 8000,
            "drop_packet_every_avg_packet_size_min": 25000,
            "drop_packet_every_avg_packet_size_max": 60000,
            "zero_copy_on": 1,
        }

        qemu_ng_max = QemuE1000NG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                                  guest_ip="10.10.0.43",
                                  host_ip="10.10.0.44")

        qemu_large_ring_ng = QemuLargeRingNG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                                             guest_ip="10.10.0.43",
                                             host_ip="10.10.0.44")

        qemu_ng_max_nocsum = QemuE1000NG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                                         guest_ip="10.10.0.43",
                                         host_ip="10.10.0.44")
        qemu_ng_max_nocsum.e1000_options["NG_no_checksum"] = "off"

        qemu_large_ring_ng_nocsum = QemuLargeRingNG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                                                    guest_ip="10.10.0.43",
                                                    host_ip="10.10.0.44")
        qemu_large_ring_ng_nocsum.e1000_options["NG_no_checksum"] = "off"
        qemu_virtio_nice = Qemu(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                           guest_ip="10.10.0.43",
                           host_ip="10.10.0.44")
        qemu_virtio_nice.ethernet_dev = Qemu.QEMU_VIRTIO
        qemu_virtio_nice.is_io_thread_nice = True
        qemu_virtio_nice.io_nice = 5

        qemu_large_ring_ng_tso_offload = QemuLargeRingNG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                                             guest_ip="10.10.0.43",
                                             host_ip="10.10.0.44")
        qemu_large_ring_ng_tso_offload.e1000_options["NG_tso_offloading"] = "on"

        return [
                # (qemu_virtio, "virtio-net_baseline"),
                (qemu_virtio_drop_packets, "qemu_virtio_drop_packets"),
            # (qemu_e1000e, "qemu_e1000e"),
            # (qemu_virtio_latency, "virito-net_smart_latency"), # working?
            # (qemu_virtio_nice, "qemu_virtio_nice"),

            # (qemu_e1000_no_new_improv, "qemu_e1000_no_new_improv"),

            # (qemu_e1000_baseline, "e1000_baseline"),
            # (qemu_e1000_newest, "qemu_e1000_newest"),

                # (qemu_e1000_arthur, "e1000_10x_arthur"),
            # (qemu_arthur_arthur, "e1000_arthur_version"),
            #     (qemu_e1000_arthur_nice, "qemu_e1000_arthur_nice"),
            # (qemu_smart_itr, "qemu_smart_latency1"),
            # (qemu_smart_itr2, "qemu_smart_latency2"),
            # (qemu_smart_itr3, "e1000_smart_latency"),  # working?
            # (qemu_e1000_io_thread, "qemu_io_thread"),

            # (qemu_e1000_no_new_improv, "qemu_e1000_no_new_improv")
            # (qemu_large_queue, "qemu_large_ring_nice"),
            # (qemu_large_queue_itr6, "qemu_large_ring_nice_itr6"),
            # (qemu_large_queue_batch_itr, "qemu_large_queue_batch_itr"),

            # (qemu_e1000_best_itr, "qemu_e1000_best_itr"),
            # (self.qemu_virtio_1g, "qemu_virtio_1G"),
            # (self.qemu_e1000_1g, "qemu_e1000_1G"),
            # (qemu_ng_max, "qemu_ng_max"),
            (qemu_large_ring_ng, "qemu_large_ring_ng"),
            # (qemu_ng_max_nocsum, "qemu_ng_max_nocsum"),
            # (qemu_large_ring_ng_nocsum, "qemu_large_ring_ng_nocsum"),
            # (qemu_large_ring_ng_tso_offload, "qemu_large_ring_ng_tso_offload"),
        ]

    def test_func(self, vm: VM, vm_name: str, x_value: int):
        self.netperf.run_netperf(vm, vm_name, x_value, msg_size=x_value)


class TestCmpThroughput(QemuThroughputTest):
    def __init__(self, vms, *args, **kargs):
        self._test_vms = vms
        super().__init__(*args, **kargs)

    def get_vms(self):
        assert len({vm.name for vm in self._test_vms}) == len(self._test_vms)
        return [(deepcopy(vm), vm.name) for vm in self._test_vms]


class TestCmpThroughputTSO(TestCmpThroughput):
    NETPERF_CLS = NetPerfTcpTSO

    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        for sensor in self._sensors:
            sensor.graph.x_label = "TSO Frame Size [bytes]"

    def get_vms(self):
        vms = super().get_vms()
        # for vm, name in vms:
        #     vm.e1000_options["x-txburst"] = str(10)
        return vms

    def get_sensors(self):
        sensors = super().get_sensors()
        self.netperf.batch_size = 10
        return sensors


if __name__ == "__main__":
    test = QemuThroughputTest(15, retries=1)
    test.pre_run()
    test.run()
    test.post_run()


