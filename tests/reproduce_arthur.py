import os
from copy import deepcopy
import sys

PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from utils.vms import QemuNG, Qemu, QemuE1000Max
from test_qemu_throughput import TestCmpThroughput

RUNTIME = 15
RETRIES = 3
BASE_DIR = r"/home/bdaviv/tmp/results/arthur-results"


def create_vms():
    OLD_QEMU = r"/home/bdaviv/repos/e1000-improv/qemu-arthur/build/x86_64-softmmu/qemu-system-x86_64"
    OLD_KERNEL = r"/home/bdaviv/repos/e1000-improv/linux-3.13.0/arch/x86/boot/bzImage"
    OLD_INITRD = r"/homes/bdaviv/repos/e1000-improv/vms/initrd.img-3.13.11-ckt22+"

    base = Qemu(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                guest_ip="10.10.0.43",
                host_ip="10.10.0.44")
    base.kernel = OLD_KERNEL
    base.initrd = OLD_INITRD
    base.exe = OLD_QEMU

    e1000_baseline = deepcopy(base)
    e1000_baseline.ethernet_dev = e1000_baseline.QEMU_E1000
    e1000_baseline.name = "E1000-baseline"

    virtio = deepcopy(base)
    virtio.ethernet_dev = virtio.QEMU_VIRTIO
    virtio.name = "virtio"

    virtio_drop = deepcopy(virtio)
    virtio_drop.name = "virtio_drop"
    virtio_drop.qemu_config["drop_packet_every"] = 8000
    virtio_drop.qemu_config["drop_packet_every_avg_packet_size_min"] = 9000
    virtio_drop.qemu_config["drop_packet_every_avg_packet_size_max"] = 62000

    e1000_arthur = QemuE1000Max(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                                guest_ip="10.10.0.43",
                                host_ip="10.10.0.44")
    e1000_arthur.kernel = OLD_KERNEL
    e1000_arthur.initrd = OLD_INITRD
    e1000_arthur.exe = OLD_QEMU
    e1000_arthur.nic_additionals = ''
    e1000_arthur.qemu_additionals = '-enable-e1000-pcix'
    e1000_arthur.name = "E1000-arthur"
    e1000_arthur.qemu_config["drop_packet_every"] = 8000
    e1000_arthur.qemu_config["drop_packet_every_avg_packet_size_min"] = 25000
    e1000_arthur.qemu_config["drop_packet_every_avg_packet_size_max"] = 60000

    return (
        e1000_baseline,
        virtio,
        virtio_drop,
        e1000_arthur
    )


if __name__ == "__main__":
    os.makedirs(BASE_DIR, exist_ok=True)
    test = TestCmpThroughput(create_vms(), RUNTIME, RETRIES, directory=BASE_DIR)
    test.pre_run()
    test.run()
    test.post_run()
