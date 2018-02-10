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
BASE_DIR = r"/home/bdaviv/tmp/results/one_feature-graph"


def create_vms():
    vm_list = list()
    base_machine = QemuNG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                          guest_ip="10.10.0.43",
                          host_ip="10.10.0.44")
    e1000_baseline = deepcopy(base_machine)
    e1000_baseline.ethernet_dev = e1000_baseline.QEMU_E1000_BETTER
    e1000_baseline.name = "e1000-Baseline"

    # # virtio
    # vm_list.append(deepcopy(base_machine))
    # vm_list[-1].ethernet_dev = QemuNG.QEMU_VIRTIO
    # vm_list[-1].name = "virtio"

    # Checksum
    vm_list.append(deepcopy(e1000_baseline))
    vm_list[-1].e1000_options["NG_no_checksum"] = "on"
    vm_list[-1].name = "e1000-Checksum"

    # TSO
    vm_list.append(deepcopy(e1000_baseline))
    vm_list[-1].e1000_options["NG_no_tcp_seg"] = "on"
    vm_list[-1].name = "e1000-TSO"

    # interrupts
    vm_list.append(deepcopy(e1000_baseline))
    vm_list[-1].e1000_options["NG_interrupt_mul"] = 1
    vm_list[-1].e1000_options["NG_interrupt_mode"] = 1
    vm_list[-1].name = "e1000-Interrupts"

    # IO thread
    vm_list.append(deepcopy(e1000_baseline))
    vm_list[-1].e1000_options["NG_tx_iothread"] = "on"
    vm_list[-1].name = "e1000-IO_Thread"

    # PCI-X
    vm_list.append(deepcopy(e1000_baseline))
    vm_list[-1].e1000_options["NG_pcix"] = "on"
    vm_list[-1].name = "e1000-PCI-X"

    # Drop Packets
    vm_list.append(deepcopy(e1000_baseline))
    vm_list[-1].e1000_options["NG_drop_packet"] = "on"
    vm_list[-1].name = "e1000-Packet_Drop"

    # Vector_send
    vm_list.append(deepcopy(e1000_baseline))
    vm_list[-1].e1000_options["NG_vsend"] = "on"
    vm_list[-1].name = "e1000-Vector_Send"

    # nice
    vm_list.append(deepcopy(e1000_baseline))
    vm_list[-1].is_io_thread_nice = True
    vm_list[-1].io_nice = 5
    vm_list[-1].name = "e1000-nice"

    # # Large Queue
    vm_list.append(deepcopy(e1000_baseline))
    vm_list[-1].large_queue = True
    vm_list[-1].static_itc = True
    vm_list[-1].name = "e1000-Large_Queues"

    # virtio, Again
    # vm_list.append(deepcopy(vm_list[0]))
    # vm_list[-1].e1000_options["NG_drop_packet"] = "on"
    # vm_list[-1].name = "Virtio-Packet_Drop"

    return [e1000_baseline] + vm_list


if __name__ == "__main__":
    os.makedirs(BASE_DIR, exist_ok=True)
    test = TestCmpThroughput(create_vms(), RUNTIME, RETRIES, directory=BASE_DIR)
    test.pre_run()
    test.run()
    test.post_run()
