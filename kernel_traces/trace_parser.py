import os.path
import struct
import collections
import csv
import argparse

DIR = r"/tmp/traces"
TRACE_BEGIN_MSG="NETPERF BEGIN"
TRACE_END_MSG="NETPERF END"


class Event:
    def __init__(self, procname, cpuNum, flags, timestamp, event, info):
        self.procname = procname
        self.cpuNum = cpuNum
        self.flags = flags
        self.timestamp = timestamp
        self.event = event
        self.info = info

    def __repr__(self):
        return "{} {}: {}".format(self.timestamp, self.event, self.info)


class TraceFile:
    def __init__(self, filename):
        self.filename = filename
        self.events = list()
        self.orig_events = list()

    def parse(self):
        with open(self.filename) as f:
            for line in f:
                if line.startswith("#") or line.startswith("CPU:"):
                    continue
                line_splitted = line.split()

                procname = line_splitted[0]
                cpu_num = line_splitted[1]
                flags = line_splitted[2]
                timestamp = int(line_splitted[3].strip(":"))
                event_name = line_splitted[4].strip(":")
                info = " ".join(line_splitted[5:])
                self.events.append(Event(procname, cpu_num, flags, timestamp, event_name, info))
        self.orig_events = self.events[:]


class Traces:
    def __init__(self, dir=DIR):
        self.guest_traces = TraceFile(os.path.join(dir, "trace_guest"))
        self.host_traces = TraceFile(os.path.join(dir, "trace_host"))
        self.tsc_offset = None
        self.events = list()

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
        return self.events[start:end+1]


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
