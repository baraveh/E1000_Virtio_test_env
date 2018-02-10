from test_qemu_latency import LatencyTest
from test_qemu_throughput import QemuThroughputTest


def main(runtime=3, retries=1):
    for cls in (QemuThroughputTest, LatencyTest):
        test = cls(runtime, retries=retries)
        test.pre_run()
        test.run()
        test.post_run()


if __name__ == '__main__':
    main(runtime=5, retries=1)
