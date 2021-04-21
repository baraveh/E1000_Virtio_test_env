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
BASE_DIR = r"/home/bdaviv/tmp/results/e1000_baseline"


def create_vms():
    OLD_QEMU = r"/usr/lib/qemu"
    OLD_KERNEL = r"/home/bdaviv/repos/e1000-improv/linux-3.13.0/arch/x86/boot/bzImage"
    OLD_INITRD = r"/homes/bdaviv/repos/e1000-improv/vms/initrd.img-3.13.11-ckt22+"

    QEMU_MIX = r"/homes/bdaviv/repos/msc-ng/qemu-orig-git/build/x86_64-softmmu/qemu-system-x86_64"
    base_machine = QemuNG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                          guest_ip="10.10.0.43",
                          host_ip="10.10.0.44")
    base_machine.ethernet_dev = base_machine.QEMU_E1000

    e1000_QnGn_better = deepcopy(base_machine)
    e1000_QnGn_better.name = "QnGn-newer"
    e1000_QnGn_better.ethernet_dev = e1000_QnGn_better.QEMU_E1000_BETTER

    e1000_QnGn_regular = deepcopy(base_machine)
    e1000_QnGn_regular.name = "QnGn"

    e1000_QnGo = deepcopy(base_machine)
    e1000_QnGo.name = 'QnGo'
    e1000_QnGo.kernel = OLD_KERNEL
    e1000_QnGo.initrd = OLD_INITRD

    e1000_QoGn = deepcopy(base_machine)
    e1000_QoGn.name = 'QoGn'
    e1000_QoGn.bootwait = 30
    e1000_QoGn.exe = OLD_QEMU

    e1000_QoGo = deepcopy(base_machine)
    e1000_QoGo.name = 'QoGo'
    e1000_QoGo.bootwait = 60
    e1000_QoGo.exe = OLD_QEMU
    e1000_QoGo.kernel = OLD_KERNEL
    e1000_QoGo.initrd = OLD_INITRD

    e1000_qemu_mix = deepcopy(e1000_QnGn_regular)
    e1000_qemu_mix.name = 'QemuMix'
    e1000_qemu_mix.exe = QEMU_MIX

    return (
        # e1000_QnGn_better,
        e1000_QnGn_regular,
        # e1000_QnGo,
        # e1000_QoGn,
        # e1000_QoGo,

        e1000_qemu_mix,
    )


if __name__ == "__main__":
    os.makedirs(BASE_DIR, exist_ok=True)
    test = TestCmpThroughput(create_vms(), RUNTIME, RETRIES, directory=BASE_DIR)
    test.pre_run()
    test.run()
    test.post_run()
