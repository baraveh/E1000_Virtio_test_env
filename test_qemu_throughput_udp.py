from os import path

import test_qemu_throughput
from sensors.netperf import NetPerfUDP
from utils.graphs import GraphErrorBarsGnuplot


class UDPThroughputTest(test_qemu_throughput.QemuThroughputTest):
    def __init__(self, *args, **kargs):
        super(UDPThroughputTest, self).__init__(*args, **kargs)

        netperf_graph = GraphErrorBarsGnuplot("msg size", "throughput",
                                              path.join(self.DIR, "throughput"),
                                              graph_title="UDP Throughput")
        self.netperf = NetPerfUDP(netperf_graph, self.netperf_runtime)
        self._sensors[0] = self.netperf

    def get_x_categories(self):
        return [
            (64, "64"),
            # (128, "128"),
            (256, "256"),
            # (512, "512"),
            (1 * 2 ** 10, "1K"),
            # (2 * 2 ** 10, "2K"),
            (4 * 2 ** 10, "4K"),
            # (8 * 2 ** 10, "8K"),
            (16 * 2 ** 10, "16K"),
            # (32 * 2 ** 10, "32K"),
            (64 * 2 ** 10 - 14-20-8-10, "64K"),
        ]


if __name__ == "__main__":
    test = UDPThroughputTest(15, retries=1)
    test.pre_run()
    test.run()
    test.post_run()