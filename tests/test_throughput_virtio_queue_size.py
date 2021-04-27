import logging
import os
import shutil
from copy import deepcopy
import sys

PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from utils.vms import QemuNG, Qemu, QemuE1000Max, QemuE1000NG
from test_qemu_throughput import TestCmpThroughput

# RUNTIME = 8
RUNTIME = 15
RETRIES = 1
BASE_DIR = r"../tmp/results/test-results"

def create_vms():
    base = QemuNG(disk_path=r"../vms/ubuntu.img",
                  guest_ip="10.10.0.43",
                  host_ip="10.10.0.44")

    virtio = deepcopy(base)
    virtio.ethernet_dev = virtio.QEMU_VIRTIO
    virtio.name = "virtio"

    virtio_drop = deepcopy(virtio)
    virtio_drop.name = "virtio_drop"
    virtio_drop.e1000_options["NG_drop_packet"] = "on"

    virtio_q_256 = deepcopy(virtio)
    virtio_q_256.name = "virtio-Q256"
    virtio_q_256.nic_additionals = ",tx_queue_size=256"

    virtio_q_128 = deepcopy(virtio)
    virtio_q_128.name = "virtio-Q128"
    virtio_q_128.nic_additionals = ",tx_queue_size=128"

    virtio_q_64 = deepcopy(virtio)
    virtio_q_64.name = "virtio-Q64"
    virtio_q_64.nic_additionals = ",tx_queue_size=64"

    virtio_q_32 = deepcopy(virtio)
    virtio_q_32.name = "virtio-Q32"
    virtio_q_32.nic_additionals = ",tx_queue_size=32"

    virtio_q_16 = deepcopy(virtio)
    virtio_q_16.name = "virtio-Q16"
    virtio_q_16.nic_additionals = ",tx_queue_size=16"

    return (
        virtio,
        virtio_drop,

        virtio_q_256,
        virtio_q_128,
        virtio_q_64,
        virtio_q_32,
        virtio_q_16
    )


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

    test = TestCmpThroughput(create_vms(), RUNTIME, RETRIES, directory=BASE_DIR)
    test.pre_run()
    test.run()
    test.post_run()
