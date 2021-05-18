import logging
import os
import sys

PACKAGE_PARENT = '../..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from utils.vms import Qemu, QemuE1000Max, QemuE1000NG, QemuLargeRingNG

# ORIG_QEMU = r"qemu-system-x86_64"
# ORIG_QEMU = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build-trace/x86_64-softmmu/qemu-system-x86_64"
ORIG_QEMU = r"qemu-system-x86_64"
ORIG_QEMU_TRACE = r"/homes/bdaviv/repos/msc-ng/qemu-ng/build-trace/x86_64-softmmu/qemu-system-x86_64"

TMP_QEMU = r"/tmp/qemu-system-x86_64"
Qemu.QEMU_EXE = ORIG_QEMU

TMP_DIR = r"/tmp/traces"

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def main(trace=False):
    vm = QemuE1000NG(disk_path=r"../vms/ubuntu-20.img",
                     guest_ip="10.10.0.43",
                     host_ip="10.10.0.44")

    if trace:
        vm.exe = ORIG_QEMU_TRACE

    vm.setup()
    vm.run()

    input("Press any enter to close VM")
    vm.teardown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", default=False, action="store_true")

    args = parser.parse_args()

    main(trace=args.trace)
