import csv
import logging
import os
import shutil
import argparse
from collections import Counter, defaultdict
from functools import partial
from math import log2
import sys
import multiprocessing
from time import sleep

from kernel_traces.latency_parser2 import MainStats

MSG_SIZES = (64, 128, 256, 512,
             1024, 1448, 2048, 4096, 8192, 16384, 32768,
             # 65536
             )

sys.path.append("../..")

from kernel_traces.kernel_trace import Trace
from kernel_traces.trace_parser import Traces, TRACE_BEGIN_MSG, TRACE_END_MSG
from kernel_traces.latency_parser import exits_stats, latency_split_to_time_portions, throughput_split_to_time_portions
from sensors.netperf import NetPerfLatency, NetPerfTCP, netserver_start, netserver_stop, NetPerfTcpTSO
from utils.machine import localRoot
from utils.vms import Qemu, QemuE1000Max, QemuE1000NG, QemuLargeRingNG, VM, QemuNG

ORIG_QEMU = r"../qemu/build/x86_64-softmmu/qemu-system-x86_64"

# TMP_QEMU = r"/tmp/qemu/x86_64-softmmu/qemu-system-x86_64"
TMP_QEMU = ORIG_QEMU
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


class TracePerformance:
    def __init__(self, vm: VM, directory=None, netperf=None, msg_size=64, title="", auto_dir=False, name=None):
        self._vm = vm
        if directory:
            self._dir = directory
        else:
            self._dir = TMP_DIR

        if auto_dir:
            self._dir = os.path.join(self._dir,
                                     "{name}-{size}".format(name=self._vm.name,
                                                            size=msg_size)
                                     )
            if name:
                self._dir += "-{name}".format(name=name)

        logger.info("Dir: %s", self._dir)

        if netperf:
            self._netperf = netperf
        else:
            self._netperf = NetPerfLatency()
        self._msg_size = msg_size
        self._title = title

        # vm.netserver_core = "2"
        self.trace_parser = None

        self._host_tracer = None
        self._guest_tracer = None

        self._old_cpumask = ""

    def init_env(self, delete=False):
        if delete:
            if os.path.exists(self._dir):
                shutil.rmtree(self._dir, ignore_errors=True)

        os.makedirs(self._dir, exist_ok=True)

        if ORIG_QEMU != TMP_QEMU:
            shutil.copyfile(ORIG_QEMU, TMP_QEMU)
        root_logger = logging.getLogger()
        root_logger.addHandler(logging.FileHandler(os.path.join(self._dir, "log")))

        self.trace_parser = Traces(self._dir)

    def host_traces(self):
        assert self._host_tracer is None

        self._host_tracer = Trace(localRoot, os.path.join(self._dir, "trace_host"))
        self._host_tracer.setup()
        self._host_tracer.set_buffer_size(2000000)
        sleep(1)

        # if self._vm.cpu_to_pin:
        #     self._host_tracer.write_value("tracing_cpumask", str(1 << (int(self._vm.cpu_to_pin))))

        # clock sync with VM
        self._host_tracer.enable_event("kvm/kvm_write_tsc_offset")

        # interrupts
        # self._host_tracer.enable_event("kvm/kvm_set_irq")
        # self._host_tracer.enable_event("kvm/kvm_msi_set_irq")
        # self._host_tracer.enable_event("kvm/kvm_inj_virq")
        # self._host_tracer.enable_event("kvm/kvm_ioapic_set_irq")

        # exit events
        self._host_tracer.enable_event("kvm/kvm_exit")
        self._host_tracer.enable_event("kvm/kvm_entry")
        # self._host_tracer.enable_event("kvm/kvm_userspace_exit")
        self._host_tracer.enable_event("kvm/kvm_mmio")
        self._host_tracer.enable_event("kvm/kvm_msr")

        # sched
        self._host_tracer.set_event_filter("sched/sched_switch", r'prev_comm ~ "*qemu*" || next_comm ~ "*qemu*"')
        self._host_tracer.enable_event("sched/sched_switch")

        # self._host_tracer.set_event_filter("sched/sched_wakeup", r'comm~"*qemu*"')
        # self._host_tracer.enable_event("sched/sched_wakeup")

        # self._host_tracer.set_event_filter("sched/sched_waking", r'comm~"*qemu*"')
        # self._host_tracer.enable_event("sched/sched_waking")
        # self._host_tracer.uprobe_add_event("p", "e1000_set_kick", self._vm.exe, "e1000_set_kick")
        # self._host_tracer.uprobe_add_event("p", "e1000_kick_cb", self._vm.exe, "e1000_kick_cb")
        # self._host_tracer.uprobe_add_event("p", "qemu_mutex_lock_iothread", self._vm.exe, "qemu_mutex_lock_iothread")
        # self._host_tracer.uprobe_add_event("r", "qemu_mutex_lock_iothread_end", self._vm.exe, "qemu_mutex_lock_iothread")
        # self._host_tracer.uprobe_add_event("p", "qemu_mutex_unlock_iothread", self._vm.exe, "qemu_mutex_unlock_iothread")
        # self._host_tracer.uprobe_add_event("r", "qemu_mutex_unlock_iothread_end", self._vm.exe, "qemu_mutex_unlock_iothread")
        self._host_tracer.enable_event("irq/irq_handler_entry")
        self._host_tracer.enable_event("irq/irq_handler_exit")
        self._host_tracer.enable_event("irq_vectors")

        self._host_tracer.enable_event("syscalls")

        # self._host_tracer.kprobe_add("p:import_iovec import_iovec")
        # self._host_tracer.kprobe_add("r:import_iovec_end import_iovec")
        # self._host_tracer.kprobe_add("p:tun_get_user tun_get_user")
        # self._host_tracer.kprobe_add("r:tun_get_user_end tun_get_user")
        #
        # self._host_tracer.kprobe_add("p:netif_receive_skb netif_receive_skb")
        # self._host_tracer.kprobe_add("r:netif_receive_skb_end netif_receive_skb")
        # # self._host_tracer.enable_event("net/netif_receive_skb")
        # # self._host_tracer.enable_event("net/netif_receive_skb_entry")
        # # self._host_tracer.enable_event("net/netif_rx_ni_entry")

        self._host_tracer.kprobe_enable()
        self._host_tracer.uprobe_enable()
        self._host_tracer.empty_trace()
        self._host_tracer.trace_on()

    def guest_traces(self):
        assert self._guest_tracer is None

        self._guest_tracer = Trace(self._vm.root, os.path.join(self._dir, "trace_guest"))
        self._guest_tracer.setup()
        self._guest_tracer.set_buffer_size(600000)

        self._guest_tracer.enable_event("power/cpu_idle")
        self._guest_tracer.enable_event("syscalls/sys_enter_sendto")
        # self._guest_tracer.enable_event("syscalls/sys_enter_recvfrom")
        self._guest_tracer.enable_event("syscalls/sys_exit_recvfrom")

        #sched
        self._guest_tracer.set_event_filter("sched/sched_switch", r'prev_comm ~ "*netperf*" || next_comm ~ "*netperf*"')
        self._guest_tracer.enable_event("sched/sched_switch")

        # net
        self._guest_tracer.enable_event("net/net_dev_start_xmit")
        self._guest_tracer.enable_event("net/net_dev_xmit")
        self._guest_tracer.enable_event("net/net_dev_recv_start")
        self._guest_tracer.enable_event("net/net_dev_recv_end")

        self._guest_tracer.enable_event("net/net_exit_before")
        self._guest_tracer.enable_event("net/net_exit_after")

        # irq
        self._guest_tracer.enable_event("irq/irq_handler_entry")
        self._guest_tracer.enable_event("irq/irq_handler_exit")
        self._host_tracer.enable_event("irq_vectors")

        self._guest_tracer.enable_event("napi")

        # self._guest_tracer.enable_event("tcp/tcp_xmit_break")

        self._guest_tracer.kprobe_add("p:recv_start virtnet_receive")
        self._guest_tracer.kprobe_add("r:recv_end virtnet_receive")

        self._guest_tracer.kprobe_add("p:recv_start e1000_clean_rx_irq")
        self._guest_tracer.kprobe_add("r:recv_end e1000_clean_rx_irq")

        self._guest_tracer.kprobe_add("p:napi_receive_start napi_gro_receive")
        self._guest_tracer.kprobe_add("r:napi_receive_end napi_gro_receive")

        self._guest_tracer.kprobe_add("p:e1000_update_stats e1000_update_stats")
        self._guest_tracer.kprobe_add("r:e1000_update_stats_end e1000_update_stats")

        # recieve checksum validation
        self._guest_tracer.kprobe_add("p:dev_gro_receive dev_gro_receive")
        self._guest_tracer.kprobe_add("r:dev_gro_receive_end dev_gro_receive")

        # tcp stack boundries
        self._guest_tracer.kprobe_add("p:netif_receive_skb_internal netif_receive_skb_internal")
        self._guest_tracer.kprobe_add("r:netif_receive_skb_internal_end netif_receive_skb_internal")
        self._guest_tracer.kprobe_add("p:dev_hard_start_xmit dev_hard_start_xmit")
        self._guest_tracer.kprobe_add("r:dev_hard_start_xmit_end dev_hard_start_xmit")

        # self._guest_tracer.kprobe_add("p:ip_rcv_finish ip_rcv_finish")
        # self._guest_tracer.kprobe_add("r:ip_rcv_finish_end ip_rcv_finish")
        # self._guest_tracer.kprobe_add("p:tcp_write_xmit tcp_write_xmit")
        # self._guest_tracer.kprobe_add("r:tcp_write_xmit_end tcp_write_xmit")
        #
        # self._guest_tracer.kprobe_add("p:dev_queue_xmit dev_queue_xmit")
        # self._guest_tracer.kprobe_add("r:dev_queue_xmit_end dev_queue_xmit")
        #
        # self._guest_tracer.kprobe_add("p:tcp_v4_rcv tcp_v4_rcv")
        # self._guest_tracer.kprobe_add("r:tcp_v4_rcv_end tcp_v4_rcv")
        #
        # for n in ("tcp_v4_do_rcv", "tcp_rcv_established", "__tcp_push_pending_frames", "tcp_write_xmit"):
        #     self._guest_tracer.kprobe_add("p:{name} {name}".format(name=n))
        #     self._guest_tracer.kprobe_add("r:{name}_end {name}".format(name=n))

        # self._guest_tracer.kprobe_add("p:validate_xmit_skb_list validate_xmit_skb_list")
        # self._guest_tracer.kprobe_add("r:validate_xmit_skb_list_end validate_xmit_skb_list")

        # self._guest_tracer.kprobe_add("p:tcp_ack tcp_ack")
        # self._guest_tracer.kprobe_add("r:tcp_ack_end tcp_ack")

        # self._guest_tracer.write_value("current_tracer", "function_graph")
        # self._guest_tracer.write_value("set_graph_function", "netif_receive_skb_internal")

        self._guest_tracer.kprobe_enable()
        self._guest_tracer.uprobe_enable()

        self._guest_tracer.empty_trace()
        self._guest_tracer.trace_on()

    def run_netperf(self, runtime=None):
        self._host_tracer.trace_marker(TRACE_BEGIN_MSG, cpu=2)
        if runtime is not None:
            self._netperf.runtime = runtime
        netperf_perf = self._netperf.run_netperf(self._vm, msg_size=self._msg_size)
        self._host_tracer.trace_marker(TRACE_END_MSG, cpu=2)
        print("Netperf performance: %s" % (netperf_perf,))
        logger.info("Netperf performance: %s", netperf_perf)

    def copy_maps(self):
        try:
            os.unlink(os.path.join(self._dir, "maps"))
        except:
            pass
        shutil.copy("/proc/{}/maps".format(self._vm.get_pid()), os.path.join(self._dir, "maps"))

    def merge_traces(self):
        logger.info("Merging traces")
        self.trace_parser.parse()
        self.trace_parser.write_to_file(self._dir, True)

    def run(self):

        try:
            self._vm.setup()
            self.host_traces()
            self._vm.run()
            self.guest_traces()
            self.run_netperf()
            self._host_tracer.trace_off()
            self._guest_tracer.trace_off()

            logger.info("Test again without traces:")
            self.run_netperf(10)
            self.run_netperf(10)
            self.run_netperf(10)

        finally:
            try:
                self._guest_tracer.read_trace_once(to_file=True)
                self._host_tracer.read_trace_once(to_file=True, cpu="2")
                # self._host_tracer.read_trace_once(to_file=True, filename=os.path.join(self._dir, "full_trace"))
                self._host_tracer.set_buffer_size(1000)
            except:
                import traceback
                traceback.print_exc()
            self.copy_maps()
            self._vm.teardown()
            try:
                self._host_tracer.disable_all_events()
            except:
                pass

        self.merge_traces()

    def stats(self):
        new_stats = MainStats(self.trace_parser, os.path.join(self._dir, "new"), size=self._msg_size)
        os.makedirs(os.path.join(self._dir, "new"), exist_ok=True)
        # new_stats.attr = "time_median"
        new_stats.attr = "time_avg"
        new_stats.run(new_stats.TYP_VIRTIO if "virtio" in self._vm.name else new_stats.TYP_E1000)

        # exits_stats(self.trace_parser, self._dir, self._title)
        # if isinstance(self._netperf, NetPerfLatency):
        #     # Latency only
        #     latency_split_to_time_portions(self.trace_parser, self._dir, self._title)
        # else:
        #     # Throughput only
        #     throughput_split_to_time_portions(self.trace_parser, self._dir, self._title)


def create_vm_base():
    base = QemuNG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                  guest_ip="10.10.0.43",
                  host_ip="10.10.0.44")
    base.bootwait = 30
    base.netserver_core = 3
    # base.netserver_nice = -10
    base.mem = 1024 * 6
    return base


def create_vm_e1000_base():
    vm = QemuE1000NG(disk_path=r"/homes/bdaviv/repos/e1000-improv/vms/ubuntu.img",
                     guest_ip="10.10.0.43",
                     host_ip="10.10.0.44")
    vm.bootwait = 30
    vm.netserver_core = 3
    vm.mem = 1024*6
    return vm


def create_vm_virtio():
    virtio = create_vm_base()
    virtio.ethernet_dev = virtio.QEMU_VIRTIO
    virtio.name = "virtio"
    return virtio


def create_vm_virtio_batch():
    virio = create_vm_virtio()
    virio.e1000_options["NG_notify_batch"] = "on"
    virio.name += "-batch"
    virio.is_io_thread_nice = True
    virio.io_nice = 1
    return virio


def create_vm_virtio_vhost():
    virtio = create_vm_virtio()
    virtio.vhost = True
    virtio.name += "-vhost"
    return virtio


def create_vm_virtio_exits():
    virtio = create_vm_virtio()
    virtio.name += "-exits"
    virtio.is_io_thread_nice = True
    virtio.io_nice = 10
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
    e1000_halt.e1000_options["NG_disable_TXDW"] = "on"
    e1000_halt.name += "-no_rdt"
    return e1000_halt


def create_vm_e1000_halt_no_rdt_send_recv_kick():
    e1000_halt = create_vm_e1000_halt_no_rdt()
    e1000_halt.e1000_options["NG_force_iothread_send"] = "on"
    # e1000_halt.e1000_options["NG_force_iothread_wait_recv"] = "on"
    e1000_halt.e1000_options["NG_fast_iothread_kick"] = "on"
    e1000_halt.name += "_sim"
    # e1000_halt.netserver_core = 2
    return e1000_halt


def create_vm_e1000_halt_no_rdt_send_recv_kick_intr():
    e1000_halt = create_vm_e1000_halt_no_rdt_send_recv_kick()
    e1000_halt.e1000_options["NG_interrupt_mode"] = 1
    e1000_halt.name += "_intr"
    # e1000_halt.netserver_core = 2
    return e1000_halt


def create_vm_e1000_halt_no_rdt_send_recv_kick_intr_no_itr():
    e1000_no_itr = create_vm_e1000_halt_no_rdt_send_recv_kick_intr()
    e1000_no_itr.name += "-no_itr"
    e1000_no_itr.static_itr = True
    e1000_no_itr.ethernet_dev = e1000_no_itr.QEMU_E1000_BETTER
    return e1000_no_itr


def create_vm_e1000_halt_no_rdt_send_recv_kick_intr_no_itr2():
    # force iothread from kick!
    e1000_no_itr = create_vm_e1000_halt_no_rdt_send_recv_kick_intr_no_itr()
    e1000_no_itr.e1000_options["NG_force_iothread_send"] = "on"
    e1000_no_itr.e1000_options["NG_fast_iothread_kick"] = "off"
    # e1000_no_itr.e1000_options["NG_force_iothread_wait_recv"] = "on"
    e1000_no_itr.name += "2"
    e1000_no_itr.is_io_thread_nice = True
    e1000_no_itr.io_nice = -1
    return e1000_no_itr


def create_vm_e1000_halt_no_rdt_send_recv_kick_intr_no_itr2_rxcsum():
    e1000_no_itr = create_vm_e1000_halt_no_rdt_send_recv_kick_intr_no_itr2()
    e1000_no_itr.e1000_options["NG_enable_rx_checksum"] = "on"
    e1000_no_itr.name += "_rxcsum"
    return e1000_no_itr


VMS = {
    "virtio": create_vm_virtio,
    "virtio_batch": create_vm_virtio_batch,
    "virtio_vhost": create_vm_virtio_vhost,
    "virtio_exits": create_vm_virtio_exits,
    "e1000-baseline": create_vm_e1000,
    "e1000_skb_orphan": create_vm_e1000_skb_orphan,
    "e1000_halt": create_vm_e1000_halt,
    "e1000_halt_no_rdt": create_vm_e1000_halt_no_rdt,
    "e1000_halt_no_rdt_sim": create_vm_e1000_halt_no_rdt_send_recv_kick,
    "e1000_halt_no_rdt_sim_intr": create_vm_e1000_halt_no_rdt_send_recv_kick_intr,
    "e1000_halt_no_rdt_sim_intr_no_itr": create_vm_e1000_halt_no_rdt_send_recv_kick_intr_no_itr,
    "e1000_halt_no_rdt_sim_intr_no_itr2": create_vm_e1000_halt_no_rdt_send_recv_kick_intr_no_itr2,
    "e1000_halt_no_rdt_sim_intr_no_itr2_rxcsum": create_vm_e1000_halt_no_rdt_send_recv_kick_intr_no_itr2_rxcsum,
}


def create_arg_parser():
    arg_parser = argparse.ArgumentParser(description="Trace VM performance")
    arg_parser.add_argument("--latency", help="Use latency mode", action='store_true')
    arg_parser.add_argument("--throughput", help="Use throughput mode", action='store_true')
    arg_parser.add_argument("--throughput-tso", help="Use throughput TSO mode", action='store_true')
    arg_parser.add_argument("--vm", help="Set VM config", choices=VMS.keys(), required=True)
    arg_parser.add_argument("--msg_size", default=64)
    arg_parser.add_argument("--runtime", default=5)
    arg_parser.add_argument("--batch_size", default=None)
    arg_parser.add_argument("--stats-only", action="store_true", default=False)
    arg_parser.add_argument("--auto-dir", action="store_true", default=False)
    arg_parser.add_argument("--name", default=None)
    arg_parser.add_argument("--multi", action="store_true", default=False)
    arg_parser.add_argument("--batch", action="store_true", default=False)
    arg_parser.add_argument("directory")
    return arg_parser


def stats_only(vm, netperf, msg_size, directory, title, auto_dir, name):
    perf = TracePerformance(vm=vm,
                            netperf=netperf,
                            msg_size=msg_size,
                            directory=directory,
                            title=vm,
                            auto_dir=auto_dir,
                            name=name,
                            )
    perf.init_env(False)
    perf.stats()


def parse_args():
    arg_parser = create_arg_parser()
    args = arg_parser.parse_args()
    return args


def runner(args):
    # arg_parser = create_arg_parser()
    # args = arg_parser.parse_args()

    if args.latency:
        netperf = NetPerfLatency(runtime=args.runtime)
    elif args.throughput:
        netperf = NetPerfTCP(runtime=args.runtime)
    elif args.throughput_tso:
        netperf = NetPerfTcpTSO(runtime=args.runtime)
    else:
        assert "Missing mode"

    vm = VMS[args.vm]()

    if args.batch_size:
        vm.e1000_options["x-txburst"] = str(args.batch_size)
        netperf.batch_size = int(args.batch_size)

    if not args.multi:
        perf = TracePerformance(vm=vm,
                                netperf=netperf,
                                msg_size=args.msg_size,
                                directory=args.directory,
                                title=args.vm,
                                auto_dir=args.auto_dir,
                                name=args.name,
                                )
        if not args.stats_only:
                perf.init_env(True)
                perf.run()
        else:
            perf.init_env(False)

        perf.stats()

    if args.multi:
        stats_func = partial(stats_only,
                             vm=vm,
                             netperf=netperf,

                             directory=args.directory,
                             title=args.vm,
                             auto_dir=args.auto_dir,
                             name=args.name,
                             )
        pool = multiprocessing.Pool(processes=4)
        for size in MSG_SIZES:
            print("start run for ", size)
            pool.apply_async(stats_func, kwds={'msg_size': size})
        pool.close()
        pool.join()


def main():
    args = parse_args()
    if args.batch:
        for size in MSG_SIZES:
            args.msg_size = size
            runner(args)
    else:
        runner(args)


def pm(*args):
    import pdb
    pdb.pm()


if __name__ == "__main__":
    import sys

    sys.excepthook = pm
    try:
        main()
    except KeyboardInterrupt:
        pass
