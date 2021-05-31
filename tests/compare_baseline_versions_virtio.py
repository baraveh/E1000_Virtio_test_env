import os
from copy import deepcopy
import sys

PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from utils.vms import QemuNG
from test_qemu_throughput import TestCmpThroughput

RUNTIME = 15
RETRIES = 1
BASE_DIR = r"../tmp/results/virtio_baseline"


def create_vms():
    OLD_QEMU = r"../qemu/build/qemu-system-x86_64"
    OLD_KERNEL = r"/home/bdaviv/repos/e1000-improv/linux-3.13.0/arch/x86/boot/bzImage"
    OLD_INITRD = r"../vms/initrd.img"
    base_machine = QemuNG(disk_path=r"../vms/ubuntu-20.img",
                          guest_ip="10.10.0.43",
                          host_ip="10.10.0.44")
    base_machine.ethernet_dev = base_machine.QEMU_VIRTIO

    # e1000_QnGn_better = deepcopy(base_machine)
    # e1000_QnGn_better.name = "QnGn-newer"
    # e1000_QnGn_better.ethernet_dev = e1000_QnGn_better.QEMU_E1000_BETTER

    virtio_QnGn = deepcopy(base_machine)
    virtio_QnGn.name = "QnGn"

    virtio_QnGo = deepcopy(base_machine)
    virtio_QnGo.name = 'QnGo'
    virtio_QnGo.kernel = OLD_KERNEL
    virtio_QnGo.initrd = OLD_INITRD

    virtio_QoGn = deepcopy(base_machine)
    virtio_QoGn.name = 'QoGn'
    virtio_QoGn.bootwait = 30
    virtio_QoGn.exe = OLD_QEMU

    virtio_QoGo = deepcopy(base_machine)
    virtio_QoGo.name = 'QoGo'
    virtio_QoGo.bootwait = 30
    virtio_QoGo.exe = OLD_QEMU
    virtio_QoGo.kernel = OLD_KERNEL
    virtio_QoGo.initrd = OLD_INITRD

    return (
        # e1000_QnGn_better,
        virtio_QnGn,
        virtio_QnGo,
        virtio_QoGn,
        virtio_QoGo
    )


if __name__ == "__main__":
    os.makedirs(BASE_DIR, exist_ok=True)
    test = TestCmpThroughput(create_vms(), RUNTIME, RETRIES, directory=BASE_DIR)
    test.pre_run()
    test.run()
    test.post_run()
