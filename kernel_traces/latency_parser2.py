import logging
import csv
import operator
import os
from statistics import mean, median

import matplotlib

from utils import read_cpu_speed

matplotlib.use('Agg')

from kernel_traces.trace_parser import Event


class Stats:
    def __init__(self, name):
        self.name = name
        self._events = list()
        self._delta_time = list()
        self._last_batch_time = list()
        self._last_batch_events = list()

    def __len__(self):
        return len(self._delta_time)

    def __lt__(self, other):
        return len(self) <= len(other)

    def __str__(self):
        # return "{:<31}: {:<6} cycles {:>11.2f} {:>11.2f} {:>11.2f} {:>11.2f} usec: {:>7.2f} {:>7.2f} {:>7.2f} {:>7.2f}".format(
        #     self.name,
        #     len(self),
        #     *self.get_stats(False),
        #     *self.get_stats(True),
        # )
        try:
            longest_idx = max(enumerate(self._delta_time), key=operator.itemgetter(1))[0]
            events = self._events[longest_idx][0].timestamp, self._events[longest_idx][1].timestamp,
        except (IndexError, ValueError):
            events = (0, 0)
        return "{:<31}: {:<6} cycles {:>11.2f} {:>11.2f} {:>11.2f} {:>11.2f} usec: {:>7.2f} {:>7.2f} {:>7.2f} {:>7.2f} longest: {}\\|{}".format(
            self.name,
            len(self),
            *self.get_stats(False),
            *self.get_stats(True),
            *events
        )

    def get_header(self):
        return "{:<31}: {:<6} cycles {:>11} {:>11} {:>11} {:>11} usec: {:>7} {:>7} {:>7} {:>7}".format(
            "Event Name", "Count", "min", "max", "avg", "mean", "min", "max", "avg", "mean"
        )

    def count_event(self, event_start, event_end):
        self._last_batch_events.append((event_start, event_end))
        self._last_batch_time.append(event_end.timestamp - event_start.timestamp)

    def count_event_series(self, events):
        if not len(events) % 2 == 0:
            # skip the first time it happens...
            return

        self._last_batch_events.append(tuple(events))
        delta_time = 0
        start = True
        for event in events:
            if start:
                delta_time -= event.timestamp
            else:
                delta_time += event.timestamp
            start = not start

        self._last_batch_time.append(delta_time)

    def finish_batch(self):
        self._events += self._last_batch_events
        self._delta_time += self._last_batch_time
        self._last_batch_events = list()
        self._last_batch_time = list()
        self.reset_batch()

    def reset_batch(self):
        self._last_batch_events = list()
        self._last_batch_time = list()

    @property
    def min(self):
        try:
            return min(self._delta_time)
        except ValueError:
            return 0

    @property
    def max(self):
        try:
            return max(self._delta_time)
        except ValueError:
            return 0

    @property
    def avg(self):
        try:
            return mean(self._delta_time)
        except ValueError:
            return 0

    @property
    def median(self):
        try:
            return median(self._delta_time)
        except ValueError:
            return 0

    @property
    def time_min(self):
        return self.min / read_cpu_speed()

    @property
    def time_max(self):
        return self.max / read_cpu_speed()

    @property
    def time_avg(self):
        return self.avg / read_cpu_speed()

    @property
    def time_median(self):
        return self.median / read_cpu_speed()

    def get_stats(self, use_time=True):
        min_val = self.min
        max_val = self.max
        avg_val = self.avg
        median_val = self.median
        if not use_time:
            return float(min_val), float(max_val), float(avg_val), float(median_val)
        else:
            cpu_speed = read_cpu_speed()
            return tuple(v / cpu_speed for v in
                         (float(min_val), float(max_val), float(avg_val), float(median_val)))


class StatsCounter(Stats):
    def count_counter(self, counter):
        self._delta_time.append(counter)

    def get_stats(self, use_time=True):
        return super().get_stats(False)


class ParseEvents:
    def handle_event(self, event):
        raise NotImplementedError()


class SendRecvStats(Stats, ParseEvents):
    def __init__(self):
        super().__init__("guest_sendrecv_netperf")
        self._last_send = None

    def handle_event(self, event):
        if event.event == "sys_sendto" and "netperf" in event.procname:
            self._last_send = event
        elif event.event == "sys_recvfrom" and "netperf" in event.procname \
                and self._last_send:
            self.count_event(self._last_send, event)

            self._last_send = None


class BatchStats(Stats, ParseEvents):
    def __init__(self):
        super().__init__("total_batch_time")
        self._last_event = None
        self._ignore_halt = False
        self._current_event_num = 0
        self.batch_event_stats = StatsCounter("events_per_batch")

    def handle_event(self, event):
        self._current_event_num += 1

        if event.event == event.EVENT_KVM_EXIT:
            if event.note and "KICK" in event.note.reason:
                self._ignore_halt = True

            if ((not self._ignore_halt and "HLT" in event.reason) or
                    (event.note and "KICK" in event.note.reason)):

                if self._last_event:
                    self.count_event(self._last_event, event)
                    self.batch_event_stats.count_counter(self._current_event_num)

                self._last_event = event
                self._current_event_num = 0
                return True

    def finish_batch(self):
        super().finish_batch()
        self.batch_event_stats.finish_batch()

    def reset_batch(self):
        super().reset_batch()
        self.batch_event_stats.reset_batch()


class SchedNetserver(Stats, ParseEvents):
    def __init__(self):
        super().__init__("host_netserver")
        self._last_event = None

    def handle_event(self, event):
        if event.source != event.EVENT_SOURCE_HOST:
            return

        if event.event == "sched_switch":
            if "next_comm=netserver" in event.info:
                self._last_event = event
            elif "prev_comm=netserver" in event.info:
                if self._last_event:
                    self.count_event(self._last_event, event)

                self._last_event = None


class SchedNetperf(Stats, ParseEvents):
    def __init__(self):
        super().__init__("guest_netperf")
        self._last_event = None

    def handle_event(self, event):
        if event.source != event.EVENT_SOURCE_GUEST:
            return

        if event.event == "sched_switch":
            if "next_comm=netperf" in event.info:
                self._last_event = event
            elif "prev_comm=netperf" in event.info:
                if self._last_event:
                    self.count_event(self._last_event, event)

                self._last_event = None


class SchedStats(Stats, ParseEvents):
    def __init__(self):
        super().__init__("host_sched_overhead")
        self._last_event = None

    def handle_event(self, event):
        if event.source != event.EVENT_SOURCE_HOST:
            return

        if event.event == "sched_switch":
            self._last_event = event
        else:
            if self._last_event:
                self.count_event(self._last_event, event)

            self._last_event = None


class NetDevXmitStats(Stats, ParseEvents):
    def __init__(self):
        super().__init__("guest_xmit")
        self._last_event = None

    def handle_event(self, event):
        if event.source != event.EVENT_SOURCE_GUEST:
            return

        if event.event == "net_dev_start_xmit":
            self._last_event = event
        elif event.event == "net_dev_xmit":
            if self._last_event:
                self.count_event(self._last_event, event)

            self._last_event = None


class SyswritevStats(Stats, ParseEvents):
    def __init__(self):
        super().__init__("host_writev")
        self._last_event = None
        self.writev_size = StatsCounter("writev_size")
        self.writev_vlen = StatsCounter("writev_vlen")

    def handle_event(self, event):
        if event.source != event.EVENT_SOURCE_HOST:
            return

        if event.event == "sys_writev":
            if "->" not in event.info:
                self._last_event = event

                vlen = int(event.info.split()[-1][:-1], 16)
                self.writev_vlen.count_counter(vlen)

            else:
                if self._last_event:
                    self.count_event(self._last_event, event)

                self._last_event = None

                length = int(event.info.split()[-1], 16)
                self.writev_size.count_counter(length)


class SysreadStats(Stats, ParseEvents):
    def __init__(self):
        super().__init__("host_read_packets")
        self._last_event = None

    def handle_event(self, event):
        if event.source != event.EVENT_SOURCE_HOST:
            return

        if event.event == "sys_read":
            if "->" not in event.info and "fd: 11" in event.info:
                self._last_event = event
            else:
                if "->" in event.info:
                    if self._last_event:
                        self.count_event(self._last_event, event)

                    self._last_event = None
                else:
                    # not fd 11
                    self._last_event = None


class SysreadDeltaStats(Stats, ParseEvents):
    def __init__(self):
        super().__init__("host_delta_read")
        self._last_read_start = None
        self._last_read_end = None

    def handle_event(self, event):
        if event.source != event.EVENT_SOURCE_HOST \
                or int(event.cpuNum) != 2:
            return

        if event.event == "sys_read":
            if "->" not in event.info and "fd: 11" in event.info:
                if self._last_read_end and self._last_read_start:
                    self.count_event(self._last_read_end, event)

                self._last_read_start = event
                self._last_read_end = None
            else:
                if "->" in event.info:
                    if self._last_read_start:
                        self._last_read_end = event
                else:
                    #  not fd 11, remove saved events
                    self._last_read_start = None
                    self._last_read_end = None
        else:
            self._last_read_end = None
            self._last_read_start = None


class SyswritevDeltaStats(Stats, ParseEvents):
    def __init__(self):
        super().__init__("host_delta_writev")
        self._last_read_start = None
        self._last_read_end = None

    def handle_event(self, event):
        if event.source != event.EVENT_SOURCE_HOST \
                or int(event.cpuNum) != 2:
            return

        if event.event == "sys_writev":
            if "->" not in event.info and "fd: 11" in event.info:
                if self._last_read_end and self._last_read_start:
                    self.count_event(self._last_read_end, event)

                self._last_read_start = event
                self._last_read_end = None
            else:
                if "->" in event.info:
                    if self._last_read_start:
                        self._last_read_end = event
                else:
                    #  not fd 11, remove saved events
                    self._last_read_start = None
                    self._last_read_end = None
        else:
            self._last_read_end = None
            self._last_read_start = None


class InterruptStats(Stats, ParseEvents):
    def __init__(self):
        super().__init__("guest_interrupt_handler")
        self._last_event = None

    def handle_event(self, event):
        if event.source != event.EVENT_SOURCE_GUEST:
            return

        if event.event == "irq_handler_entry" and (
                "virtio" in event.info
                or "eth" in event.info
        ):
            self._last_event = event
        elif event.event == "irq_handler_exit":
            if self._last_event:
                self.count_event(self._last_event, event)

            self._last_event = None


class ExitStats(ParseEvents):
    def __init__(self):
        self._results = dict()
        self._last_exit = None

    def __getitem__(self, item):
        return self._results.get(item, Stats(item))

    def count_event(self, name, start, end):
        if name not in self._results:
            self._results[name] = Stats(name)
        self._results[name].count_event(start, end)

    def finish_batch(self):
        for k in self._results:
            self._results[k].finish_batch()

    def reset_batch(self):
        for k in self._results:
            self._results[k].reset_batch()

    def handle_event(self, event):
        if event.event == Event.EVENT_KVM_EXIT:
            self._last_exit = event
        elif event.event == Event.EVENT_KVM_ENTRY and self._last_exit:
            reason = self._last_exit.reason
            if self._last_exit.note:
                reason += " " + self._last_exit.note.reason

            self.count_event(reason, self._last_exit, event)

            self._last_exit = None

    def get_results(self):
        return self._results


class HWExitStats(ParseEvents):
    HW_EXIT = "HW_exit"
    HW_ENRTY = "HW_entry"

    def __init__(self):
        self._results = dict()

        self._last_pre_exit = None
        self._last_exit = None

        self._last_entry = None
        self._last_post_entry = None

    def __getitem__(self, item):
        return self._results.get(item, Stats(item))

    def count_event(self, name, start, end):
        if name not in self._results:
            self._results[name] = Stats(name)
        self._results[name].count_event(start, end)

    def finish_batch(self):
        for k in self._results:
            self._results[k].finish_batch()

    def reset_batch(self):
        for k in self._results:
            self._results[k].reset_batch()

    def handle_event(self, event):
        if event.event == "net_exit_before":
            self._last_pre_exit = event
        elif event.event == Event.EVENT_KVM_EXIT:
            self._last_exit = event
            if self._last_pre_exit:
                reason = "HW-exit-" + self._last_exit.reason
                if self._last_exit.note:
                    reason += " " + self._last_exit.note.reason

                self.count_event(reason, self._last_pre_exit, event)
                self.count_event(self.HW_EXIT, self._last_pre_exit, event)

            self._last_pre_exit = None

        elif event.event == Event.EVENT_KVM_ENTRY:
            self._last_entry = event
        elif event.event == "net_exit_after":
            self._last_post_entry = event
            if self._last_entry and self._last_exit:
                reason = "HW-enter-" + self._last_exit.reason
                if self._last_exit.note:
                    reason += " " + self._last_exit.note.reason

                self.count_event(reason, self._last_entry, event)
                self.count_event(self.HW_ENRTY, self._last_entry, event)

            self._last_entry = None
            self._last_exit = None

    def get_results(self):
        return self._results


class InterruptIoctlStats(Stats, ParseEvents):
    def __init__(self):
        super().__init__("host_ioctl_interrupt")
        self._last_event = None

    def handle_event(self, event):
        if event.source != event.EVENT_SOURCE_HOST:
            return

        if event.event == "sys_ioctl":
            if "->" not in event.info and (
                    "cmd: 4020aea5" in event.info
                    or "cmd: ffffffffc008ae67" in event.info):
                self._last_event = event
            else:
                if self._last_event:
                    self.count_event(self._last_event, event)

                self._last_event = None


class RecvStats(Stats, ParseEvents):
    def __init__(self):
        super().__init__("guest_recv_func")
        self._last_event = list()

    def handle_event(self, event):
        if event.source != event.EVENT_SOURCE_GUEST:
            return

        if event.event == "net_dev_recv_start":
            # trace start of driver function
            self._last_event = list()
            self._last_event.append(event)
        elif event.event == "napi_receive_start":
            # pass the packet to TCP stack
            self._last_event.append(event)
        elif event.event == "napi_receive_end":
            # return from packet processing in TCP stack
            self._last_event.append(event)
        elif event.event == "net_dev_recv_end":
            # trace end of driver function
            self._last_event.append(event)
            self.count_event_series(self._last_event)
            self._last_event = list()


class WritevDeep(ParseEvents):
    def __init__(self):

        self.writev_size = StatsCounter("writev_size")
        self.writev_vlen = StatsCounter("writev_vlen")

        self.writev_import_iovec = Stats("writev_import_iovec")
        self.writev_tun_get_user = Stats("writev_tun_get_user")
        self.writev_receive_skb = Stats("writev_receive_skb")
        self.writev_stat = Stats("writev")

        self._last_writev = None
        self._last_import_iovec = None
        self._last_tun_get_user = None
        self._last_netif_receive_skb = None
        self.name = "writev_deep"

        self._stat_list = (
            self.writev_stat,
            self.writev_receive_skb, self.writev_tun_get_user,
            self.writev_import_iovec,
            self.writev_vlen, self.writev_size
        )

    def __len__(self):
        return 0

    def __lt__(self, other):
        return False

    def __str__(self):
        result = list()
        for p in self._stat_list:
            result.append(str(p))
        return "\n".join(result)

    def get_header(self):
        return self.writev_size.get_header()

    def handle_event(self, event):
        if event.event == "sys_writev":
            if "->" not in event.info:
                self._last_writev = event
                vlen = int(event.info.split()[-1][:-1], 16)
                self.writev_vlen.count_counter(vlen)
            else:  # end
                length = int(event.info.split()[-1], 16)
                self.writev_size.count_counter(length)
                if self._last_writev:
                    self.writev_stat.count_event(self._last_writev, event)
                self._last_writev = None
        if self._last_writev:
            if event.event == "import_iovec":
                self._last_import_iovec = event
            elif event.event == "import_iovec_end":
                self.writev_import_iovec.count_event(self._last_import_iovec, event)

            elif event.event == "tun_get_user":
                self._last_tun_get_user = event
            elif event.event == "tun_get_user_end":
                self.writev_tun_get_user.count_event(self._last_tun_get_user, event)

            elif event.event == "netif_receive_skb":
                self._last_netif_receive_skb = event
            elif event.event == "netif_receive_skb_end":
                self.writev_receive_skb.count_event(self._last_netif_receive_skb, event)

    def finish_batch(self):
        for p in self._stat_list:
            p.finish_batch()

    def reset_batch(self):
        for p in self._stat_list:
            p.reset_batch()


class TraceFunctionStats(Stats, ParseEvents):
    def __init__(self, func1, func2=None, source=Event.EVENT_SOURCE_GUEST, name=None):
        self._name1 = func1
        self._name2 = func2
        self._source = source
        self._last_event = None
        if name is None:
            name = "{}_{}-{}".format(source, func1, func2)
        super().__init__(name)
        self._last_event = list()

    def handle_event(self, event):
        if self._source and event.source != self._source:
            return

        if event.event == self._name1:
            self._last_event = list()
            self._last_event.append(event)
        elif self._name2 and event.event == self._name2:
            self._last_event.append(event)
        elif self._name2 and event.event == self._name2 + "_end":
            self._last_event.append(event)
        elif event.event == self._name1 + "_end":
            self._last_event.append(event)
            self.count_event_series(self._last_event)
            self._last_event = list()


class MainStats:
    ATTR = "time_avg"

    def __init__(self, traces, output_dir, size=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)

        self._traces = traces
        self._dir = output_dir
        self._size = size

        self._events = tuple(self._traces.get_test_events())

        self.translate_events()

        # parsers
        self._parse_send_recv = SendRecvStats()
        self._parse_batch = BatchStats()

        self._parse_exits = ExitStats()
        self._parse_hw_exits = HWExitStats()
        self._parse_sched = SchedStats()
        self._parse_xmit = NetDevXmitStats()
        self._parse_writev = SyswritevStats()
        self._parse_read = SysreadStats()
        self._parse_ioctl_interrupt = InterruptIoctlStats()
        self._parse_interrupt = InterruptStats()
        self._parse_recv = RecvStats()
        self._parse_netserver = SchedNetserver()
        self._parse_netperf = SchedNetperf()

        self._parse_delta_read = SysreadDeltaStats()
        self._parse_delta_writev = SyswritevDeltaStats()

        self._writev_deep = WritevDeep()
        self._parse_guest_recv_checksum = TraceFunctionStats("dev_gro_receive", name="guest_recv_checksum")
        self._parse_guest_tcp_stack = TraceFunctionStats("netif_receive_skb_internal", "dev_hard_start_xmit", Event.EVENT_SOURCE_GUEST, name="Guest TCP stack")

        self._parse_guest_tcp = TraceFunctionStats("netif_receive_skb_internal", "ip_rcv_finish", name="guest_tcp_func")
        self._parse_guest_tcp1 = TraceFunctionStats("ip_rcv_finish", "tcp_v4_rcv", name="guest_tcp_func1")
        self._parse_guest_tcp1_2 = TraceFunctionStats("tcp_v4_rcv", "tcp_write_xmit", name="guest_tcp_func1_2")
        self._parse_guest_tcp2 = TraceFunctionStats("tcp_write_xmit", "dev_queue_xmit", name="guest_tcp_func2")
        self._parse_guest_tcp3 = TraceFunctionStats("dev_queue_xmit", "dev_hard_start_xmit", name="guest_tcp_func3")
        self._parse_guest_tcp_ack = TraceFunctionStats("tcp_ack", name="guest_tcp_ack")

        self._general_parsers = [
            self._parse_sched,
            self._parse_xmit,
            self._parse_writev,
            self._parse_read,
            self._parse_ioctl_interrupt,
            self._parse_interrupt,
            self._parse_recv,
            self._parse_netserver,
            self._parse_netperf,

            self._parse_delta_read,
            self._parse_delta_writev,
            self._writev_deep,
            self._parse_guest_recv_checksum,
            self._parse_guest_tcp_stack,

            self._parse_guest_tcp,
            self._parse_guest_tcp1,
            self._parse_guest_tcp1_2,
            self._parse_guest_tcp2,
            self._parse_guest_tcp3,
            self._parse_guest_tcp_ack,
            TraceFunctionStats("tcp_v4_rcv", "tcp_v4_do_rcv", Event.EVENT_SOURCE_GUEST),
            TraceFunctionStats("tcp_v4_do_rcv", "tcp_rcv_established", Event.EVENT_SOURCE_GUEST),
            TraceFunctionStats("tcp_rcv_established", "__tcp_push_pending_frames", Event.EVENT_SOURCE_GUEST),
            TraceFunctionStats("__tcp_push_pending_frames", "tcp_write_xmit", Event.EVENT_SOURCE_GUEST),
            # TraceFunctionStats("tcp_write_xmit", Event.EVENT_SOURCE_GUEST),

        ]

        self.attr = self.ATTR

    TYP_E1000 = "E1000"
    TYP_VIRTIO = "VIRTIO"

    def run(self, typ=None):
        self.translate_events()
        self.parse_events()
        self.output_stats()

        if typ is None or typ == self.TYP_E1000:
            self.output_e1000_csv()
        elif typ == self.TYP_VIRTIO:
            self.output_virtio_csv()
        else:
            raise RuntimeError()
        # self.output_writev_deep_csv()

    def translate_events(self):
        last_exit = None
        for e in self._events:
            if e.event == Event.EVENT_KVM_EXIT:
                last_exit = e
            elif e.event == Event.EVENT_KVM_MMIO and last_exit:
                last_exit.note = e
            elif e.event == Event.EVENT_KVM_MSR and last_exit:
                last_exit.note = e

    def filter_events(self, event):
        return event.source == event.EVENT_SOURCE_GUEST or \
               (event.source == event.EVENT_SOURCE_HOST and
                event.cpuNum == "002")

    def is_event_invalid(self, event):
        return (
            event.event == "sys_fdatasync" or
            (event.event == "kvm_exit" and "EXTERNAL_INTERRUPT" in event.info) or
            (event.event == "kvm_exit" and "PREEMPTION_TIMER" in event.info) or
            (event.event == "local_timer_entry" or event.event == "local_timer_exit") or
            (event.source == event.EVENT_SOURCE_HOST and event.event == "irq_handler_entry") or
            (event.source == event.EVENT_SOURCE_HOST and event.event == "irq_handler_exit")
        )

    def parse_events(self):
        is_batch_invalid = False
        skiped_batches = 0
        for e in self._events:
            if self.filter_events(e):
                is_batch_invalid = is_batch_invalid or self.is_event_invalid(e)
                self._parse_exits.handle_event(e)
                self._parse_hw_exits.handle_event(e)
                self._parse_send_recv.handle_event(e)
                is_new_batch = self._parse_batch.handle_event(e)
                for p in self._general_parsers:
                    p.handle_event(e)

                if is_new_batch:
                    if not is_batch_invalid:
                        for parser in self._general_parsers:
                            parser.finish_batch()
                        self._parse_exits.finish_batch()
                        self._parse_hw_exits.finish_batch()
                        self._parse_send_recv.finish_batch()
                        self._parse_batch.finish_batch()
                    else:
                        for parser in self._general_parsers:
                            parser.reset_batch()
                        self._parse_exits.reset_batch()
                        self._parse_hw_exits.reset_batch()
                        self._parse_send_recv.reset_batch()
                        self._parse_batch.reset_batch()
                        skiped_batches += 1
                    is_batch_invalid = False
        self.logger.warning("Skip %d batches", skiped_batches)
        print("Skip %d batches" % (skiped_batches, ))

    def get_all_results(self):
        results = dict()
        results.update(self._parse_exits.get_results())
        results.update(self._parse_hw_exits.get_results())
        results.update({p.name: p for p in self._general_parsers})
        return results

    def output_stats(self):
        with open(os.path.join(self._dir, "stats.txt"), "w") as f:
            sorted_stats = sorted(self.get_all_results().values(), reverse=True)

            # headers
            f.write(sorted_stats[0].get_header())
            f.write("\n")

            f.write(str(self._parse_send_recv))
            f.write("\n")

            f.write(str(self._parse_batch))
            f.write("\n")
            f.write(str(self._parse_batch.batch_event_stats))
            f.write("\n")

            for stat in sorted_stats:
                f.write(str(stat))
                f.write("\n")
        print("finish")

    def _output_row(self, csv_writer, name, count, value, count_normalize=True, multiply=True):
        if isinstance(count, Stats):
            count = len(count)

        if count_normalize:
            count = round(count / len(self._parse_batch))

        if multiply:
            final = value * count
        else:
            final = value

        csv_writer.writerow([name, count, value, final])

    def _output_single_row(self, csv_writer, stat, name=None, count=None, count_normalize=True, multiply=True, attr=None):
        if name is None:
            name = stat.name
        if count is None:
            count = len(stat)

        if attr is None:
            attr = self.attr

        self._output_row(csv_writer, name, count, getattr(stat, attr), count_normalize=count_normalize, multiply=multiply)

    def _output_compute_row(self, csv_writer,
                            func, args, name=None, count=1, count_normalize=True):

        args_values = [getattr(arg, self.attr, arg) for arg in args]
        value = func(*args_values)

        self._output_row(csv_writer, name, count, value, count_normalize=count_normalize)

    def output_writev_deep_csv(self):
        with open(os.path.join(self._dir, "writev.csv"), "w") as f:
            writer = csv.writer(f)
            writer.writerow(["using %s" % (self.attr,), "msg size:", self._size, self._size])
            self._output_single_row(writer, self._writev_deep.writev_vlen, attr=self.attr.replace("time_", ""))
            self._output_single_row(writer, self._writev_deep.writev_size, attr=self.attr.replace("time_", ""))

            self._output_single_row(writer, self._writev_deep.writev_stat, multiply=True)
            self._output_single_row(writer, self._writev_deep.writev_import_iovec, multiply=True)
            self._output_single_row(writer, self._writev_deep.writev_tun_get_user, multiply=True)
            self._output_single_row(writer, self._writev_deep.writev_receive_skb, multiply=True)

    def output_e1000_csv(self):
        with open(os.path.join(self._dir, "proc.csv"), "w") as f:
            writer = csv.writer(f)
            writer.writerow(["using %s" % (self.attr,), "msg size:", self._size, self._size])

            writer.writerow(["name", "count per batch", "one", "total"])
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_EXIT], name="exit overhead", count_normalize=False, multiply=False)
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY], name="entry overhead", count_normalize=False, multiply=False)
            writer.writerow([])

            # batch
            self._output_single_row(writer, self._parse_batch, count_normalize=False, multiply=False)
            writer.writerow([])

            # send
            self._output_single_row(writer, self._parse_exits["EPT_MISCONFIG E1000 TDT"], name="TDT")
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_EXIT], count=self._parse_exits["EPT_MISCONFIG E1000 TDT"], name="TDT hw exit")
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY], count=self._parse_exits["EPT_MISCONFIG E1000 TDT"], name="TDT hw entry")
            self._output_compute_row(writer,
                                     lambda w, x, y, z, lw, lz: z - (w + x + y) * lw / lz,
                                     (
                                         self._parse_exits["EPT_MISCONFIG E1000 TDT"],
                                         self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY],
                                         self._parse_hw_exits[self._parse_hw_exits.HW_EXIT],
                                         self._parse_xmit,
                                         len(self._parse_exits["EPT_MISCONFIG E1000 TDT"]),
                                         len(self._parse_xmit)
                                     ),
                                     name="Guest xmit",
                                     count=self._parse_xmit,
                                     )
            writer.writerow([])

            # recv
            self._output_single_row(writer, self._parse_exits["EPT_MISCONFIG E1000 RDT"], name="RDT")
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_EXIT], count=self._parse_exits["EPT_MISCONFIG E1000 RDT"], name="RDT hw exit")
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY], count=self._parse_exits["EPT_MISCONFIG E1000 RDT"], name="RDT hw entry")
            self._output_compute_row(writer,
                                     lambda w, x, y, z, lw, lz: z - (w + x + y) * lw / lz ,
                                        (self._parse_exits["EPT_MISCONFIG E1000 RDT"],
                                         self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY],
                                         self._parse_hw_exits[self._parse_hw_exits.HW_EXIT],
                                         self._parse_recv,
                                         len(self._parse_exits["EPT_MISCONFIG E1000 RDT"]),
                                         len(self._parse_recv)
                                         ),
                                     name="Guest recv",
                                     count=self._parse_recv
                                     )
            writer.writerow([])

            # interrupt
            interrupt_exit_count = (
                                            len(self._parse_exits["EPT_MISCONFIG E1000 STATUS"]) +
                                            len(self._parse_exits["EPT_MISCONFIG E1000 IMC"]) +
                                            len(self._parse_exits["EPT_MISCONFIG E1000 IMS"]) +
                                            len(self._parse_exits["EPT_MISCONFIG E1000 ICR"]) +
                                            len(self._parse_exits["EPT_MISCONFIG E1000 ITR"]) +
                                            len(self._parse_exits["EOI_INDUCED"])
                                    )
            self._output_single_row(writer, self._parse_exits["EPT_MISCONFIG E1000 STATUS"], name="STATUS")
            self._output_single_row(writer, self._parse_exits["EPT_MISCONFIG E1000 IMC"], name="IMC")
            self._output_single_row(writer, self._parse_exits["EPT_MISCONFIG E1000 IMS"], name="IMS")
            self._output_single_row(writer, self._parse_exits["EPT_MISCONFIG E1000 ICR"], name="ICR")
            self._output_single_row(writer, self._parse_exits["EPT_MISCONFIG E1000 ITR"], name="ITR")
            self._output_single_row(writer, self._parse_exits["EOI_INDUCED"], name="EOI_INDUCED")
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_EXIT],
                                    name="interrupt exit overhead", count=interrupt_exit_count)
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY],
                                    name="interrupt entry overhead",
                                    count=interrupt_exit_count)
            self._output_compute_row(writer,
                                     lambda i, icr, imc, status, cnt, hw_exit, hw_entry: i - (icr + imc + status + cnt * (hw_entry + hw_exit)),
                                     (
                                         self._parse_interrupt,
                                         self._parse_exits["EPT_MISCONFIG E1000 ICR"],
                                         self._parse_exits["EPT_MISCONFIG E1000 IMC"],
                                         self._parse_exits["EPT_MISCONFIG E1000 STATUS"],
                                         3 if interrupt_exit_count else 0,  # number of exits during interrupt handler
                                         self._parse_hw_exits[self._parse_hw_exits.HW_EXIT] if interrupt_exit_count else 0,
                                         self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY] if interrupt_exit_count else 0,
                                     ),
                                     name="guest interrupt handler",
                                     count=self._parse_interrupt,
                                     )
            writer.writerow([])

            # hypervisor send

            self._output_single_row(writer, self._parse_writev)
            self._output_single_row(writer, self._parse_delta_writev, count=self._parse_writev)
            self._output_single_row(writer, self._parse_read)
            self._output_single_row(writer, self._parse_delta_read)

            self._output_single_row(writer, self._parse_sched)
            self._output_single_row(writer, self._parse_ioctl_interrupt)
            self._output_single_row(writer, self._parse_netserver)

            self._output_single_row(writer, self._parse_exits["MSR_WRITE MSR ICR"], name="MSR ICR")

            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY],
                                    name="msr entry overhead",
                                    count=self._parse_exits["MSR_WRITE MSR ICR"])
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_EXIT],
                                    name="msr exit overhead",
                                    count=self._parse_exits["MSR_WRITE MSR ICR"])

            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY],
                                    name="kick entry overhead",
                                    count=self._parse_batch)
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_EXIT],
                                    name="kick exit overhead",
                                    count=self._parse_batch)

            self._output_compute_row(writer,
                                     lambda kick,
                                            writev, writev_cnt, d_write,
                                            read, read_cnt, d_read,
                                            sched, sched_cnt,
                                            netserver, ioctl, overhead_exit, overhead_entry:
                                     kick - (
                                             (writev + d_write) * writev_cnt +
                                             (read + d_read) * read_cnt +
                                             netserver +
                                             sched * sched_cnt +
                                             ioctl + overhead_exit + overhead_entry),
                                     (
                                         self._parse_exits["EPT_MISCONFIG E1000 KICK"],

                                         self._parse_writev,
                                         round(len(self._parse_writev) / len(self._parse_batch)),
                                         self._parse_delta_writev,

                                         self._parse_read,
                                         round(len(self._parse_read) / len(self._parse_batch)),
                                         self._parse_delta_read,

                                         self._parse_sched,
                                         round(len(self._parse_sched) / len(self._parse_batch)),

                                         self._parse_netserver,
                                         self._parse_ioctl_interrupt,
                                         self._parse_hw_exits[self._parse_hw_exits.HW_EXIT],
                                         self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY]
                                     ),
                                     name="qemu iothread",
                                     count=self._parse_batch,
                                     )
            writer.writerow([])
            self._output_compute_row(writer, lambda perf, perf_cnt, batch_cnt: (perf * perf_cnt / batch_cnt),
                                     (self._parse_netperf, len(self._parse_netperf), len(self._parse_batch)),
                                     count=self._parse_batch,
                                     name="Guest Netperf")
            writer.writerow([])
            self._output_single_row(writer, self._parse_guest_recv_checksum)
            self._output_single_row(writer, self._parse_guest_tcp_stack)

            writer.writerow(["guest other", 1, "", "=D6-SUM(D7:D45)"])
            writer.writerow([])
            self._output_single_row(writer, self._parse_guest_tcp)
            self._output_single_row(writer, self._parse_guest_tcp1)
            self._output_single_row(writer, self._parse_guest_tcp2)
            self._output_single_row(writer, self._parse_guest_tcp3)
            self._output_single_row(writer, self._parse_guest_tcp1_2)
            writer.writerow([])

            self._output_single_row(writer, self._parse_writev.writev_vlen, attr=self.attr.replace("time_", ""))
            self._output_single_row(writer, self._parse_writev.writev_size, attr=self.attr.replace("time_", ""))

    def output_virtio_csv(self):
        with open(os.path.join(self._dir, "proc.csv"), "w") as f:
            writer = csv.writer(f)
            writer.writerow(["using %s" % (self.attr,), "msg size:", self._size, self._size])

            writer.writerow(["name", "count per batch", "one", "total"])
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_EXIT], name="exit overhead", count_normalize=False, multiply=False)
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY], name="entry overhead", count_normalize=False, multiply=False)
            writer.writerow([])

            # batch
            self._output_single_row(writer, self._parse_batch, count_normalize=False, multiply=False)
            writer.writerow([])

            # send
            self._output_single_row(writer, self._parse_exits["EPT_MISCONFIG"], name="KICK")
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_EXIT], count=self._parse_exits["EPT_MISCONFIG"], name="KICK hw exit")
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY], count=self._parse_exits["EPT_MISCONFIG"], name="KICK hw entry")
            self._output_compute_row(writer,
                                     lambda w, x, y, z, lw, lz: z - (w + x + y) * lw / lz,
                                     (
                                         self._parse_exits["EPT_MISCONFIG"],
                                         self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY],
                                         self._parse_hw_exits[self._parse_hw_exits.HW_EXIT],
                                         self._parse_xmit,
                                         len(self._parse_exits["EPT_MISCONFIG"]),
                                         len(self._parse_xmit)
                                     ),
                                     name="Guest xmit",
                                     count=self._parse_xmit,
                                     )
            writer.writerow([])

            # recv
            self._output_single_row(writer, self._parse_recv, name="Guest recv")

            writer.writerow([])

            # interrupt
            self._output_single_row(writer, self._parse_interrupt, name="guest interrupt handler")
            writer.writerow([])

            # hypervisor send
            self._output_single_row(writer, self._parse_writev)
            self._output_single_row(writer, self._parse_delta_writev, count=self._parse_writev)
            self._output_single_row(writer, self._parse_read)
            self._output_single_row(writer, self._parse_delta_read)

            self._output_single_row(writer, self._parse_sched)
            self._output_single_row(writer, self._parse_ioctl_interrupt)
            self._output_single_row(writer, self._parse_netserver)

            self._output_single_row(writer, self._parse_exits["MSR_WRITE MSR ICR"], name="MSR ICR")

            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY],
                                    name="msr entry overhead",
                                    count=self._parse_exits["MSR_WRITE MSR ICR"])
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_EXIT],
                                    name="msr exit overhead",
                                    count=self._parse_exits["MSR_WRITE MSR ICR"])

            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY],
                                    name="kick entry overhead",
                                    count=self._parse_batch)
            self._output_single_row(writer, self._parse_hw_exits[self._parse_hw_exits.HW_EXIT],
                                    name="kick exit overhead",
                                    count=self._parse_batch)

            self._output_compute_row(writer,
                                     lambda kick,
                                            writev, writev_cnt, d_write,
                                            read, read_cnt, d_read,
                                            sched, sched_cnt,
                                            netserver, ioctl, overhead_exit, overhead_entry:
                                     kick - (
                                             (writev + d_write) * writev_cnt +
                                             (read + d_read) * read_cnt +
                                             netserver +
                                             sched * sched_cnt +
                                             ioctl + overhead_exit + overhead_entry),
                                     (
                                         self._parse_exits["HLT"],

                                         self._parse_writev,
                                         round(len(self._parse_writev) / len(self._parse_batch)),
                                         self._parse_delta_writev,

                                         self._parse_read,
                                         round(len(self._parse_read) / len(self._parse_batch)),
                                         self._parse_delta_read,

                                         self._parse_sched,
                                         round(len(self._parse_sched) / len(self._parse_batch)),

                                         self._parse_netserver,
                                         self._parse_ioctl_interrupt,
                                         self._parse_hw_exits[self._parse_hw_exits.HW_EXIT],
                                         self._parse_hw_exits[self._parse_hw_exits.HW_ENRTY]
                                     ),
                                     name="qemu iothread",
                                     count=self._parse_batch,
                                     )
            writer.writerow([])
            self._output_compute_row(writer, lambda perf, perf_cnt, batch_cnt: (perf * perf_cnt / batch_cnt) ,
                                     (self._parse_netperf, len(self._parse_netperf), len(self._parse_batch)),
                                     count=self._parse_batch,
                                     name="Guest Netperf")
            writer.writerow([])
            self._output_single_row(writer, self._parse_guest_recv_checksum)
            self._output_single_row(writer, self._parse_guest_tcp_stack)

            writer.writerow(["guest other", 1, "", "=D6-SUM(D7:D34)"])
            writer.writerow([])
            self._output_single_row(writer, self._parse_guest_tcp)
            self._output_single_row(writer, self._parse_guest_tcp1)
            self._output_single_row(writer, self._parse_guest_tcp2)
            self._output_single_row(writer, self._parse_guest_tcp3)
            self._output_single_row(writer, self._parse_guest_tcp1_2)
            writer.writerow([])

            self._output_single_row(writer, self._parse_writev.writev_vlen, attr=self.attr.replace("time_", ""))
            self._output_single_row(writer, self._parse_writev.writev_size, attr=self.attr.replace("time_", ""))

