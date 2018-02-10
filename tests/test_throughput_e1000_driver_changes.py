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
BASE_DIR = r"/home/bdaviv/tmp/results/test-results"

OLD_QEMU = r"/home/bdaviv/repos/e1000-improv/qemu-arthur/build/x86_64-softmmu/qemu-system-x86_64"
OLD_KERNEL = r"/home/bdaviv/repos/e1000-improv/linux-3.13.0/arch/x86/boot/bzImage"
OLD_INITRD = r"/homes/bdaviv/repos/e1000-improv/vms/initrd.img-3.13.11-ckt22+"


def create_vms():
    base = QemuNG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                  guest_ip="10.10.0.43",
                  host_ip="10.10.0.44")

    e1000_baseline = deepcopy(base)
    e1000_baseline.ethernet_dev = e1000_baseline.QEMU_E1000
    e1000_baseline.name = "E1000-baseline"

    e1000_best_orig_driver = QemuE1000NG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                             guest_ip="10.10.0.43",
                             host_ip="10.10.0.44")
    e1000_best_orig_driver.name = "E1000-original"
    e1000_best_orig_driver.is_io_thread_nice = False
    e1000_best_orig_driver.e1000_options["NG_interrupt_mul"] = 10
    e1000_best_orig_driver.e1000_options["NG_interrupt_mode"] = 0
    e1000_best_orig_driver.bootwait = 10

    e1000_clean_tx = deepcopy(e1000_best_orig_driver)
    e1000_clean_tx.kernel_cmdline_additional = "e1000.NG_flags=2"
    e1000_clean_tx.name = "E1000-clean_tx"

    e1000_skb_orphan = deepcopy(e1000_best_orig_driver)
    e1000_skb_orphan.kernel_cmdline_additional = "e1000.NG_flags=1"
    e1000_skb_orphan.name = "E1000-skb_orphan"

    e1000_both = deepcopy(e1000_best_orig_driver)
    e1000_both.kernel_cmdline_additional = "e1000.NG_flags=3"
    e1000_both.name = "E1000-both"

    return (
        e1000_baseline,
        e1000_best_orig_driver,
        e1000_clean_tx,
        e1000_skb_orphan,
        e1000_both
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
