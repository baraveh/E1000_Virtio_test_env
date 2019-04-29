import os
import logging
from socket import gethostname
from copy import deepcopy
import itertools
import sys

PACKAGE_PARENT = '../..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from utils.vms import QemuNG
from test_qemu_throughput import QemuThroughputTest

RUNTIME = 15
RETRIES = 1
BASE_DIR = r"/home/bdaviv/tmp/results/step-compare/{hostname}".format(
    hostname=gethostname()
)


def pairwise(iterable):
    """s -> (s0,s1), (s1,s2), (s2, s3), ..."""
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(b, a)


def create_vms():
    pairs = list()
    vm_list_e1000 = list()
    vm_list_virtio = list()
    base_machine = QemuNG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                          guest_ip="10.10.0.43",
                          host_ip="10.10.0.44")

    # virtio
    virtio = deepcopy(base_machine)
    virtio.ethernet_dev = QemuNG.QEMU_VIRTIO
    virtio.name = "virtio"

    vm_list_virtio.append(virtio)

    vm_list_virtio.append(deepcopy(vm_list_virtio[-1]))
    vm_list_virtio[-1].disable_kvm_poll = True
    vm_list_virtio[-1].name = "virtio-noPoll"

    vm_list_virtio.append(deepcopy(vm_list_virtio[-1]))
    vm_list_virtio[-1].e1000_options["NG_notify_batch"] = "on"
    vm_list_virtio[-1].name = "virtio-batchInterrupts"

    pairs.extend(pairwise(vm_list_virtio))

    # e1000 baseline
    e1000 = deepcopy(base_machine)
    e1000.ethernet_dev = QemuNG.QEMU_E1000_BETTER
    e1000.name = "e1000-Baseline"

    pairs.append((virtio, e1000))

    vm_list_e1000.append(deepcopy(e1000))

    # Checksum
    vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    vm_list_e1000[-1].e1000_options["NG_no_checksum"] = "on"
    vm_list_e1000[-1].name = "e1000-Checksum"

    # TSO
    vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    vm_list_e1000[-1].e1000_options["NG_no_tcp_seg"] = "on"
    vm_list_e1000[-1].name = "e1000-TSO"

    # IO thread
    vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    vm_list_e1000[-1].e1000_options["NG_tx_iothread"] = "on"
    vm_list_e1000[-1].name = "e1000-IOThread"

    # PCI-X
    vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    vm_list_e1000[-1].e1000_options["NG_pcix"] = "on"
    vm_list_e1000[-1].name = "e1000-PCI-X"

    # Vector_send
    vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    vm_list_e1000[-1].e1000_options["NG_vsend"] = "on"
    vm_list_e1000[-1].name = "e1000-VectorSend"

    # Eliminate ITR
    vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    vm_list_e1000[-1].static_itr = True
    vm_list_e1000[-1].ethernet_dev = vm_list_e1000[-1].QEMU_E1000_BETTER
    vm_list_e1000[-1].name = "e1000-NoITR"



    pairs.extend(pairwise(vm_list_e1000))

    return vm_list_virtio + vm_list_e1000, pairs


class TestCmpThroughput(QemuThroughputTest):
    def __init__(self, vms, *args, **kargs):
        self._test_vms = vms
        super().__init__(*args, **kargs)

    def get_vms(self):
        return [(deepcopy(vm), vm.name) for vm in self._test_vms]


def main(skip=0, end=99):
    os.makedirs(BASE_DIR, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.addHandler(
        logging.FileHandler(os.path.join(BASE_DIR, "log"))
    )
    root_logger.setLevel(logging.DEBUG)

    vms, pairs = create_vms()

    test = TestCmpThroughput(vms, RUNTIME, RETRIES, directory=BASE_DIR)
    test.pre_run()
    test.run()
    test.post_run()

    for num, current_vms in enumerate(pairs):
        name = "+".join((vm.name for vm in vms))
        d = os.path.join(BASE_DIR, "{}-{}".format(num, name))
        test.create_sensor_graphs(vm_names_to_include=[vm.name for vm in current_vms],
                                  folder=d)

    # for num, vms in enumerate(create_vms()):
    #     if num < skip:
    #         continue
    #     if num >= end:
    #         break
    #
    #     name = "+".join((vm.name for vm in vms))
    #     root_logger.info("Starting %s", name)
    #     d = os.path.join(BASE_DIR, "{}-{}".format(num, name))
    #     os.makedirs(d, exist_ok=True)
    #     test = TestCmpThroughput(vms, RUNTIME, RETRIES, directory=d)
    #     test.pre_run()
    #     test.run()
    #     test.post_run()


if __name__ == "__main__":
    main()
