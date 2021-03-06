import logging
import os
import socket
from copy import deepcopy
from pathlib import Path
from shutil import rmtree

from test_qemu_latency import TestCmpLatency
from utils.vms import QemuNG, Qemu, QemuE1000Max, QemuE1000NG, QemuE1000NGBest, QemuE1000NGAdaptive
from test_qemu_throughput import TestCmpThroughput, TestCmpThroughputTSO

RUNTIME = 15
# RUNTIME = 30
RETRIES = 3
BASE_DIR = r"../tmp/results/test-finals/{hostname}".format(
    hostname=socket.gethostname()
)


def create_vms():
    base = QemuNG(disk_path=r"../vms/ubuntu-20.img",
                  guest_ip="10.10.0.43",
                  host_ip="10.10.0.44")

    e1000_baseline = deepcopy(base)
    e1000_baseline.ethernet_dev = e1000_baseline.QEMU_E1000
    e1000_baseline.name = "E1000-baseline"

    virtio = deepcopy(base)
    virtio.ethernet_dev = virtio.QEMU_VIRTIO
    virtio.name = "virtio"

    virtio_vhost = deepcopy(virtio)
    virtio_vhost.name += "_vhost"
    virtio_vhost.vhost = True

    virtio_batch = deepcopy(virtio)
    virtio_batch.name = "virtio_batch"
    virtio_batch.e1000_options["NG_notify_batch"] = "on"

    e1000_para_halt = QemuE1000NGBest(disk_path=r"../vms/ubuntu-20.img",
                                      guest_ip="10.10.0.43",
                                      host_ip="10.10.0.44")
    e1000_para_halt.name = "e1000-parahalt"

    regular_vms = [
        # e1000_baseline,

        virtio,
        #virtio_batch,

        #e1000_para_halt,
    ]

    return tuple(regular_vms)


if __name__ == "__main__":
    os.makedirs(BASE_DIR, exist_ok=True)
    log_file = os.path.join(BASE_DIR, "log")
    if os.path.exists(log_file):
        os.unlink(log_file)
    root_logger = logging.getLogger()
    root_logger.addHandler(
        logging.FileHandler(log_file)
    )
    root_logger.setLevel(logging.DEBUG)

    additional_x = [
        (1448, "1.5K")
    ]

    test_clss = [
        (TestCmpThroughput, "throughput"),
        (TestCmpLatency, "latency"),
        (TestCmpThroughputTSO, "throughput-TSO"),
    ]

    for cls, subdir in test_clss:
        root_logger.info("Starting test %s", cls.__name__)
        test_dir = os.path.join(BASE_DIR, subdir)
        os.makedirs(test_dir, exist_ok=True)
        test = cls(create_vms(), RUNTIME, RETRIES, directory=test_dir,
                   additional_x=additional_x)
        test.pre_run()
        test.run()
        test.post_run()

