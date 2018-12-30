from os import path

from copy import deepcopy

import test_qemu_throughput
from sensors import netperf
from sensors.cpu import get_all_cpu_sensors, get_all_proc_cpu_sensors
from sensors.interrupts import InterruptSensor, QemuInterruptDelaySensor
from sensors.kvm_exits import KvmExitsSensor, KvmHaltExitsSensor
from sensors.packet_num2 import PacketTxBytesSensor, PacketTxPacketsSensor, PacketRxBytesSensor, PacketRxPacketsSensor
from sensors.qemu_batch import QemuBatchSizeSensor, QemuBatchDescriptorsSizeSensor, QemuBatchCountSensor
from sensors.sched import SchedSwitchSensor
from utils.graphs import Graph, RatioGraph, GraphErrorBarsGnuplot, FuncGraph, EmptyGraph
from utils.sensors import DummySensor


class LatencyTest(test_qemu_throughput.QemuThroughputTest):
    # def get_msg_sizes(self):
    #     return [(1, "1")]

    # def get_msg_sizes(self):
    #     return [
    #         (1500*88, "128K"),
    #         (1500*43, "64K"),
    #         (1500*22, "32k"),
    #         (1500*11, "16K"),
    #         (1500*5, "8k"),
    #         (1500*3, "4k"),
    #         (1500*2, "3K"),
    #         (1 * 2 ** 10, "1K"),
    #         (512, "512"),
    #         (256, "256"),
    #         (128, "128"),
    #         (64, "64"),
    #     ]

    def get_sensors(self):
        ret = super(LatencyTest, self).get_sensors
        self.netperf = netperf.NetPerfLatency(
            # GraphErrorBarsGnuplot
            Graph("Message size [bytes]", "Transactions/Sec",
                                  path.join(self.dir, "latency"),
                                  graph_title="Latency(%s sec)" % (self.netperf_runtime,)),
            runtime=self.netperf_runtime
        )
        # self.netperf.graph.script_filename = "gnuplot/plot_columns_latency"

        letency_us = DummySensor(
            FuncGraph(lambda x1: 1 / x1 * 1000 * 1000,
                      self.netperf.graph, EmptyGraph(),
                      "Message Size [bytes]", "uSec",
                      path.join(self.dir, "latency-time"),
                      graph_title="Latency (%s sec)" % (self.netperf_runtime,))
        )

        interrupt_sensor = InterruptSensor(
            Graph("msg size", "interrupt count (per sec)",
                  path.join(self.dir, "latency-interrupts"),
                  normalize=self.netperf_runtime)
        )

        kvm_exits = KvmExitsSensor(
            Graph("msg size", "exits count (per sec)",
                  path.join(self.dir, "latency-kvm_exits"),
                  normalize=self.netperf_runtime)
        )

        kvm_exits_ratio = DummySensor(
            RatioGraph(kvm_exits.graph, self.netperf.graph,
                       "msg size", "Exits per transaction",
                       path.join(self.dir, "latency-kvm_exits-ratio"),
                       graph_title="KVM exits per transaction")
        )

        kvm_halt_exits = KvmHaltExitsSensor(
            GraphErrorBarsGnuplot("msg size", "Halt exits count (per sec)",
                                  path.join(self.dir, "latency-kvm_halt_exits"),
                                  normalize=self.netperf_runtime)
        )

        kvm_halt_exits_ratio = DummySensor(
            RatioGraph(kvm_halt_exits.graph, self.netperf.graph,
                       "msg size", "Halt Exits per transaction",
                       path.join(self.dir, "latency-kvm_halt_exits-ratio"),
                       graph_title="KVM Haly exits per transaction")
        )

        packet_sensor_tx_bytes = PacketRxBytesSensor(
            Graph("msg size", "Total TX size(Mb)",
                  path.join(self.dir, "latency-tx_bytes"),
                  normalize=self.netperf_runtime * 1000 * 1000 / 8
                  )
        )
        packet_sensor_tx_packets = PacketRxPacketsSensor(
            Graph("msg size", "Total TX packets",
                  path.join(self.dir, "latency-tx_packets"),
                  normalize=self.netperf_runtime)
        )

        packet_sensor_avg_size = DummySensor(
            RatioGraph(packet_sensor_tx_bytes.graph, packet_sensor_tx_packets.graph,
                       "msg size", "TX Packet Size (KB)",
                       path.join(self.dir, "latency-tx_packet-size"),
                       normalize=8 * 0.001
                       )
        )

        interrupt_ratio = DummySensor(
            RatioGraph(interrupt_sensor.graph, self.netperf.graph,
                       "msg size", "Interrupts per transaction",
                       path.join(self.dir, "latency-interrupts-ratio"))
        )

        batch_size = QemuBatchSizeSensor(
            Graph("msg size", "Average batch size (in packets)",
                  path.join(self.dir, "latency-batch_size"))
        )

        batch_descriptos_size = QemuBatchDescriptorsSizeSensor(
            Graph("msg size", "Average batch size (in descriptors)",
                  path.join(self.dir, "latency-batch_descriptors_size"))
        )

        batch_count = QemuBatchCountSensor(
            Graph("msg size", "Average batch Count (per Sec)",
                  path.join(self.dir, "latency-batch_count"),
                  normalize=self.netperf_runtime)
        )

        interrupt_delay = QemuInterruptDelaySensor(
            Graph("msg size", "Average interrupt delay",
                  path.join(self.dir, "latency-interrupt_delay"))
        )

        sched_switch = SchedSwitchSensor(
            Graph("msg size", "Num of Scheduler switch (per sec)",
                  path.join(self.dir, "latency-context_switch"),
                  normalize=self.netperf_runtime
                  )
        )
        sched_switch_per_batch = DummySensor(
            RatioGraph(sched_switch.graph, self.netperf.graph,
                       "msg size", "Context switch per transaction",
                       path.join(self.dir, "latency-context_switch-ratio")
                       )
        )

        cpu_sensors = get_all_cpu_sensors(self.dir, "latency", self.netperf_runtime, exits_graph=kvm_exits.graph)
        cpu_proc_sensors = get_all_proc_cpu_sensors(self.dir, "latency", self.netperf_runtime, exits_graph=kvm_exits.graph)

        return [self.netperf,
                letency_us,
                interrupt_sensor,

                kvm_exits,
                kvm_halt_exits,
                kvm_exits_ratio,
                kvm_halt_exits_ratio,

                packet_sensor_tx_bytes,
                packet_sensor_tx_packets,
                packet_sensor_avg_size,

                batch_size,
                batch_descriptos_size,
                batch_count,

                interrupt_ratio,

                interrupt_delay,

                sched_switch,
                sched_switch_per_batch,

                ] + cpu_sensors + cpu_proc_sensors


class TestCmpLatency(LatencyTest):
    def __init__(self, vms, *args, **kargs):
        self._test_vms = vms
        super().__init__(*args, **kargs)

    def get_vms(self):
        assert len({vm.name for vm in self._test_vms}) == len(self._test_vms)
        return [(deepcopy(vm), vm.name) for vm in self._test_vms]


if __name__ == "__main__":
    test = LatencyTest(15, retries=1)
    test.pre_run()
    test.run()
    test.post_run()
