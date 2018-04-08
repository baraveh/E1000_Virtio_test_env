import logging
import os
import shutil
from copy import deepcopy
import sys
from os import path

from test_qemu_latency import TestCmpLatency

PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from utils.graphs import Graph
from utils.sensors import SensorBeforeAfter
from utils.vms import QemuNG, Qemu, QemuE1000Max, QemuE1000NG
from test_qemu_throughput import TestCmpThroughput

RUNTIME = 8
# RUNTIME = 15
RETRIES = 1
BASE_DIR = r"/home/bdaviv/tmp/results/test-results"

OLD_QEMU = r"/home/bdaviv/repos/e1000-improv/qemu-arthur/build/x86_64-softmmu/qemu-system-x86_64"
OLD_KERNEL = r"/home/bdaviv/repos/e1000-improv/linux-3.13.0/arch/x86/boot/bzImage"
OLD_INITRD = r"/homes/bdaviv/repos/e1000-improv/vms/initrd.img-3.13.11-ckt22+"


def create_vms():
    base = QemuNG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                  guest_ip="10.10.0.43",
                  host_ip="10.10.0.44")

    e1000_baseline = deepcopy(base)
    e1000_baseline.ethernet_dev = e1000_baseline.QEMU_E1000
    e1000_baseline.name = "E1000-baseline"

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

    e1000_delay_timer = list()
    for i in range(610, 1400, 100):
        vm = deepcopy(e1000_timer_itr)
        vm.e1000_options["NG_interrupt_min"] = i
        vm.name = "e1000_delay_{}".format(i)
        e1000_delay_timer.append(vm)

    return e1000_delay_timer


class MaxPacketPerSecondSensor(SensorBeforeAfter):
    def _get_value(self, vm):
        with open("/tmp/recv_stats.txt", "r") as f:
            lines = f.readlines()
            return [float(line.strip()) for line in lines]

    def _delta(self, value1, value2):
        new_lines = value2[len(value1):]
        return max(new_lines)


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

    test = TestCmpThroughput(create_vms(), RUNTIME, RETRIES, directory=BASE_DIR)
    test._sensors.append(
        MaxPacketPerSecondSensor(
            Graph("msg size", "Maximum recv packets per second",
                  path.join(test.dir, "throughput-max_recv_packets")
                  )
        )
    )
    test.pre_run()
    test.run()
    test.post_run()


    additional_x = [
        (1488, "1.5K")
    ]

    test = TestCmpLatency(create_vms(), RUNTIME, RETRIES, directory=BASE_DIR,
                          additional_x=additional_x)
    test.pre_run()
    test.run()
    test.post_run()