import logging
import os.path
import struct
import collections
import csv
import argparse

from utils import read_cpu_speed

DIR = r"/tmp/traces"
TRACE_BEGIN_MSG = "NETPERF BEGIN"
TRACE_END_MSG = "NETPERF END"

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Event:
    EVENT_KVM_EXIT = "kvm_exit"
    EVENT_KVM_ENTRY = "kvm_entry"
    EVENT_KVM_MMIO = "kvm_mmio"
    EVENT_KVM_MSR = "kvm_msr"

    EVENT_SOURCE_HOST = "h"
    EVENT_SOURCE_GUEST = "g"

    REASONS_NAME = {
        "msr_write 80b": "MSR EOI",
        "msr_write 838": "MSR ICR",  # initial count register
        "msr_read 819"  : "MSR TMR",  # Trigger mode register bits 32:63
        "read 0008" : "E1000 STATUS",
        "write 3818": "E1000 TDT",
        "write 2818": "E1000 RDT",
        "write 0034": "E1000 KICK",
        "write 00d0": "E1000 IMS",
        "write 00d8": "E1000 IMC",
        "read 00c0" : "E1000 ICR",
        "write 00c4": "E1000 ITR",
    }

    def __init__(self, procname, cpuNum, flags, timestamp, event, info, source=""):
        self.procname = procname
        self.cpuNum = cpuNum
        self.flags = flags
        self.timestamp = timestamp
        self.event = event
        self.info = info
        self.source = source
        self.note = None  # can be used in the parser
        self.reason = ""  # parsed reason
        self.parse_reason()

    def parse_reason(self):
        if self.event == self.EVENT_KVM_EXIT:
            self.reason = self.info.split()[1]
        elif self.event == self.EVENT_KVM_MMIO:
            op = self.info.split()[1]
            addr = self.info.split()[5]
            self.reason = "{} {}".format(op, addr[-4:])
        elif self.event == self.EVENT_KVM_MSR:
            op = self.info.split()[0]
            addr = self.info.split()[1]
            self.reason = "{} {}".format(op, addr)
        self.translate_reason()

    def translate_reason(self):
        if self.reason in self.REASONS_NAME:
            self.reason = self.REASONS_NAME[self.reason]

    def __str__(self):
        return "{} {}: {}".format(self.timestamp, self.event, self.info)

    def __repr__(self):
        return "{proc:>23} {cpu} {source}{flags} {timestamp} {name}: {info}".format(
            proc=self.procname,
            cpu=self.cpuNum,
            source=self.source,
            flags=self.flags,
            timestamp=self.timestamp,
            name=self.event,
            info=self.info
        )

    @property
    def pid(self):
        return int(self.procname.split("-")[-1])


class TraceFile:
    def __init__(self, filename, source=""):
        self.filename = filename
        self.events = list()
        self.orig_events = list()
        self.source = source

    def parse(self):
        with open(self.filename) as f:
            EVENT_SPLIT_POINT = 23
            for line in f:
                if line.startswith("#") or line.startswith("CPU:"):
                    continue

                procname = line[:EVENT_SPLIT_POINT].strip()
                line_splitted = [procname] + line[EVENT_SPLIT_POINT:].split()

                procname = line_splitted[0].strip()
                cpu_num = line_splitted[1].strip("[]")
                flags = line_splitted[2]
                timestamp = int(line_splitted[3].strip(":"))
                event_name = line_splitted[4].strip(":")
                info = " ".join(line_splitted[5:])

                if "(" in event_name:
                    #  handle sys_* events
                    event_name, rest = line_splitted[4].split("(", maxsplit=1)
                    info = " ".join([rest, info])
                self.events.append(Event(procname, cpu_num, flags, timestamp, event_name, info, source=self.source))
        self.orig_events = self.events[:]


class Traces:
    def __init__(self, dir=DIR):
        self.guest_traces = TraceFile(os.path.join(dir, "trace_guest"),
                                      source=Event.EVENT_SOURCE_GUEST)
        self.host_traces = TraceFile(os.path.join(dir, "trace_host"),
                                     source=Event.EVENT_SOURCE_HOST)
        self.tsc_offset = None
        self.events = list()
        try:
            self.parse()
        except:
            logger.debug("Failed to parse traces")

    def parse(self):
        self.guest_traces.parse()
        self.host_traces.parse()
        self.parse_tsc()
        self.update_guest_tsc()
        self.merge()

    def parse_tsc(self):
        for event in self.host_traces.events:
            if event.event == 'kvm_write_tsc_offset':
                raw_delta = int(event.info.split("=")[-1].strip())
                self.tsc_offset = struct.unpack("q", struct.pack("Q", raw_delta))[0]
                print("Found sync event: {}".format(event))
                print("New Delta: {}".format(self.tsc_offset))

    def update_guest_tsc(self):
        assert self.tsc_offset is not None
        for event in self.guest_traces.events:
            event.timestamp -= self.tsc_offset

    def merge(self):
        self.events = self.guest_traces.events + self.host_traces.events
        self.events.sort(key=lambda e: e.timestamp)

    def get_test_events(self):
        start, end = [n for n, e in enumerate(self.events) if e.event == 'tracing_mark_write']
        start_timestamp = self.events[start].timestamp + read_cpu_speed() * 1e6 * 1.5  # 0.5 sec
        end_timestamp = self.events[end].timestamp - read_cpu_speed() * 1e6 * 0.5  # 1.5 sec
        events = [start + n for n, e in enumerate(self.events[start:end+1]) if start_timestamp < e.timestamp < end_timestamp]
        # print("start", start)
        start, end = events[0], events[-1]
        # print("new start", start)
        return self.events[start:end + 1]

    def write_to_file(self, filename, test_events_only=False):
        if os.path.isdir(filename):
            filename = os.path.join(filename, "merged_trace")
        if test_events_only:
            events = self.get_test_events()
        else:
            events = self.events
        with open(filename, "w") as f:
            for event in events:
                f.write("{!r}\n".format(event))


def virtio_kick_exits(events):
    times = list()
    fails = 0
    deltas = collections.namedtuple("deltas",
                                    ("guest2host", "host2user", "user2qemu", "qemu", "qemu2host", "host2guest"))
    events_order = ['notify_begin',
                    'kvm_exit',
                    'kvm_userspace_exit',
                    'virtio_queue_notify_vq',
                    'kvm_vcpu_ioctl',
                    'kvm_entry',
                    'notify_end']

    event_notify_begin = ((n, e) for n, e in enumerate(events) if e.event == 'notify_begin')
    for n, e in event_notify_begin:
        current_events = events[n:n + 7]
        if [e.event for e in current_events] != events_order:
            fails += 1
            continue

        current_deltas = list()
        for e1, e2 in zip(current_events[:-1], current_events[1:]):
            current_deltas.append(e2.timestamp - e1.timestamp)
        times.append(deltas(*current_deltas))
    return times, fails


def deltas2csv(csvname, deltas):
    with open(csvname, "w", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=deltas[0]._fields)
        writer.writeheader()
        writer.writerows(({n: v for n, v in zip(d._fields, d)} for d in deltas))


cpu_hz = None


def delta2time(delta):
    global cpu_hz
    if not cpu_hz:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("cpu MHz"):
                    cpu_hz = float(line.split(':')[1].strip())
    return delta / cpu_hz


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--dir")
    parser.add_argument("-o", "--output", default=None)
    args = parser.parse_args()

    if not args.dir:
        parser.print_help()
        return

    output = os.path.join(args.dir, "exits.csv")
    if args.output:
        output = args.output

    t = Traces(args.dir)
    deltas, fails = virtio_kick_exits(t.events)
    print("Found {} events, Failed to parse {} kick events".format(len(deltas), fails))
    deltas2csv(output, deltas)


if __name__ == "__main__":
    main()
