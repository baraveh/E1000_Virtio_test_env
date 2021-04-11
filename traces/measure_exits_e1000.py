import logging
import os
import shutil

from kernel_traces.kernel_trace import Trace
from sensors.netperf import NetPerfLatency
from utils.machine import localRoot
from utils.vms import Qemu, QemuE1000Max

ORIG_QEMU = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build/x86_64-softmmu/qemu-system-x86_64"
# ORIG_QEMU = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build-trace/x86_64-softmmu/qemu-system-x86_64"
TMP_QEMU = r"/tmp/qemu-system-x86_64"
Qemu.QEMU_EXE = TMP_QEMU

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def main(directory=None):
    shutil.copyfile(ORIG_QEMU, TMP_QEMU)
    vm = QemuE1000Max(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                                   guest_ip="10.10.0.43",
                                   host_ip="10.10.0.44")
    vm.qemu_config["latency_itr"] = 2
    vm.ethernet_dev = 'e1000-82545em'
    vm.addiotional_guest_command = 'sudo ethtool -C eth0 rx-usecs 3000'

    local_trace = Trace(localRoot, "/tmp/trace_host")
    local_trace.setup()

    local_trace.enable_event("kvm/kvm_write_tsc_offset")
    local_trace.enable_event("kvm/kvm_exit")
    local_trace.enable_event("kvm/kvm_entry")
    local_trace.enable_event("kvm/kvm_userspace_exit")

    local_trace.set_event_filter("sched/sched_switch", r'prev_comm ~ "*qemu*" || next_comm ~ "*qemu*"')
    local_trace.enable_event("sched/sched_switch")

    local_trace.uprobe_add_event("p", "set_tctl", TMP_QEMU, "set_tctl")
    local_trace.uprobe_add_event("p", "kvm_vcpu_ioctl", TMP_QEMU, "kvm_vcpu_ioctl", "cmd=%si")
    local_trace.uprobe_enable()

    local_trace.empty_trace()
    local_trace.trace_on()
    local_trace.trace_to_local_file()

    vm.setup()
    vm.run()

    remote_trace = Trace(vm.root, "/tmp/trace_guest")
    remote_trace.setup()
    # remote_trace.kprobe_add("p:e1000_tdt_begin e1000_tx_queue")
    remote_trace.enable_event("e1000/e1000_set_tdt")
    # remote_trace.kprobe_add("r:e1000_tdt_end e1000_tx_queue")
    remote_trace.enable_event("e1000/e1000_post_set_tdt")
    remote_trace.kprobe_add("p:e1000_intr e1000_intr")
    remote_trace.kprobe_enable()
    remote_trace.trace_on()

    netperf = NetPerfLatency(None, runtime=2)
    netperf_perf = netperf.run_netperf(vm, msg_size=64)
    print("Netperf performance: %s" % (netperf_perf, ))
    logger.info("Netperf performance: %s", netperf_perf)

    remote_trace.trace_off()
    remote_trace.disable_all_events()
    local_trace.trace_off()
    local_trace.disable_all_events()

    netperf_perf = netperf.run_netperf(vm, msg_size=64)
    print("Netperf performance: %s" % (netperf_perf,))
    logger.info("Netperf performance: %s", netperf_perf)

    remote_trace.read_trace_once(to_file=True)
    local_trace.trace_to_local_file_stop()

    local_trace.disable_all_events()

    # input()
    vm.teardown()

    if directory:
        os.makedirs(directory, exist_ok=True)
        shutil.copy("/tmp/trace_guest", directory)
        shutil.copy("/tmp/trace_host", directory)


if __name__ == "__main__":
    import sys
    d = None
    if len(sys.argv) > 1:
        d = sys.argv[1]
    main(d)

