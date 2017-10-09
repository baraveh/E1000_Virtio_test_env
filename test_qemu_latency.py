from os import path

import test_qemu_throughput
from sensors import netperf
from sensors.cpu import get_all_cpu_sensors
from sensors.interrupts import InterruptSensor
from sensors.kvm_exits import KvmExitsSensor, KvmHaltExitsSensor
from sensors.packet_num2 import PacketTxBytesSensor, PacketTxPacketsSensor, PacketRxBytesSensor, PacketRxPacketsSensor
from utils.graphs import Graph, RatioGraph, GraphErrorBarsGnuplot
from utils.sensors import DummySensor


class LatencyTest(test_qemu_throughput.QemuRegularTest):
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
            GraphErrorBarsGnuplot("Message size [bytes]", "Transactions/Sec",
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
                ] + cpu_sensors


if __name__ == "__main__":
    test = LatencyTest(15, retries=1)
    test.pre_run()
    test.run()
    test.post_run()
