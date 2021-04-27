import os
import logging
from shutil import rmtree
from socket import gethostname
from copy import deepcopy
import itertools
import sys

from pathlib import Path

from test_qemu_latency import TestCmpLatency

PACKAGE_PARENT = '../..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from utils.vms import QemuNG
from test_qemu_throughput import QemuThroughputTest, TestCmpThroughputTSO

RUNTIME = 15
RETRIES = 3
BASE_DIR = r"/home-local/bdaviv/tmp/results/step-compare/{hostname}".format(
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
    base_machine = QemuNG(disk_path=r"../vms/ubuntu.img",
                          guest_ip="10.10.0.43",
                          host_ip="10.10.0.44")

    # virtio
    virtio = deepcopy(base_machine)
    virtio.ethernet_dev = QemuNG.QEMU_VIRTIO
    virtio.name = "virtio"

    vm_list_virtio.append(virtio)

    vm_list_virtio.append(deepcopy(vm_list_virtio[-1]))
    vm_list_virtio[-1].e1000_options["NG_notify_batch"] = "on"
    vm_list_virtio[-1].name = "virtio-batchInterrupts"
    #
    # vm_list_virtio.append(deepcopy(vm_list_virtio[-1]))
    # vm_list_virtio[-1].disable_kvm_poll = True
    # vm_list_virtio[-1].name = "virtio-noPoll"

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
    e1000_before_interrupt_step = vm_list_e1000[-1]

    # Interrupts
    vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    # vm_list_e1000[-1].e1000_options["NG_interrupt_mode"] = 3
    # vm_list_e1000[-1].name = "e1000-Interrupt_adaptive"
    vm_list_e1000[-1].e1000_options["NG_parahalt"] = "on"
    vm_list_e1000[-1].e1000_options["NG_interrupt_mode"] = 0
    vm_list_e1000[-1].e1000_options["NG_interrupt_mul"] = 0
    vm_list_e1000[-1].e1000_options["mitigation"] = "off"
    vm_list_e1000[-1].name = "e1000-send_on_halt"
    e1000_send_on_halt = vm_list_e1000[-1]

    # Disable always flush TX queue RDT write
    vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    vm_list_e1000[-1].e1000_options["NG_disable_rdt_jump"] = "on"
    vm_list_e1000[-1].name = "e1000-NoRDTJump"

    # Vector_send
    vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    vm_list_e1000[-1].e1000_options["NG_vsend"] = "on"
    vm_list_e1000[-1].name = "e1000-zero_copy"

    # PCI-X
    vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    vm_list_e1000[-1].e1000_options["NG_pcix"] = "on"
    vm_list_e1000[-1].name = "e1000-high_mem_dma"

    # # Eliminate ITR
    # vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    # vm_list_e1000[-1].static_itr = True
    # vm_list_e1000[-1].ethernet_dev = vm_list_e1000[-1].QEMU_E1000_BETTER
    # vm_list_e1000[-1].name = "e1000-NoITR"

    # Guest TX orphan
    vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    vm_list_e1000[-1].guest_e1000_ng_flag = 1
    vm_list_e1000[-1].name = "e1000-tx_skb_orphan"

    # halt
    e1000_int_halt = deepcopy(vm_list_e1000[-1])
    e1000_int_halt.e1000_options["NG_parahalt"] = "on"
    e1000_int_halt.e1000_options["NG_interrupt_mode"] = 0
    e1000_int_halt.e1000_options["NG_interrupt_mul"] = 0
    e1000_int_halt.e1000_options["mitigation"] = "off"
    e1000_int_halt.name = "e1000-interrupts"

    # Adaptive
    e1000_adaptive = deepcopy(vm_list_e1000[-1])
    e1000_adaptive.e1000_options["NG_parahalt"] = "off"
    e1000_adaptive.e1000_options["mitigation"] = "on"
    e1000_adaptive.e1000_options["NG_interrupt_mul"] = 1
    e1000_adaptive.e1000_options["NG_interrupt_mode"] = 3
    e1000_adaptive.name = "e1000-adaptive-after"

    e1000_adaptive_partial = deepcopy(e1000_send_on_halt)
    e1000_adaptive_partial.e1000_options["NG_parahalt"] = "off"
    e1000_adaptive_partial.e1000_options["mitigation"] = "on"
    e1000_adaptive_partial.e1000_options["NG_interrupt_mul"] = 1
    e1000_adaptive_partial.e1000_options["NG_interrupt_mode"] = 3
    e1000_adaptive_partial.name = "e1000-adaptive"

    # Adaptive1
    e1000_adaptive1 = deepcopy(vm_list_e1000[-1])
    e1000_adaptive1.e1000_options["NG_parahalt"] = "off"
    e1000_adaptive1.e1000_options["NG_interrupt_mode"] = 2
    e1000_adaptive1.e1000_options["NG_interrupt_mul"] = 1
    e1000_adaptive1.e1000_options["mitigation"] = "on"
    e1000_adaptive1.name = "e1000-adaptive-before"

    # # Eliminate TXDW - ???
    # vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    # vm_list_e1000[-1].e1000_options["NG_disable_TXDW"] = "on"
    # vm_list_e1000[-1].name = "e1000-NoTXDW"

    # # recall RXT0 when setting RDT - ???
    # vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    # vm_list_e1000[-1].e1000_options["NG_recall_RXT0"] = "on"
    # vm_list_e1000[-1].name = "e1000-RecallRXT0"

    # # Fast IOthread kick
    # vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    # vm_list_e1000[-1].e1000_options["NG_fast_iothread_kick"] = "on"
    # vm_list_e1000[-1].name = "e1000-fastIothread"

    # # Guest TX clean - ???
    # vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    # vm_list_e1000[-1].guest_e1000_ng_flag |= 2
    # vm_list_e1000[-1].name = "e1000-txClean"

    # # Guest disable nic stats
    # vm_list_e1000.append(deepcopy(vm_list_e1000[-1]))
    # vm_list_e1000[-1].guest_e1000_ng_flag |= 4
    # vm_list_e1000[-1].name = "e1000-noStats"

    pairs.extend(pairwise(vm_list_e1000))

    pairs.append((vm_list_e1000[-1], e1000))
    pairs.append((vm_list_e1000[-1], vm_list_virtio[-1]))
    pairs.append((vm_list_e1000[-1], e1000_int_halt))

    pairs.append((e1000_int_halt, e1000_adaptive))
    pairs.append((e1000_send_on_halt, e1000_adaptive_partial))
    pairs.append((e1000_adaptive_partial, e1000_before_interrupt_step))

    pairs.append((virtio, vm_list_e1000[-1]))

    # return vm_list_virtio + vm_list_e1000 + [e1000_int_halt, e1000_adaptive], pairs
    # vms = vm_list_virtio + vm_list_e1000 + [e1000_int_halt, e1000_adaptive, e1000_adaptive_partial]
    vms = vm_list_virtio + vm_list_e1000 + [e1000_adaptive, e1000_adaptive_partial]
    for vm in vms:
        vm.enabled = False
    # e1000_adaptive_partial.enabled = True

    return vms, pairs

    # return (vm_list_e1000[-1], e1000_adaptive, e1000_adaptive1), \
    #        ((vm_list_e1000[-1], e1000_adaptive),
    #          (vm_list_e1000[-1], e1000_adaptive1),
    #          (e1000_adaptive, e1000_adaptive1),
    #         )


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

    # for vm in vms:
    #     vm.enabled = False

    # pairs = list(pairs)
    # vms = list(pairs[0]) + [vms[2]]
    # pairs = [pairs[0]]

    additional_x = [
        (1448, "1.5K")
    ]

    # for vm in vms:
    #     vm.enabled = False

    test_clss = [
        (TestCmpThroughput, "throughput"),
        (TestCmpLatency, "latency"),
        (TestCmpThroughputTSO, "throughput-TSO"),
    ]

    for cls, subdir in test_clss:
        root_logger.info("Starting test %s", cls.__name__)
        test_dir = os.path.join(BASE_DIR, subdir)
        os.makedirs(test_dir, exist_ok=True)

        for d in Path(test_dir).iterdir():
            if d.is_dir():
                rmtree(str(d))

        test = cls(vms, RUNTIME, RETRIES, directory=test_dir,
                   additional_x=additional_x)
        test.pre_run()
        test.run()
        test.post_run()

        for num, current_vms in enumerate(pairs):
            current_vms = list(reversed(current_vms))
            # print(num, [vm.name for vm in current_vms])
            name = "---".join((vm.name for vm in current_vms))
            d = os.path.join(test_dir, "{:02}-{}".format(num, name))
            os.makedirs(d, exist_ok=True)
            test.create_sensor_graphs(vm_names_to_include=[vm.name for vm in current_vms],
                                      folder=d)

if __name__ == "__main__":
    main()
