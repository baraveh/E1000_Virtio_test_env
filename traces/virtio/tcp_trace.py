import csv
import logging
import os
import shutil
from collections import Counter
from math import log2

from kernel_traces.kernel_trace import Trace
from kernel_traces.trace_parser import Traces, TRACE_BEGIN_MSG, TRACE_END_MSG, delta2time, TraceFile
from sensors.netperf import NetPerfLatency, NetPerfTCP, netserver_start, netserver_stop
from utils.machine import localRoot
from utils.shell_utils import run_command_async
from utils.vms import Qemu, QemuE1000Max, QemuNG

# ORIG_QEMU = r"/usr/lib/qemu"
# ORIG_QEMU = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build-trace/x86_64-softmmu/qemu-system-x86_64"
ORIG_QEMU = r"../qemu/build/x86_64-softmmu/qemu-system-x86_64"
# TMP_QEMU = r"/tmp/qemu-system-x86_64"
TMP_QEMU = ORIG_QEMU
Qemu.QEMU_EXE = ORIG_QEMU

TMP_DIR = r"/tmp/traces"
MSG_SIZE = "4k"

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_dir(directory=None):
    if directory:
        return directory
    else:
        return TMP_DIR


def main(directory=None, netperf_msg_size=None):
    trace_dir = get_dir(directory)

    if netperf_msg_size is None:
        netperf_msg_size = MSG_SIZE

    if ORIG_QEMU != TMP_QEMU:
        shutil.copyfile(ORIG_QEMU, TMP_QEMU)
    os.makedirs(trace_dir, exist_ok=True)

    netserver_start()
    logger.info("msg size = %s", netperf_msg_size)

    vm = QemuNG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                guest_ip="10.10.0.43",
                host_ip="10.10.0.44")
    vm.ethernet_dev = Qemu.QEMU_VIRTIO
    vm.e1000_options["NG_notify_batch"] = "on"
    vm.BOOTUP_WAIT = 15

    local_trace = Trace(localRoot, os.path.join(trace_dir, "trace_host"))
    local_trace.setup()
    local_trace.set_buffer_size(100000)

    local_trace.enable_event("kvm/kvm_write_tsc_offset")
    local_trace.enable_event("kvm/kvm_set_irq")
    local_trace.enable_event("kvm/kvm_msi_set_irq")
    local_trace.enable_event("kvm/kvm_inj_virq")
    local_trace.enable_event("kvm/kvm_ioapic_set_irq")
    local_trace.enable_event("kvm/kvm_exit")
    local_trace.enable_event("kvm/kvm_entry")
    local_trace.enable_event("kvm/kvm_userspace_exit")
    local_trace.enable_event("kvm")

    local_trace.set_event_filter("sched/sched_switch", r'prev_comm ~ "*qemu*" || next_comm ~ "*qemu*"')
    local_trace.enable_event("sched/sched_switch")

    local_trace.set_event_filter("sched/sched_wakeup", '\"comm~*qemu*\"')
    local_trace.enable_event("sched/sched_wakeup")

    local_trace.set_event_filter("sched/sched_waking", '\"comm~*qemu*\"')
    local_trace.enable_event("sched/sched_waking")

    # objdump -tT /tmp/qemu-system-x86_64 |grep .text|grep virtio_queue_notify_vq
    ## local_trace.uprobe_add("p:virtio_queue_notify_vq /tmp/qemu-system-x86_64:0x1bfba6")
    # local_trace.uprobe_add_event("p", "virtio_queue_notify_vq", TMP_QEMU, "virtio_queue_notify_vq")
    # objdump -tT /tmp/qemu-system-x86_64 |grep .text|grep kvm_vcpu_ioctl
    ## local_trace.uprobe_add("p:kvm_vcpu_ioctl /tmp/qemu-system-x86_64:0x16a886 cmd=%si")
    # local_trace.uprobe_add_event("p", "kvm_vcpu_ioctl", TMP_QEMU, "kvm_vcpu_ioctl", "cmd=%si")

    local_trace.uprobe_add_event("p", "tap_write_packet", TMP_QEMU, "tap_write_packet")
    local_trace.uprobe_add_event("p", "tap_recv_packets", TMP_QEMU, "tap_send")
    local_trace.uprobe_add_event("r", "tap_recv_packets_end", TMP_QEMU, "tap_send")
    local_trace.uprobe_add_event("p", "virtio_irq", TMP_QEMU, "virtio_irq")

    # local_trace.uprobe_add_event("p", "virtio_queue_notify_vq", TMP_QEMU, "virtio_queue_notify_vq")
    # local_trace.uprobe_add_event("p", "e1000_set_kick", TMP_QEMU, "e1000_set_kick")
    # local_trace.uprobe_add_event("p", "e1000_receive_batch_finished", TMP_QEMU, "e1000_receive_batch_finished")
    local_trace.uprobe_enable()

    local_trace.empty_trace()
    local_trace.trace_on()
    # local_trace.trace_to_local_file()

    vm.setup()
    vm.run()

    remote_trace = Trace(vm.root, os.path.join(trace_dir, "trace_guest"))
    remote_trace.setup()
    remote_trace.set_buffer_size(100000)
    remote_trace.enable_event("tcp")
    remote_trace.enable_event("net")
    remote_trace.enable_event("irq")
    remote_trace.enable_event("irq_vectors")
    remote_trace.enable_event("napi")
    remote_trace.enable_event("power/cpu_idle")
    remote_trace.enable_event("syscalls/sys_enter_sendto")
    remote_trace.enable_event("syscalls/sys_enter_recvfrom")
    remote_trace.enable_event("net/net_dev_xmit")

    # remote_trace.enable_event("irq/irq_handler_entry")
    # remote_trace.enable_event("e1000/e1000_pre_mem_op")
    # remote_trace.enable_event("e1000/e1000_post_mem_op")
    # remote_trace.enable_event("e1000/e1000_set_tdt")
    # remote_trace.enable_event("e1000/e1000_post_set_tdt")

    remote_trace.kprobe_add("p:notify_begin virtqueue_kick")
    remote_trace.kprobe_add("r:notify_end virtqueue_kick")

    # remote_trace.kprobe_enable()
    remote_trace.trace_on()

    netperf = NetPerfTCP(None, runtime=2)
    run_command_async("tcpdump -i tap0 -s 100 -w {} -W 1 -G 7".format(os.path.join(trace_dir, "virtio.cap")))
    remote_trace.trace_marker(TRACE_BEGIN_MSG)
    netperf_perf = netperf.run_netperf(vm, msg_size=netperf_msg_size)
    remote_trace.trace_marker(TRACE_END_MSG)
    print("Netperf performance: %s" % (netperf_perf, ))
    logger.info("Netperf performance: %s", netperf_perf)

    remote_trace.trace_off()
    remote_trace.disable_all_events()
    local_trace.trace_off()
    local_trace.disable_all_events()

    netperf_perf = netperf.run_netperf(vm, msg_size=netperf_msg_size)
    print("Base Netperf performance: %s" % (netperf_perf,))
    logger.info("Base Netperf performance: %s", netperf_perf)

    local_trace.read_trace_once(to_file=True)
    remote_trace.read_trace_once(to_file=True)
    # local_trace.trace_to_local_file_stop()

    local_trace.disable_all_events()

    # input("Press Enter to exit")
    vm.teardown()
    netserver_stop()


def trace2csv(dirname):
    traces = TraceFile(os.path.join(dirname, "trace_guest"))
    traces.parse()
    start, end = [n for n, e in enumerate(traces.events) if e.event == 'tracing_mark_write']

    with open(os.path.join(dirname, "virtio-calling.csv"), "w") as csvfile:
        csvwritter = csv.writer(csvfile)
        csvwritter.writerow(("timestamp", "cwnd", "inflight", "mss_now", "pacing_rate", "sk_wmem_alloc"))

        for event in traces.events[start:end+1]:
            if event.event == "tcp_send_info":
                content = [event.timestamp] + [field.split("=")[1] for field in event.info.split(",")]
                csvwritter.writerow(content)

    with open(os.path.join(dirname, "virtio-sending.csv"), "w") as csvfile:
        csvwritter = csv.writer(csvfile)
        csvwritter.writerow(("timestamp", "cwnd", "inflight", "mss_now", "pacing_rate"))

        for event, next_event in zip(traces.events[start:end], traces.events[start+1:end+1]):
            if event.event == "tcp_send_info" and next_event.event == "tcp_sending":
                content = [event.timestamp] + [field.split("=")[1] for field in event.info.split(",")]
                csvwritter.writerow(content)

    with open(os.path.join(dirname, "virtio-waiting.csv"), "w") as csvfile:
        csvwritter = csv.writer(csvfile)
        csvwritter.writerow(("timestamp", "wmem_queued", "sndbuf", "is_sleep"))

        for event in traces.events[start:end+1]:
            if event.event == "tcp_wait_for_memory":
                content = [event.timestamp] + [field.split("=")[1] for field in event.info.split(",")]
                csvwritter.writerow(content)

    c = Counter((e.event for e in traces.events[start:end]))
    logger.info(c)


def startup():
    import sys
    d = None
    size = None
    if len(sys.argv) > 1:
        d = sys.argv[1]
    if len(sys.argv) > 2:
        size = sys.argv[2]

    d = get_dir(d)

    os.makedirs(d, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.addHandler(logging.FileHandler(os.path.join(d, "log")))

    main(d, size)
    trace2csv(d)

    t = Traces(d)
    t.write_to_file(d, True)


if __name__ == "__main__":
    startup()
