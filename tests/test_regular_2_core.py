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
BASE_DIR = r"../tmp/results/test-results-2core/{hostname}".format(
    hostname=socket.gethostname()
)

OLD_QEMU = r"/home/bdaviv/repos/e1000-improv/qemu-arthur/build/x86_64-softmmu/qemu-system-x86_64"
OLD_KERNEL = r"/home/bdaviv/repos/e1000-improv/linux-3.13.0/arch/x86/boot/bzImage"
OLD_INITRD = r"/homes/bdaviv/repos/e1000-improv/vms/initrd.img-3.13.11-ckt22+"


def create_vms():
    base = QemuNG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                  guest_ip="10.10.0.43",
                  host_ip="10.10.0.44")

    e1000_baseline = deepcopy(base)
    e1000_baseline.ethernet_dev = e1000_baseline.QEMU_E1000
    e1000_baseline.name = "E1000-baseline"

    virtio = deepcopy(base)
    virtio.ethernet_dev = virtio.QEMU_VIRTIO
    virtio.name = "virtio"

    virtio_vhost = deepcopy(virtio)
    virtio_vhost.name += "_vhost"
    virtio_vhost.vhost = True

    virtio_batch = deepcopy(virtio)
    virtio_batch.name = "virtio_batch"
    virtio_batch.e1000_options["NG_notify_batch"] = "on"

    virtio_drop = deepcopy(virtio)
    virtio_drop.name = "virtio_drop"
    virtio_drop.e1000_options["NG_drop_packet"] = "on"

    e1000_best_interrupt = QemuE1000NG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
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

    e1000_arthur = QemuE1000Max(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
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

    e1000_timer_itr_reg = deepcopy(e1000_skb_orphan)
    e1000_timer_itr_reg.e1000_options["NG_interrupt_mode"] = 3
    e1000_timer_itr_reg.name = "E1000-timer_itr-reg"

    e1000_timer_itr_reg_lq = deepcopy(e1000_timer_itr_reg)
    e1000_timer_itr_reg_lq.name = "E1000-timer_itr-reg-q512"
    e1000_timer_itr_reg_lq.large_queue = True
    e1000_timer_itr_reg_lq.queue_size = 512

    # no lock varients
    e1000_skb_orphan_nolock = deepcopy(e1000_skb_orphan)
    e1000_skb_orphan_nolock.name += "-nolock"
    e1000_skb_orphan_nolock.e1000_options["NG_disable_iothread_lock"] = "on"

    e1000_skb_orphan_lq_nolock = deepcopy(e1000_skb_orphan_nolock)
    e1000_skb_orphan_lq_nolock.large_queue = True
    e1000_skb_orphan_lq_nolock.queue_size = 512
    e1000_skb_orphan_lq_nolock.name += "-lq"

    e1000_timer_itr_reg_nolock = deepcopy(e1000_timer_itr_reg)
    e1000_timer_itr_reg_nolock.name += "-nolock"
    e1000_timer_itr_reg_nolock.e1000_options["NG_disable_iothread_lock"] = "on"

    e1000_batch_interrupt_nolock = deepcopy(e1000_batch_interrupt)
    e1000_batch_interrupt_nolock.name += "-nolock"
    e1000_batch_interrupt_nolock.e1000_options["NG_disable_iothread_lock"] = "on"

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

    e1000_halt_unlock = deepcopy(e1000_halt)
    e1000_halt_unlock.name += "-unlocked"
    e1000_halt_unlock.e1000_options["NG_disable_iothread_lock"] = "on"

    e1000_halt_no_rdt_jump = deepcopy(e1000_halt)
    e1000_halt_no_rdt_jump.name += "-no_rdt_jump"
    e1000_halt_no_rdt_jump.e1000_options["NG_disable_rdt_jump"] = "on"
    e1000_halt_no_rdt_jump.e1000_options["NG_fast_iothread_kick"] = "on"
    e1000_halt_no_rdt_jump.disable_kvm_poll = True

    e1000_halt_no_rdt_jump_lq = deepcopy(e1000_halt_no_rdt_jump)
    e1000_halt_no_rdt_jump_lq.name += "-lq"
    e1000_halt_no_rdt_jump_lq.large_queue = True
    e1000_halt_no_rdt_jump_lq.queue_size = 512

    virtio_batch_nopoll = deepcopy(virtio_batch)
    virtio_batch_nopoll.disable_kvm_poll = True
    virtio_batch_nopoll.name += "-nopoll"

    # virtio.enabled = False
    # virtio_batch.enabled = False
    # e1000_skb_orphan.enabled = False
    # e1000_baseline.enabled = False
    # e1000_timer_itr_reg.enabled = False
    # e1000_skb_orphan_nolock.enabled = False
    # e1000_timer_itr_reg_nolock.enabled = False

    # e1000_halt.enabled = False
    # e1000_halt_lq.enabled = False

    vms = (

        virtio,
        virtio_batch,
        # virtio_drop,
        # virtio_vhost,
        virtio_batch_nopoll,

        # e1000_best_3_13,
        # e1000_best_interrupt_3_13,
        # e1000_best_interrupt,

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
        # e1000_halt_no_rdt_jump,
        # e1000_halt_no_rdt_jump_lq,
        # e1000_halt_unlock

        # e1000_batch_interrupt,
        # e1000_batch_interrupt_nolock,
        # e1000_best_lq
        # e1000_tso_offloading,
        # e1000_arthur,
        # e1000_baseline,
    )

    vms2 = list()
    for vm in vms:
        new_vm = deepcopy(vm)
        new_vm.name += "-2core"
        new_vm.io_thread_cpu = "1"
        vms2.append(new_vm)

    return vms + tuple(vms2)


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
