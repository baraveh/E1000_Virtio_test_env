import logging
import os
import shutil
from collections import Counter
from math import log2

from kernel_traces.kernel_trace import Trace
from kernel_traces.trace_parser import Traces, TRACE_BEGIN_MSG, TRACE_END_MSG, delta2time
from sensors.netperf import NetPerfLatency, NetPerfTCP
from utils.machine import localRoot
from utils.vms import Qemu, QemuE1000Max

ORIG_QEMU = r"../qemu/build/x86_64-softmmu/qemu-system-x86_64"
# ORIG_QEMU = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build-trace/x86_64-softmmu/qemu-system-x86_64"
TMP_QEMU = r"/tmp/qemu-system-x86_64"
Qemu.QEMU_EXE = TMP_QEMU

TMP_DIR = r"/tmp/traces"

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_dir(directory=None):
    if directory:
        return directory
    else:
        return TMP_DIR


def main(directory=None):
    trace_dir = get_dir(directory)

    shutil.copyfile(ORIG_QEMU, TMP_QEMU)
    os.makedirs(trace_dir, exist_ok=True)

    vm = QemuE1000Max(disk_path=r"../vms/ubuntu.img",
                      guest_ip="10.10.0.43",
                      host_ip="10.10.0.44")
    vm.qemu_config["latency_itr"] = 0
    vm.ethernet_dev = 'e1000-82545em'
    vm.addiotional_guest_command = 'sudo ethtool -C eth0 rx-usecs 3000'

    local_trace = Trace(localRoot, os.path.join(trace_dir, "trace_host"))
    local_trace.setup()

    # local_trace.enable_event("kvm/kvm_write_tsc_offset")
    # local_trace.enable_event("kvm/kvm_exit")
    # local_trace.enable_event("kvm/kvm_entry")
    # local_trace.enable_event("kvm/kvm_userspace_exit")

    # local_trace.set_event_filter("sched/sched_switch", r'prev_comm ~ "*qemu*" || next_comm ~ "*qemu*"')
    # local_trace.enable_event("sched/sched_switch")

    # objdump -tT /tmp/qemu-system-x86_64 |grep .text|grep virtio_queue_notify_vq
    ## local_trace.uprobe_add("p:virtio_queue_notify_vq /tmp/qemu-system-x86_64:0x1bfba6")
    # local_trace.uprobe_add_event("p", "virtio_queue_notify_vq", TMP_QEMU, "virtio_queue_notify_vq")
    # objdump -tT /tmp/qemu-system-x86_64 |grep .text|grep kvm_vcpu_ioctl
    ## local_trace.uprobe_add("p:kvm_vcpu_ioctl /tmp/qemu-system-x86_64:0x16a886 cmd=%si")
    # local_trace.uprobe_add_event("p", "kvm_vcpu_ioctl", TMP_QEMU, "kvm_vcpu_ioctl", "cmd=%si")
    # local_trace.uprobe_enable()

    # local_trace.empty_trace()
    # local_trace.trace_on()
    # local_trace.trace_to_local_file()

    vm.setup()
    vm.run()

    remote_trace = Trace(vm.root, os.path.join(trace_dir, "trace_guest"))
    remote_trace.setup()
    remote_trace.set_buffer_size(20000)
    remote_trace.enable_event("napi/napi_poll")
    # remote_trace.enable_event("power/cpu_idle")
    remote_trace.enable_event("irq/irq_handler_entry")
    # remote_trace.enable_event("e1000/e1000_pre_mem_op")
    # remote_trace.enable_event("e1000/e1000_post_mem_op")
    # remote_trace.enable_event("e1000/e1000_set_tdt")
    # remote_trace.enable_event("e1000/e1000_post_set_tdt")
    # remote_trace.kprobe_add("p:notify_begin vp_notify")
    # remote_trace.kprobe_add("r:notify_end vp_notify")
    # remote_trace.kprobe_enable()
    remote_trace.trace_on()

    netperf = NetPerfTCP(None, runtime=2)

    remote_trace.trace_marker(TRACE_BEGIN_MSG)
    netperf_perf = netperf.run_netperf(vm, msg_size="64K")
    remote_trace.trace_marker(TRACE_END_MSG)
    print("Netperf performance: %s" % (netperf_perf, ))
    logger.info("Netperf performance: %s", netperf_perf)

    remote_trace.trace_off()
    remote_trace.disable_all_events()
    local_trace.trace_off()
    local_trace.disable_all_events()

    netperf_perf = netperf.run_netperf(vm, msg_size="64K")
    print("Base Netperf performance: %s" % (netperf_perf,))
    logger.info("Base Netperf performance: %s", netperf_perf)

    remote_trace.read_trace_once(to_file=True)
    # local_trace.trace_to_local_file_stop()

    local_trace.disable_all_events()

    # input()
    vm.teardown()


def startup():
    import sys
    d = None
    if len(sys.argv) > 1:
        d = sys.argv[1]
    d = get_dir(d)

    os.makedirs(d, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.addHandler(logging.FileHandler(os.path.join(d, "log")))

    main(d)


if __name__ == "__main__":
    startup()
