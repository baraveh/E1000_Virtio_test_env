import logging
import os
import shutil

from kernel_traces.kernel_trace import Trace
from sensors.netperf import NetPerfLatency
from utils.machine import localRoot
from utils.vms import Qemu

ORIG_QEMU = r"qemu-system-x86_64"
# ORIG_QEMU = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build-trace/x86_64-softmmu/qemu-system-x86_64"
TMP_QEMU = r"/tmp/qemu-system-x86_64"
Qemu.QEMU_EXE = TMP_QEMU

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def main(directory=None):
    shutil.copyfile(ORIG_QEMU, TMP_QEMU)
    vm = Qemu(disk_path=r"../vms/ubuntu-20.img",
              guest_ip="10.10.0.43",
              host_ip="10.10.0.44")
    vm.ethernet_dev = Qemu.QEMU_VIRTIO
    # vm.qemu_config["latency_itr"] = 2

    local_trace = Trace(localRoot, "/tmp/trace_host")
    local_trace.setup()

    local_trace.enable_event("kvm/kvm_write_tsc_offset")
    local_trace.enable_event("kvm/kvm_exit")
    local_trace.enable_event("kvm/kvm_entry")
    local_trace.enable_event("kvm/kvm_userspace_exit")

    local_trace.set_event_filter("sched/sched_switch", r'prev_comm ~ "*qemu*" || next_comm ~ "*qemu*"')
    local_trace.enable_event("sched/sched_switch")

    # objdump -tT /tmp/qemu-system-x86_64 |grep .text|grep virtio_queue_notify_vq
    # local_trace.uprobe_add("p:virtio_queue_notify_vq /tmp/qemu-system-x86_64:0x1bfba6")
    local_trace.uprobe_add_event("p", "virtio_queue_notify_vq", TMP_QEMU, "virtio_queue_notify_vq")
    # objdump -tT /tmp/qemu-system-x86_64 |grep .text|grep kvm_vcpu_ioctl
    # local_trace.uprobe_add("p:kvm_vcpu_ioctl /tmp/qemu-system-x86_64:0x16a886 cmd=%si")
    local_trace.uprobe_add_event("p", "kvm_vcpu_ioctl", TMP_QEMU, "kvm_vcpu_ioctl", "cmd=%si")
    local_trace.uprobe_enable()

    local_trace.empty_trace()
    local_trace.trace_on()
    local_trace.trace_to_local_file()

    vm.setup()
    vm.run()

    remote_trace = Trace(vm.root, "/tmp/trace_guest")
    remote_trace.setup()
    remote_trace.kprobe_add("p:notify_begin vp_notify")
    remote_trace.kprobe_add("r:notify_end vp_notify")
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

