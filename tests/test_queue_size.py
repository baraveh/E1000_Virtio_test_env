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
BASE_DIR = r"../tmp/results/test-qeueu_size/{hostname}".format(
    hostname=socket.gethostname()
)

OLD_QEMU = r"/home/bdaviv/repos/e1000-improv/qemu-arthur/build/x86_64-softmmu/qemu-system-x86_64"
OLD_KERNEL = r"/home/bdaviv/repos/e1000-improv/linux-3.13.0/arch/x86/boot/bzImage"
OLD_INITRD = r"../vms/initrd.img"


def create_vms():
    base = QemuNG(disk_path=r"../vms/ubuntu-20.img",
                  guest_ip="10.10.0.43",
                  host_ip="10.10.0.44")

    virtio = deepcopy(base)
    virtio.ethernet_dev = virtio.QEMU_VIRTIO
    virtio.name = "virtio"

    virtio_vhost = deepcopy(virtio)
    virtio_vhost.name += "_vhost"
    virtio_vhost.vhost = True

    virtio_batch = deepcopy(virtio)
    virtio_batch.name = "virtio_batch"
    virtio_batch.e1000_options["NG_notify_batch"] = "on"

    e1000_baseline = deepcopy(base)
    e1000_baseline.ethernet_dev = e1000_baseline.QEMU_E1000
    e1000_baseline.name = "E1000-baseline"

    e1000_best_interrupt = QemuE1000NG(disk_path=r"../vms/ubuntu-20.img",
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

    e1000_halt = deepcopy(e1000_skb_orphan)
    e1000_halt.name = "E1000-halt"
    e1000_halt.e1000_options["NG_parahalt"] = "on"
    # e1000_halt.e1000_options["NG_disable_iothread_lock"] = "on"
    # e1000_halt.e1000_options["NG_tx_iothread"] = "off"
    e1000_halt.e1000_options["NG_interrupt_mode"] = 0
    e1000_halt.e1000_options["NG_interrupt_mul"] = 0
    e1000_halt.e1000_options["mitigation"] = "off"

    e1000_halt_lq = deepcopy(e1000_halt)
    e1000_halt_lq.name += "-lq"
    e1000_halt_lq.large_queue = True
    e1000_halt_lq.queue_size = 512

    e1000_halt_no_rdt_jump = deepcopy(e1000_halt)
    e1000_halt_no_rdt_jump.name += "-no_rdt_jump"
    e1000_halt_no_rdt_jump.e1000_options["NG_disable_rdt_jump"] = "on"
    e1000_halt_no_rdt_jump.e1000_options["NG_disable_TXDW"] = "on"
    e1000_halt_no_rdt_jump.e1000_options["NG_fast_iothread_kick"] = "on"

    e1000_halt_no_rdt_jump_lq512 = deepcopy(e1000_halt_no_rdt_jump)
    e1000_halt_no_rdt_jump_lq512.name += "-lq512"
    e1000_halt_no_rdt_jump_lq512.large_queue = True
    e1000_halt_no_rdt_jump_lq512.queue_size = 512

    e1000_halt_no_rdt_jump_lq1024 = deepcopy(e1000_halt_no_rdt_jump)
    e1000_halt_no_rdt_jump_lq1024.name += "-lq1024"
    e1000_halt_no_rdt_jump_lq1024.large_queue = True
    e1000_halt_no_rdt_jump_lq1024.queue_size = 1024

    e1000_halt_no_rdt_jump_lq2048 = deepcopy(e1000_halt_no_rdt_jump)
    e1000_halt_no_rdt_jump_lq2048.name += "-lq2048"
    e1000_halt_no_rdt_jump_lq2048.large_queue = True
    e1000_halt_no_rdt_jump_lq2048.queue_size = 2048

    # e1000_halt_no_rdt_jump.enabled = False
    # e1000_halt_no_rdt_jump_lq512.enabled = False
    # e1000_halt_no_rdt_jump_lq1024.enabled = False
    # e1000_halt_no_rdt_jump_lq2048.enabled = False

    return (
        virtio_batch,
        # e1000_skb_orphan, # latest
        # e1000_skb_orphan_nolock,
        # e1000_skb_orphan_lq_nolock,

        # e1000_timer_itr,
        # e1000_timer_itr_lq_4096,
        # e1000_timer_itr_parabatch,
        # e1000_timer_itr_reg,  # latest
        # e1000_timer_itr_reg_lq,
        # e1000_timer_itr_reg_nolock,

        # e1000_halt,
        # e1000_halt_lq,
        e1000_halt_no_rdt_jump,
        e1000_halt_no_rdt_jump_lq512,
        e1000_halt_no_rdt_jump_lq1024,
        e1000_halt_no_rdt_jump_lq2048,
        # e1000_halt_unlock

        # e1000_batch_interrupt,
        # e1000_batch_interrupt_nolock,
        # e1000_best_lq
        # e1000_tso_offloading,
        # e1000_arthur,
        # e1000_baseline,
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
