import logging
import os
from copy import deepcopy
import socket
from utils.vms import QemuNG, Qemu, QemuE1000Max, QemuE1000NG
from test_qemu_latency import TestCmpLatency
from test_qemu_throughput import TestCmpThroughputTSO, TestCmpThroughput

# RUNTIME = 30
RUNTIME = 10
RETRIES = 1
BASE_DIR = r"../tmp/results/test-results-netserver_core/{hostname}".format(
    hostname=socket.gethostname()
)

OLD_QEMU = r"/home/bdaviv/repos/e1000-improv/qemu-arthur/build/x86_64-softmmu/qemu-system-x86_64"
OLD_KERNEL = r"/home/bdaviv/repos/e1000-improv/linux-3.13.0/arch/x86/boot/bzImage"
OLD_INITRD = r"../vms/initrd.img"


def create_vms():
    base = QemuNG(disk_path=r"../vms/ubuntu.img",
                  guest_ip="10.10.0.43",
                  host_ip="10.10.0.44")

    e1000_baseline = deepcopy(base)
    e1000_baseline.ethernet_dev = e1000_baseline.QEMU_E1000
    e1000_baseline.name = "E1000-baseline"

    virtio = deepcopy(base)
    virtio.ethernet_dev = virtio.QEMU_VIRTIO
    virtio.name = "virtio"

    virtio_batch = deepcopy(virtio)
    virtio_batch.name = "virtio_batch"
    virtio_batch.e1000_options["NG_notify_batch"] = "on"

    e1000_best_interrupt = QemuE1000NG(disk_path=r"../vms/ubuntu.img",
                             guest_ip="10.10.0.43",
                             host_ip="10.10.0.44")
    e1000_best_interrupt.name = "E1000-int_mul"
    e1000_best_interrupt.is_io_thread_nice = False
    # e1000_best_interrupt.kernel = r"../linux/arch/x86/boot/bzImage"
    # e1000_best_interrupt.initrd = r"/homes/bdaviv/repos/msc-ng/vm-files/kernels/initrd.img-4.14.4-ng+"
    e1000_best_interrupt.e1000_options["NG_interrupt_mul"] = 10
    e1000_best_interrupt.e1000_options["NG_interrupt_mode"] = 0
    e1000_best_interrupt.bootwait = 10

    e1000_skb_orphan = deepcopy(e1000_best_interrupt)
    e1000_skb_orphan.kernel_cmdline_additional = "e1000.NG_flags=1"
    e1000_skb_orphan.name = "E1000-skb_orphan"

    e1000_timer_itr = deepcopy(e1000_skb_orphan)
    e1000_timer_itr.e1000_options["NG_interrupt_mode"] = 2
    e1000_timer_itr.name = "E1000-timer_itr"
    # e1000_timer_itr.e1000_options["NG_parabatch"] = "on"

    e1000_timer_itr_reg = deepcopy(e1000_skb_orphan)
    e1000_timer_itr_reg.e1000_options["NG_interrupt_mode"] = 3
    e1000_timer_itr_reg.name = "E1000-timer_itr-reg"

    e1000_timer_itr_reg_lq = deepcopy(e1000_timer_itr_reg)
    e1000_timer_itr_reg_lq.name = "E1000-timer_itr-reg-q512"
    e1000_timer_itr_reg_lq.large_queue = True
    e1000_timer_itr_reg_lq.queue_size = 512

    # virtio.enabled = False
    # virtio_batch.enabled = False
    # e1000_skb_orphan.enabled = False
    # e1000_baseline.enabled = False
    # e1000_timer_itr_reg.enabled = False

    regular_vms = (

        virtio,
        virtio_batch,
        # virtio_drop,

        # e1000_best_3_13,
        # e1000_best_interrupt_3_13,
        # e1000_best_interrupt,

        e1000_skb_orphan,

        # e1000_timer_itr,
        # e1000_timer_itr_lq_4096,
        # e1000_timer_itr_parabatch,
        e1000_timer_itr_reg,
        # e1000_timer_itr_reg_lq,

        # e1000_batch_interrupt,
        # e1000_best_lq
        # e1000_tso_offloading,
        # e1000_arthur,
        e1000_baseline,
    )

    same_core = list()
    for vm in regular_vms:
        new_vm = deepcopy(vm)
        new_vm.name = vm.name + "-same_core"
        new_vm.netserver_core = vm.cpu_to_pin
        same_core.append(new_vm)

    return regular_vms + tuple(same_core)


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

    additional_x = [
        (1488, "1.5K")
    ]

    test_clss = [
        (TestCmpThroughput, "throughput"),
        (TestCmpLatency, "latency"),
        (TestCmpThroughputTSO, "throughput-TSO"),
    ]

    for cls, subdir in test_clss:
        root_logger.info("Starting test %s", cls.__name__)
        test_dir = os.path.join(BASE_DIR, subdir)
        os.makedirs(test_dir, exist_ok=True)
        test = cls(create_vms(), RUNTIME, RETRIES, directory=test_dir,
                   additional_x=additional_x)
        test.pre_run()
        test.run()
        test.post_run()
