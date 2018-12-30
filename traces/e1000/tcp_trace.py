import csv
import logging
import os
import shutil
from collections import Counter, defaultdict
from math import log2

from kernel_traces.kernel_trace import Trace
from kernel_traces.trace_parser import Traces, TRACE_BEGIN_MSG, TRACE_END_MSG, delta2time, TraceFile
from sensors.netperf import NetPerfLatency, NetPerfTCP, netserver_start, netserver_stop
from utils.machine import localRoot
from utils.shell_utils import run_command_async
from utils.vms import Qemu, QemuE1000Max, QemuE1000NG, QemuLargeRingNG

# ORIG_QEMU = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build/x86_64-softmmu/qemu-system-x86_64"
# ORIG_QEMU = r"/home/bdaviv/repos/e1000-improv/qemu-2.2.0/build-trace/x86_64-softmmu/qemu-system-x86_64"
ORIG_QEMU = r"/homes/bdaviv/repos/msc-ng/qemu-ng/build/x86_64-softmmu/qemu-system-x86_64"
# ORIG_QEMU = r"/homes/bdaviv/repos/msc-ng/qemu-ng/build-debug/x86_64-softmmu/qemu-system-x86_64"
TMP_QEMU = r"/tmp/qemu/x86_64-softmmu/qemu-system-x86_64"
TMP_QEMU = ORIG_QEMU
Qemu.QEMU_EXE = TMP_QEMU

TMP_DIR = r"/tmp/traces"

# MSG_SIZE = "16K"
MSG_SIZE = "64"

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def create_vm_base():
    base = QemuNG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                  guest_ip="10.10.0.43",
                  host_ip="10.10.0.44")
    base.bootwait = 10
    return base


def create_vm_e1000_base():
    vm = QemuE1000NG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
                     guest_ip="10.10.0.43",
                     host_ip="10.10.0.44")
    vm.bootwait = 10
    return vm


def create_vm_virtio():
    virtio = create_vm_base()
    virtio.ethernet_dev = virtio.QEMU_VIRTIO
    virtio.name = "virtio"
    return virtio


def create_vm_virtio_vhost():
    virtio = create_vm_virtio()
    virtio.vhost = True
    virtio.name += "-vhost"
    return virtio


def create_vm_e1000():
    e1000_baseline = create_vm_base()
    e1000_baseline.ethernet_dev = e1000_baseline.QEMU_E1000
    e1000_baseline.name = "E1000-baseline"
    return e1000_baseline


def create_vm_e1000_skb_orphan():
    e1000_skb_orphan = create_vm_e1000_base()
    e1000_skb_orphan.is_io_thread_nice = False
    e1000_skb_orphan.e1000_options["NG_interrupt_mul"] = 10
    e1000_skb_orphan.e1000_options["NG_interrupt_mode"] = 0
    e1000_skb_orphan.kernel_cmdline_additional = "e1000.NG_flags=1"
    e1000_skb_orphan.name = "E1000-skb_orphan"
    return e1000_skb_orphan


def create_vm_e1000_halt():
    e1000_halt = create_vm_e1000_skb_orphan()
    e1000_halt.name = "E1000-halt"
    e1000_halt.e1000_options["NG_parahalt"] = "on"
    # e1000_halt.e1000_options["NG_disable_iothread_lock"] = "on"
    # e1000_halt.e1000_options["NG_tx_iothread"] = "off"
    e1000_halt.e1000_options["NG_interrupt_mode"] = 0
    e1000_halt.e1000_options["NG_interrupt_mul"] = 0
    e1000_halt.e1000_options["mitigation"] = "off"
    return e1000_halt


def create_vm_e1000_halt_no_rdt():
    e1000_halt = create_vm_e1000_halt()
    e1000_halt.e1000_options["NG_disable_rdt_jump"] = "on"
    e1000_halt.name += "-no_rdt"
    return e1000_halt

# class QemuLargeRing(QemuE1000Max):
#     def configure_guest(self):
#         super(QemuLargeRing, self).configure_guest()
#         self.remote_command("sudo ethtool -G eth0 rx 4096")
#         self.remote_command("sudo ethtool -G eth0 tx 4096")


def get_dir(directory=None):
    if directory:
        return directory
    else:
        return TMP_DIR


def main(directory=None):
    trace_dir = get_dir(directory)

    if ORIG_QEMU != TMP_QEMU:
        shutil.copyfile(ORIG_QEMU, TMP_QEMU)
    os.makedirs(trace_dir, exist_ok=True)

    netserver_start()
    # vm = QemuE1000NG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/vm.img",
    #                  guest_ip="10.10.0.43",
    #                  host_ip="10.10.0.44")
    # vm.netperf_test_params = "-C"
    # vm.kernel_cmdline_additional = "e1000.NG_flags=1" # skb_orphan
    # vm.e1000_options["NG_interrupt_mode"] = 2
    # vm.large_queue = True
    # vm.queue_size = 1024*4
    # vm.e1000_options["NG_parabatch"] = "on"
    # vm.e1000_options["NG_interrupt_mode"] = 1
    # vm.e1000_options["NG_interrupt_mul"] = 1
    # vm.e1000_options["NG_disable_iothread_lock"] = "on"
    vm = create_vm_e1000_halt_no_rdt()

    # para halt mode
    # vm.e1000_options["NG_parahalt"] = "on"
    # # vm.e1000_options["NG_disable_iothread_lock"] = "on"
    # # vm.e1000_options["NG_tx_iothread"]z = "off"
    # vm.e1000_options["NG_interrupt_mode"] = 0
    # vm.e1000_options["NG_interrupt_mul"] = 0
    # vm.e1000_options["mitigation"] = "off"
    # vm.large_queue = True
    # vm.queue_size = 512

    # vm.ethernet_dev = 'e1000-82545em'
    # vm.addiotional_guest_command = 'sudo ethtool -C eth0 rx-usecs 3000'

    local_trace = Trace(localRoot, os.path.join(trace_dir, "trace_host"))
    local_trace.setup()
    local_trace.set_buffer_size(1000000)

    local_trace.enable_event("kvm/kvm_write_tsc_offset")
    local_trace.enable_event("kvm/kvm_set_irq")
    local_trace.enable_event("kvm/kvm_msi_set_irq")
    local_trace.enable_event("kvm/kvm_inj_virq")
    local_trace.enable_event("kvm/kvm_ioapic_set_irq")
    local_trace.enable_event("kvm/kvm_exit")
    local_trace.enable_event("kvm/kvm_entry")
    local_trace.enable_event("kvm/kvm_userspace_exit")
    local_trace.enable_event("kvm/kvm_mmio")

    local_trace.set_event_filter("sched/sched_switch", r'prev_comm ~ "*qemu*" || next_comm ~ "*qemu*"')
    local_trace.enable_event("sched/sched_switch")

    local_trace.set_event_filter("sched/sched_wakeup", r'comm~"*qemu*"')
    local_trace.enable_event("sched/sched_wakeup")

    local_trace.set_event_filter("sched/sched_waking", r'comm~"*qemu*"')
    local_trace.enable_event("sched/sched_waking")

    # objdump -tT /tmp/qemu-system-x86_64 |grep .text|grep virtio_queue_notify_vq
    ## local_trace.uprobe_add("p:virtio_queue_notify_vq /tmp/qemu-system-x86_64:0x1bfba6")
    # local_trace.uprobe_add_event("p", "virtio_queue_notify_vq", TMP_QEMU, "virtio_queue_notify_vq")
    # objdump -tT /tmp/qemu-system-x86_64 |grep .text|grep kvm_vcpu_ioctl
    ## local_trace.uprobe_add("p:kvm_vcpu_ioctl /tmp/qemu-system-x86_64:0x16a886 cmd=%si")
    # local_trace.uprobe_add_event("p", "kvm_vcpu_ioctl", TMP_QEMU, "kvm_vcpu_ioctl", "cmd=%si")
    local_trace.uprobe_add_event("p", "tap_write_packet", TMP_QEMU, "tap_write_packet")
    local_trace.uprobe_add_event("p", "e1000_set_kick", TMP_QEMU, "e1000_set_kick")
    local_trace.uprobe_add_event("r", "e1000_set_kick_end", TMP_QEMU, "e1000_set_kick")
    local_trace.uprobe_add_event("p", "e1000_receive_batch_finished", TMP_QEMU, "e1000_receive_batch_finished",
                                 "packets=%si interrupt_packets=+209052\(%di\):u32")
    local_trace.uprobe_add_event("r", "tap_recv_packets_end", TMP_QEMU, "tap_send")
    local_trace.uprobe_add_event("p", "tap_recv_packets", TMP_QEMU, "tap_send")

    local_trace.uprobe_add_event("r", "all_cpu_idle_end", TMP_QEMU, "all_cpu_threads_idle_ex", misc=r"result=\$retval")
    local_trace.uprobe_add_event("p", "all_cpu_idle", TMP_QEMU, "all_cpu_threads_idle_ex")
    # local_trace.uprobe_add_event("p", "qemu_bh_schedule", TMP_QEMU, "qemu_bh_schedule")
    local_trace.uprobe_add_event("p", "set_tctl", TMP_QEMU, "set_tctl")
    local_trace.uprobe_add_event("p", "e1000_mit_timer", TMP_QEMU, "e1000_mit_timer")

    # local_trace.uprobe_add_event("p", "qemu_clock_run_all_timers", TMP_QEMU, "qemu_clock_run_all_timers")
    # local_trace.uprobe_add_event("r", "qemu_clock_run_all_timers_end", TMP_QEMU, "qemu_clock_run_all_timers", misc=r"result=\$retval")
    # local_trace.uprobe_add_event("r", "timerlistgroup_deadline_ns", TMP_QEMU, "timerlistgroup_deadline_ns", misc=r"result=\$retval")
    # local_trace.uprobe_add_event("r", "os_host_main_loop_wait", TMP_QEMU, "os_host_main_loop_wait", misc=r"result=\$retval")
    local_trace.uprobe_add_event("p", "aio_bh_call", TMP_QEMU, "aio_bh_call")
    local_trace.uprobe_add_event("p", "e1000_net_bh_tx", TMP_QEMU, "e1000_net_bh_tx")
    local_trace.uprobe_add_event("p", "qemu_bh_schedule", TMP_QEMU, "qemu_bh_schedule")
    local_trace.uprobe_add_event("r", "qemu_bh_schedule_end", TMP_QEMU, "qemu_bh_schedule")
    local_trace.uprobe_add_event("p", "event_notifier_set", TMP_QEMU, "event_notifier_set")
    local_trace.uprobe_add_event("r", "event_notifier_set_end", TMP_QEMU, "event_notifier_set")
    local_trace.uprobe_add_event("p", "notify_event_cb", TMP_QEMU, "notify_event_cb")
    local_trace.uprobe_add_event("p", "event_notifier_test_and_clear", TMP_QEMU, "event_notifier_test_and_clear")
    local_trace.uprobe_add_event("p", "aio_notify", TMP_QEMU, "aio_notify")
    local_trace.uprobe_add_event("r", "aio_notify_end", TMP_QEMU, "aio_notify")

    # local_trace.uprobe_add_event("p", "e1000_mmio_write", TMP_QEMU, "e1000_mmio_write")
    local_trace.uprobe_enable()

    local_trace.empty_trace()
    local_trace.trace_on()
    # local_trace.trace_to_local_file()

    vm.setup()
    vm.run()
    local_trace.set_event_filter("syscalls", r'common_pid=={}'.format(vm.get_pid()))
    local_trace.enable_event("syscalls")

    remote_trace = Trace(vm.root, os.path.join(trace_dir, "trace_guest"))
    remote_trace.setup()
    remote_trace.set_buffer_size(200000)
    remote_trace.enable_event("tcp")
    remote_trace.enable_event("net")
    remote_trace.enable_event("irq")
    remote_trace.enable_event("irq_vectors")
    remote_trace.enable_event("napi")
    remote_trace.enable_event("power/cpu_idle")
    remote_trace.enable_event("syscalls/sys_enter_sendto")
    remote_trace.enable_event("syscalls/sys_enter_recvfrom")
    # remote_trace.enable_event("irq/irq_handler_entry")
    # remote_trace.enable_event("e1000/e1000_pre_mem_op")
    # remote_trace.enable_event("e1000/e1000_post_mem_op")
    # remote_trace.enable_event("e1000/e1000_set_tdt")
    # remote_trace.enable_event("e1000/e1000_post_set_tdt")
    # remote_trace.kprobe_add("p:notify_begin vp_notify")
    # remote_trace.kprobe_add("r:notify_end vp_notify")
    remote_trace.kprobe_add("p:e1000_clean e1000_clean")
    remote_trace.kprobe_add("p:e1000_kick e1000_qemu_kick")
    remote_trace.kprobe_add("p:e1000_kick_halt e1000_halt_kick")
    remote_trace.kprobe_enable()

    # netperf = NetPerfTCP(None, runtime=15)
    netperf = NetPerfLatency(None, runtime=15)
    # netperf_perf = netperf.run_netperf(vm, msg_size="64K")
    # print("Netperf performance: %s" % (netperf_perf, ))
    # logger.info("Netperf performance: %s", netperf_perf)
    # input("Press Enter to start tracing")

    remote_trace.trace_on()

    run_command_async("tcpdump -i tap0 -s 100 -w {} -W 1 -G 7".format(os.path.join(trace_dir, "e1000.cap")))
    remote_trace.trace_marker(TRACE_BEGIN_MSG)
    netperf.runtime = 3
    netperf_perf = netperf.run_netperf(vm, msg_size=MSG_SIZE)
    remote_trace.trace_marker(TRACE_END_MSG)
    print("Netperf performance: %s" % (netperf_perf, ))
    logger.info("Netperf performance: %s", netperf_perf)

    remote_trace.trace_off()
    remote_trace.disable_all_events()
    local_trace.trace_off()
    local_trace.disable_all_events()

    netperf.runtime = 15
    netperf_perf = netperf.run_netperf(vm, msg_size=MSG_SIZE)
    print("Base Netperf performance: %s" % (netperf_perf,))
    logger.info("Base Netperf performance: %s", netperf_perf)

    local_trace.read_trace_once(to_file=True)
    remote_trace.read_trace_once(to_file=True)
    # local_trace.trace_to_local_file_stop()

    local_trace.disable_all_events()

    try:
        os.unlink(os.path.join(trace_dir, "maps"))
    except:
        pass
    shutil.copy("/proc/{}/maps".format(vm.get_pid()), os.path.join(trace_dir, "maps"))

    # input()

    vm.teardown()
    netserver_stop()


def trace2csv(dirname):
    traces = TraceFile(os.path.join(dirname, "trace_guest"))
    traces.parse()
    start, end = [n for n, e in enumerate(traces.events) if e.event == 'tracing_mark_write']

    with open(os.path.join(dirname, "e1000-calling.csv"), "w") as csvfile:
        csvwritter = csv.writer(csvfile)
        csvwritter.writerow(("timestamp", "cwnd", "inflight", "mss_now", "pacing_rate"))

        for event in traces.events[start:end+1]:
            if event.event == "tcp_send_info":
                content = [event.timestamp] + [field.split("=")[1] for field in event.info.split(",")]
                csvwritter.writerow(content)

    with open(os.path.join(dirname, "e1000-sending.csv"), "w") as csvfile:
        csvwritter = csv.writer(csvfile)
        csvwritter.writerow(("timestamp", "cwnd", "inflight", "mss_now", "pacing_rate", "sk_wmem_alloc"))

        for event, next_event in zip(traces.events[start:end], traces.events[start+1:end+1]):
            if event.event == "tcp_send_info" and next_event.event == "tcp_sending":
                content = [event.timestamp] + [field.split("=")[1] for field in event.info.split(",")]
                csvwritter.writerow(content)

    with open(os.path.join(dirname, "e1000-waiting.csv"), "w") as csvfile:
        csvwritter = csv.writer(csvfile)
        csvwritter.writerow(("timestamp", "wmem_queued", "sndbuf", "is_sleep"))

        for event in traces.events[start:end+1]:

            if event.event == "tcp_wait_for_memory":
                content = [event.timestamp] + [field.split("=")[1] for field in event.info.split(",")]
                csvwritter.writerow(content)

    c = Counter((e.event for e in traces.events[start:end]))
    logger.info(c)


def analysie_exit(trace: Traces, dirname):
    TYPE = "type"
    DURATION = "duration"
    ADDR = "addr"
    VALUE = "value"
    START = "start"
    END = "end"
    with open(os.path.join(dirname, "exit_info.csv"), "w") as csvfile:
        csvwriter = csv.DictWriter(csvfile, (TYPE, DURATION, START, END, ADDR, VALUE))
        csvwriter.writeheader()

        current_event_info = defaultdict(lambda: 0)
        for event in trace.get_test_events():
            if event.event == "kvm_entry":
                current_event_info[END] = int(event.timestamp)
                current_event_info[DURATION] = current_event_info[END] - current_event_info[START]
                csvwriter.writerow(current_event_info)
                current_event_info.clear()
            elif event.event == "kvm_exit":
                current_event_info[START] = int(event.timestamp)
                current_event_info[TYPE] = event.info.split()[1]
            elif event.event == "kvm_mmio":
                current_event_info[ADDR] = event.info.split()[5]
                current_event_info[VALUE] = event.info.split()[7]


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
    trace2csv(d)

    t = Traces(d)
    t.write_to_file(d, True)

    analysie_exit(t, d)


if __name__ == "__main__":
    startup()
