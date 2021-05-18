import os
import sys
import logging
import itertools
from copy import deepcopy

PACKAGE_PARENT = '../..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
print(SCRIPT_DIR)
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from utils.vms import QemuNG
from test_qemu_throughput import TestCmpThroughput

RUNTIME = 30
RETRIES = 1
BASE_DIR = r"../tmp/results/iothread+one_feature"


def create_vms():
    vm_list = list()
    base_machine = QemuNG(disk_path=r"../vms/ubuntu-20.img",
                          guest_ip="10.10.0.43",
                          host_ip="10.10.0.44")
    e1000_baseline = deepcopy(base_machine)
    e1000_baseline.ethernet_dev = e1000_baseline.QEMU_E1000_BETTER
    e1000_baseline.name = "e1000-Baseline"

    iothread = deepcopy(e1000_baseline)
    iothread.name = "e1000-iothread"
    iothread.e1000_options["NG_tx_iothread"] = "on"


    # # virtio
    # vm_list.append(deepcopy(base_machine))
    # vm_list[-1].ethernet_dev = QemuNG.QEMU_VIRTIO
    # vm_list[-1].name = "virtio"

    # Checksum
    vm_list.append(deepcopy(iothread))
    vm_list[-1].e1000_options["NG_no_checksum"] = "on"
    vm_list[-1].name = "e1000-Checksum"

    # TSO
    vm_list.append(deepcopy(iothread))
    vm_list[-1].e1000_options["NG_no_tcp_seg"] = "on"
    vm_list[-1].name = "e1000-TSO"

    # interrupts
    vm_list.append(deepcopy(iothread))
    vm_list[-1].e1000_options["NG_interrupt_mul"] = 1
    vm_list[-1].e1000_options["NG_interrupt_mode"] = 1
    vm_list[-1].name = "e1000-Interrupts"

    # IO thread
    # vm_list.append(deepcopy(iothread))
    # vm_list[-1].e1000_options["NG_tx_iothread"] = "on"
    # vm_list[-1].name = "e1000-IO_Thread"

    # PCI-X
    vm_list.append(deepcopy(iothread))
    vm_list[-1].e1000_options["NG_pcix"] = "on"
    vm_list[-1].name = "e1000-PCI-X"

    # Drop Packets
    vm_list.append(deepcopy(iothread))
    vm_list[-1].e1000_options["NG_drop_packet"] = "on"
    vm_list[-1].name = "e1000-Packet_Drop"

    # Vector_send
    vm_list.append(deepcopy(iothread))
    vm_list[-1].e1000_options["NG_vsend"] = "on"
    vm_list[-1].name = "e1000-Vector_Send"

    # nice
    vm_list.append(deepcopy(iothread))
    vm_list[-1].is_io_thread_nice = True
    vm_list[-1].io_nice = 5
    vm_list[-1].name = "e1000-nice"

    # # Large Queue
    vm_list.append(deepcopy(iothread))
    vm_list[-1].large_queue = True
    vm_list[-1].static_itc = True
    vm_list[-1].name = "e1000-Large_Queues"

    # virtio, Again
    # vm_list.append(deepcopy(vm_list[0]))
    # vm_list[-1].e1000_options["NG_drop_packet"] = "on"
    # vm_list[-1].name = "Virtio-Packet_Drop"

    return zip(vm_list, [iothread] * len(vm_list))


def pairwise(iterable):
    """s -> (s0,s1), (s1,s2), (s2, s3), ..."""
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


def main(skip=0, end=99):
    os.makedirs(BASE_DIR, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.addHandler(
        logging.FileHandler(os.path.join(BASE_DIR, "log"))
    )
    root_logger.setLevel(logging.DEBUG)

    for num, vms in enumerate(create_vms()):
        if num < skip:
            continue
        if num >= end:
            break

        name = "+".join((vm.name for vm in vms))
        root_logger.info("Starting %s", name)
        d = os.path.join(BASE_DIR, "{}-{}".format(num, name))
        os.makedirs(d, exist_ok=True)
        test = TestCmpThroughput(vms, RUNTIME, RETRIES, directory=d)
        test.pre_run()
        test.run()
        test.post_run()


if __name__ == "__main__":
    main()
