import logging
import os
import socket
from copy import deepcopy
from utils.vms import QemuNG, Qemu, QemuE1000Max, QemuE1000NG
from test_qemu_latency import TestCmpLatency

# RUNTIME = 8
RUNTIME = 30
RETRIES = 3
BASE_DIR = r"../tmp/results/{hostname}/test-results-latency".format(
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

    virtio_drop = deepcopy(virtio)
    virtio_drop.name = "virtio_drop"
    virtio_drop.e1000_options["NG_drop_packet"] = "on"

    e1000_best_3_13 = QemuE1000NG(disk_path=r"../vms/ubuntu.img",
                             guest_ip="10.10.0.43",
                             host_ip="10.10.0.44")
    e1000_best_3_13.name = "E1000-best"
    e1000_best_3_13.is_io_thread_nice = False
    e1000_best_3_13.kernel = OLD_KERNEL
    e1000_best_3_13.initrd = OLD_INITRD

    e1000_best_interrupt_3_13 = deepcopy(e1000_best_3_13)
    e1000_best_interrupt_3_13.name = "E1000-Arthur_interrupt-3.13"
    e1000_best_interrupt_3_13.e1000_options["NG_interrupt_mul"] = 10
    e1000_best_interrupt_3_13.e1000_options["NG_interrupt_mode"] = 0

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

    e1000_timer_itr = deepcopy(e1000_skb_orphan)
    e1000_timer_itr.e1000_options["NG_interrupt_mode"] = 2
    e1000_timer_itr.name = "E1000-timer_itr"
    # e1000_timer_itr.e1000_options["NG_parabatch"] = "on"

    e1000_arthur = QemuE1000Max(disk_path=r"../vms/ubuntu.img",
                                guest_ip="10.10.0.43",
                                host_ip="10.10.0.44")
    e1000_arthur.kernel = OLD_KERNEL
    e1000_arthur.initrd = OLD_INITRD
    e1000_arthur.exe = OLD_QEMU
    e1000_arthur.nic_additionals = ''
    e1000_arthur.qemu_additionals = '-enable-e1000-pcix'
    e1000_arthur.name = "E1000-Arthur-old"
    e1000_arthur.qemu_config["drop_packet_every"] = 8000
    e1000_arthur.qemu_config["drop_packet_every_avg_packet_size_min"] = 25000
    e1000_arthur.qemu_config["drop_packet_every_avg_packet_size_max"] = 60000

    e1000_timer_itr_lq_4096 = deepcopy(e1000_timer_itr)
    e1000_timer_itr_lq_4096.name = "E1000-timer_itr-lq1024"
    e1000_timer_itr_lq_4096.large_queue = True
    e1000_timer_itr_lq_4096.queue_size = 4096

    e1000_timer_itr_parabatch = deepcopy(e1000_skb_orphan)
    e1000_timer_itr_parabatch.e1000_options["NG_interrupt_mode"] = 2
    e1000_timer_itr_parabatch.name = "E1000-timer_itr-parabatch"
    e1000_timer_itr_parabatch.e1000_options["NG_parabatch"] = "on"
    # e1000_timer_itr_parabatch.large_queue = True
    # e1000_timer_itr_parabatch.queue_size = 4096

    return (

        virtio,
        virtio_batch,
        # virtio_drop,

        # e1000_best_3_13,
        # e1000_best_interrupt_3_13,
        # e1000_best_interrupt,

        e1000_skb_orphan,

        e1000_timer_itr,
        # e1000_timer_itr_lq_4096,
        # e1000_timer_itr_parabatch,

        # e1000_batch_interrupt,
        # e1000_best_lq
        # e1000_tso_offloading,
        # e1000_arthur,
        e1000_baseline,
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

    test = TestCmpLatency(create_vms(), RUNTIME, RETRIES, directory=BASE_DIR,
                          additional_x=additional_x)
    test.pre_run()
    test.run()
    test.post_run()
