import logging
import os
import shutil
from copy import deepcopy
import sys

PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from utils.vms import QemuNG, Qemu, QemuE1000Max, QemuE1000NG
from test_qemu_throughput import TestCmpThroughputTSO

# RUNTIME = 8
RUNTIME = 30
RETRIES = 3
BASE_DIR = r"/home/bdaviv/tmp/results/test-results-tso"

OLD_QEMU = r"/home/bdaviv/repos/e1000-improv/qemu-arthur/build/x86_64-softmmu/qemu-system-x86_64"
OLD_KERNEL = r"/home/bdaviv/repos/e1000-improv/linux-3.13.0/arch/x86/boot/bzImage"
OLD_INITRD = r"/homes/bdaviv/repos/e1000-improv/vms/initrd.img-3.13.11-ckt22+"


def create_vms():
    base = QemuNG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                  guest_ip="10.10.0.43",
                  host_ip="10.10.0.44")
    base.netperf_test_params = "-C"

    e1000_baseline = deepcopy(base)
    e1000_baseline.ethernet_dev = e1000_baseline.QEMU_E1000
    e1000_baseline.name = "E1000-baseline"

    virtio = deepcopy(base)
    virtio.ethernet_dev = virtio.QEMU_VIRTIO
    virtio.name = "virtio"

    virtio_batch = deepcopy(virtio)
    virtio_batch.name = "virtio_batch"
    virtio_batch.e1000_options["NG_notify_batch"] = "on"

    virtio_drop = deepcopy(virtio)
    virtio_drop.name = "virtio_drop"
    virtio_drop.e1000_options["NG_drop_packet"] = "on"


    e1000_best_interrupt = QemuE1000NG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                             guest_ip="10.10.0.43",
                             host_ip="10.10.0.44")
    e1000_best_interrupt.name = "E1000-int_mul"
    e1000_best_interrupt.is_io_thread_nice = False
    # e1000_best_interrupt.kernel = r"/homes/bdaviv/repos/msc-ng/linux-4.14.4/arch/x86/boot/bzImage"
    # e1000_best_interrupt.initrd = r"/homes/bdaviv/repos/msc-ng/vm-files/kernels/initrd.img-4.14.4-ng+"
    e1000_best_interrupt.e1000_options["NG_interrupt_mul"] = 10
    e1000_best_interrupt.e1000_options["NG_interrupt_mode"] = 0
    e1000_best_interrupt.bootwait = 10
    e1000_best_interrupt.netperf_test_params = "-C"

    e1000_tso_offloading = deepcopy(e1000_best_interrupt)
    e1000_tso_offloading.e1000_options["NG_tso_offloading"] = "on"

    e1000_batch_interrupt = deepcopy(e1000_best_interrupt)
    e1000_batch_interrupt.name = "e1000-batch_itr"
    e1000_batch_interrupt.e1000_options["NG_interrupt_mul"] = 1
    e1000_batch_interrupt.e1000_options["NG_interrupt_mode"] = 1
    # e1000_batch_interrupt.e1000_options["NG_parabatch"] = "on"

    e1000_best_lq = deepcopy(e1000_best_interrupt)
    e1000_best_lq.name = "e1000-int_mul-largeQ"
    e1000_best_lq.large_queue = True
    # e1000_best_lq.static_itr = True

    e1000_skb_orphan = deepcopy(e1000_best_interrupt)
    e1000_skb_orphan.kernel_cmdline_additional = "e1000.NG_flags=1"
    e1000_skb_orphan.name = "E1000-skb_orphan"

    e1000_skb_orphan_lq_512 = deepcopy(e1000_skb_orphan)
    e1000_skb_orphan_lq_512.large_queue = True
    e1000_skb_orphan_lq_512.queue_size = 512
    e1000_skb_orphan_lq_512.name = "E1000-skb_orphan-LQ_{}".format(e1000_skb_orphan_lq_512.queue_size)

    e1000_skb_orphan_lq_1024 = deepcopy(e1000_skb_orphan_lq_512)
    e1000_skb_orphan_lq_1024.queue_size = 1024
    e1000_skb_orphan_lq_1024.name = "E1000-skb_orphan-LQ_{}".format(e1000_skb_orphan_lq_1024.queue_size)

    e1000_timer_itr = deepcopy(e1000_skb_orphan)
    e1000_timer_itr.e1000_options["NG_interrupt_mode"] = 2
    e1000_timer_itr.name = "E1000-timer_itr"
    # e1000_timer_itr.e1000_options["NG_parabatch"] = "on"

    e1000_timer_itr_parabatch = deepcopy(e1000_skb_orphan)
    e1000_timer_itr_parabatch.e1000_options["NG_interrupt_mode"] = 2
    e1000_timer_itr_parabatch.name = "E1000-timer_itr-parabatch"
    e1000_timer_itr_parabatch.e1000_options["NG_parabatch"] = "on"
    # e1000_timer_itr_parabatch.large_queue = True
    # e1000_timer_itr_parabatch.queue_size = 4096

    e1000_timer_itr_lq_4096 = deepcopy(e1000_timer_itr)
    e1000_timer_itr_lq_4096.name = "E1000-timer_itr-lq4096"
    e1000_timer_itr_lq_4096.large_queue = True
    e1000_timer_itr_lq_4096.queue_size = 4096

    return (
        # e1000_baseline,

        virtio,
        virtio_batch,
        # virtio_drop,

        # e1000_best_interrupt,

        e1000_skb_orphan,

        e1000_timer_itr,
        # e1000_timer_itr_lq_4096,
        # e1000_timer_itr_parabatch

        # e1000_skb_orphan_lq_512,
        # e1000_skb_orphan_lq_1024
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

    additional_x = [
        (1488, "1.5K")
    ]

    test = TestCmpThroughputTSO(create_vms(), RUNTIME, RETRIES, directory=BASE_DIR,
                                additional_x=additional_x)
    test.pre_run()
    test.run()
    test.post_run()
