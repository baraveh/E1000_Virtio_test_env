import copy
import csv
import math
import math
import os
from collections import defaultdict
from functools import lru_cache
from operator import itemgetter
from statistics import mean, median
from itertools import product

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt

from kernel_traces.trace_parser import Event, Traces

import numpy as np
from matplotlib.ticker import FuncFormatter


@lru_cache()
def read_cpu_speed():
    """
    return cpu speed in MHz
    :return:
    """
    with open("/proc/cpuinfo") as f:
        for l in f:
            if l.startswith("cpu MHz"):
                _, speed = l.split(":")
                return float(speed)


def time_stats(results):
    """
    :param list[int, Event, Event] results:
    :return:
    """
    if results:
        min_val = min(results, key=itemgetter(0))[0]
        max_val = max(results, key=itemgetter(0))[0]
        avg_val = mean((a[0] for a in results))
        median_val = median((a[0] for a in results))
    else:
        min_val, max_val, avg_val, median_val = 0, 0, 0, 0
    # print("min {}".format(min_val))
    # print("max {}".format(max_val))
    # print("avg {}".format(avg_val))
    # print("median {}".format(median_val))
    return float(min_val), float(max_val), float(avg_val), float(median_val)


def cycles2usec(stats):
    cpu_speed = read_cpu_speed()
    return tuple((val / cpu_speed) if isinstance(val, float) or isinstance(val, int) else (val[0] / cpu_speed)
                 for val in stats)


def latency_send_recv(events):
    """

    :param list[Event] events:
    :return list[int, Event, Event]:
    """
    results = list()
    last_send = None  # type: Event
    for e in events:
        if e.event == "sys_sendto" and "netperf" in e.procname:
            last_send = e
        elif e.event == "sys_recvfrom" and "netperf" in e.procname \
                and last_send:
            results.append(
                (e.timestamp - last_send.timestamp, last_send, e)
            )
            last_send = None
    return results


def throughput_batch_time_kick(events):
    """

    :param list[Event] events:
    :return list[int, Event, Event]:
    """
    results = list()
    last_kick = None  # type: Event
    for e in events:
        # if e.event == e.EVENT_KVM_MMIO and "KICK" in e.reason:
        if e.event == e.EVENT_KVM_EXIT and (
                "HLT" in e.reason or (e.note and "KICK" in e.note.reason)
        ):
            if last_kick:
                results.append(
                    (e.timestamp - last_kick.timestamp, last_kick, e)
                )
            last_kick = e
            # print(e)

    # print(results)
    return results


def exit_time(events):
    """
    :param list[Event] events:
    :return dict[list[int, Event, Event]]:
    """
    results = defaultdict(list)
    last_exit = None  # type: Event
    for e in events:
        if e.event == Event.EVENT_KVM_EXIT:
            last_exit = e
        elif e.event == Event.EVENT_KVM_MMIO and last_exit:
            last_exit.note = e
        elif e.event == Event.EVENT_KVM_MSR and last_exit:
            last_exit.note = e
        elif e.event == Event.EVENT_KVM_ENTRY and last_exit:
            reason = last_exit.reason
            if last_exit.note:
                reason += " " + last_exit.note.reason
            last_exit.reason = reason
            results[reason].append(
                (e.timestamp - last_exit.timestamp, last_exit, e)
            )
            last_exit = None
    return results


def create_histogram(results, output_file):
    if results:
        with open(output_file, "w") as f:
            data = [round(math.log(time, 2)) for time, _, _ in results]
            for i in range(max(data)):
                f.write("{} {}\n".format(i, data.count(i)))


def draw_histogram(results, output_file, title):
    data = results
    # data = [time for time, _, _ in results]
    # plt.hist(data, bins=100, log=False)
    # plt.xlabel("Cycles")
    # plt.ylabel("Count")
    # plt.grid(True)
    # plt.savefig(output_file)
    fig, ax = plt.subplots()
    counts, bins, patches = ax.hist(data, facecolor='yellow', edgecolor='gray')

    # Set the ticks to be at the edges of the bins.
    ax.set_xticks(bins)
    # ax.tick_params(axis='x', pad=30)
    # Set the xaxis's tick labels to be formatted with 1 decimal place...
    # ax.xaxis.set_major_formatter(FormatStrFormatter('%0.0f'))
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda x, pos: "%0.2f" % x if x < 100 else "%0.0f" % x
    ))
    for label in ax.xaxis.get_majorticklabels():
        label.set_rotation(30)

    # Change the colors of bars at the edges...
    # twentyfifth, seventyfifth = np.percentile(data, [25, 75])
    # for patch, rightside, leftside in zip(patches, bins[1:], bins[:-1]):
    #     if rightside < twentyfifth:
    #         patch.set_facecolor('green')
    #     elif leftside > seventyfifth:
    #         patch.set_facecolor('red')

    # Label the raw counts and the percentages below the x-axis...
    bin_centers = 0.5 * np.diff(bins) + bins[:-1]
    for count, x in zip(counts, bin_centers):
        # Label the raw counts
        # ax.annotate(str(count), xy=(x, 0), xycoords=('data', 'axes fraction'),
        #             xytext=(0, -18), textcoords='offset points', va='top', ha='center')

        # Label the percentages
        percent = '%0.1f%%' % (100 * float(count) / counts.sum())
        ax.annotate(percent, xy=(x, 0), xycoords=('data', 'axes fraction'),
                    xytext=(0, -32), textcoords='offset points', va='top', ha='center')

    # Give ourselves some more room at the bottom of the plot
    plt.subplots_adjust(bottom=0.15)
    plt.title(title)
    plt.savefig(output_file)
    plt.close()


def exits_stats(traces, output_dir=None, title=""):
    exit_latency = exit_time(traces.get_test_events())
    send_recv = latency_send_recv(traces.get_test_events())
    try:
        throughput_kick = throughput_batch_time_kick(traces.get_test_events())
    except:
        throughput_kick = list(send_recv)
    send_recv_stats = time_stats(send_recv)
    kick_stats = time_stats(throughput_kick)

    sorted_keys = list(exit_latency.keys())
    sorted_keys.sort(key=lambda key: len(exit_latency[key]), reverse=True)

    if output_dir is None:
        f = sys.stdout
    else:
        f = open(os.path.join(output_dir, "exit_stats"), "w")
    print(
        "{:<31}: {:<6} cycles {:>11} {:>11} {:>11} {:>11} usec: {:>7} {:>7} {:>7} {:>7}".format(
            "Event Name", "Count", "min", "max", "avg", "mean", "min", "max", "avg", "mean"
        ), file=f)

    print(
        "{:<31}: {:<6} cycles {:>11.2f} {:>11.2f} {:>11.2f} {:>11.2f} usec: {:>7.2f} {:>7.2f} {:>7.2f} {:>7.2f}".format(
            "Transactions", len(send_recv), *(send_recv_stats + cycles2usec(send_recv_stats))
        ), file=f)
    print(
        "{:<31}: {:<6} cycles {:>11.2f} {:>11.2f} {:>11.2f} {:>11.2f} usec: {:>7.2f} {:>7.2f} {:>7.2f} {:>7.2f}".format(
            "kick_batch", len(throughput_kick), *(kick_stats + cycles2usec(kick_stats))
        ), file=f)

    if output_dir:
        create_histogram(send_recv, os.path.join(output_dir, "0_hist_transaction.txt"))
        draw_histogram(cycles2usec(send_recv), os.path.join(output_dir, "0_hist_transaction.png"), "{} - transactions".format(title))
        create_histogram(throughput_kick, os.path.join(output_dir, "1_hist_kick2kick.txt"))
        draw_histogram(cycles2usec(throughput_kick), os.path.join(output_dir, "1_hist_kick2kick.png"),
                       "{} - kick 2 kick".format(title))

    i = 2
    for k in sorted_keys:
        stats_cycles = time_stats(exit_latency[k])
        stats_time = cycles2usec(stats_cycles)
        count = len(exit_latency[k])
        print(
            "{:<31}: {:<6} cycles {:>11.2f} {:>11.2f} {:>11.2f} {:>11.2f} usec: {:>7.2f} {:>7.2f} {:>7.2f} {:>7.2f}".format(
                k, count, *(stats_cycles + stats_time)
            ), file=f)
        # if output_dir:
        #     create_histogram(exit_latency[k], os.path.join(output_dir, "{}_hist_{}.txt".format(i, k)))
        #     # draw_histogram(cycles2usec(exit_latency[k]),
        #     #                os.path.join(output_dir, "{}_hist_{}.png".format(i, k)),
        #     #                "{} - {}".format(title, k))
        i += 1

    f.close()


def exit_stats_main(folder):
    t = Traces(folder)
    exits_stats(t)


class TestTimes:
    MODE_INIT = "init"
    MODE_VM = "vm"
    MODE_KERNEL = "kernel"
    MODE_USER = "user"

    MODE_VCPU = "vcpu"
    MODE_IOTHREAD = "iothread"
    MODE_OTHER = "other_userspace"
    # MODE_USER = (MODE_VCPU, MODE_IOTHREAD, MODE_OTHER)
    # MODE_ALL = (MODE_VM, MODE_KERNEL, MODE_VCPU, MODE_IOTHREAD, MODE_OTHER)
    MODE_ALL = (MODE_VM, MODE_KERNEL, MODE_USER)

    def __init__(self, title):
        self._title = title

        self.results = list()

        self.mode = defaultdict(lambda: self.MODE_INIT)
        self.current_times = defaultdict(lambda: defaultdict(int))
        self.last_change = defaultdict(int)
        self.pid_vcpu = 0
        self.pid_iothread = 0

        self.count_syscalls = list()
        self.current_syscalls = 0

        self.count_switch = list()
        self.current_switch = 0

        self.current_exits = defaultdict(int)
        self.exits_results = list()
        self.last_exit = None

    def csv_cpu_times(self, filename):
        with open(filename, "w") as f:
            header = [p + k for p, k in product(("vcpu_", "iothread_", "other_"), self.MODE_ALL)]
            # print(header)
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            for res in self.results:
                line = defaultdict(int)
                line.update({"vcpu_" + k: v for k, v in res[self.pid_vcpu].items() if k in self.MODE_ALL})
                line.update({"iothread_" + k: v for k, v in res[self.pid_iothread].items() if k in self.MODE_ALL})
                for pid in res:
                    if pid not in (self.pid_iothread, self.pid_vcpu):
                        for k in res[pid]:
                            if "init" == k:
                                continue
                            line["other_" + k] += res[pid][k]

                # print(line)
                writer.writerow(line)

    def graph_cpu_times(self, filename):
        convert_result = defaultdict(list)
        for result in self.results[30:-30]:
            others = defaultdict(int)
            for pid in result:
                if pid not in (self.pid_iothread, self.pid_vcpu):
                    for k in result[pid]:
                        others[k] += result[pid][k]

            convert_result["vcpu_vm"].append(result[self.pid_vcpu][self.MODE_VM])
            convert_result["vcpu_kernel"].append(result[self.pid_vcpu][self.MODE_KERNEL])
            convert_result["vcpu_user"].append(result[self.pid_vcpu][self.MODE_USER])

            convert_result["iothread_vm"].append(result[self.pid_iothread][self.MODE_VM])
            convert_result["iothread_kernel"].append(result[self.pid_iothread][self.MODE_KERNEL])
            convert_result["iothread_user"].append(result[self.pid_iothread][self.MODE_USER])

            convert_result["others_vm"].append(others[self.MODE_VM])
            convert_result["others_kernel"].append(others[self.MODE_KERNEL])
            convert_result["others_user"].append(others[self.MODE_USER])

        fig, ax = plt.subplots()

        x = list(range(len(convert_result["vcpu_vm"])))
        m = [
            np.asarray(convert_result["vcpu_vm"]),
            np.asarray(convert_result["vcpu_kernel"]),
            np.asarray(convert_result["vcpu_user"]),
            np.asarray(convert_result["iothread_vm"]),
            np.asarray(convert_result["iothread_kernel"]),
            np.asarray(convert_result["iothread_user"]),
            np.asarray(convert_result["others_vm"]),
            np.asarray(convert_result["others_kernel"]),
            np.asarray(convert_result["others_user"]),
        ]

        number_of_plots = len(m)
        print("colors num ", len(m))
        ax.set_prop_cycle("color", reversed(plt.cm.Spectral(np.linspace(0, 1, number_of_plots))))

        ax.stackplot(x,
                     m,
                     labels=["vcpu_vm", "vcpu_kernel", "vcpu_user",
                             "iothread_vm", "iothread_kernel", "iothread_user",
                             "others_vm", "others_kernel", "others_user",
                             ],
                     linewidth=0,
                     )
        lgd = ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=2, mode="expand", borderaxespad=0.)
        ax.set_ylim(0, 700000)
        plt.title(self._title)
        plt.savefig(filename, bbox_extra_artists=(lgd,), bbox_inches='tight')
        plt.close()

    def csv_kernel_events(self, filename):
        with open(filename, "w") as f:
            header = ["Context_Switches", "syscalls"]
            # print(header)
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            for switch, syscalls in zip(self.count_switch, self.count_syscalls):
                line = defaultdict(int)
                line["Context_Switches"] = switch
                line["syscalls"] = syscalls
                writer.writerow(line)

    def graph_kernel_events(self, filename):
        assert len(self.count_switch) == len(self.count_syscalls)
        count = len(self.count_syscalls)

        fig, ax = plt.subplots()

        x = np.asarray(range(count))
        ax.plot(x, self.count_switch, label="Context Switches")
        ax.plot(x, self.count_syscalls, label="Syscalls")
        # ax.stackplot(x,
        #              self.count_switch,
        #              self.count_syscalls,
        #              labels=("Context switch", "Syscalls"),
        #              linewidth=0,
        #              )

        lgd = ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=2, mode="expand", borderaxespad=0.)
        ax.set_ylim(0, 30)
        plt.title(self._title)
        plt.savefig(filename, bbox_extra_artists=(lgd,), bbox_inches='tight')
        plt.close()

    def graph_exit_times(self, filename):
        # get all exits types, and count
        exit_results = self.exits_results[30:-30]

        exit_types = defaultdict(int)
        for exits in self.exits_results:
            for exit_type in exits:
                exit_types[exit_type] += 1

        ordered_keys = list(sorted(( t for t in exit_types if exit_types[t] > 1000),
                                   key=lambda t: exit_types[t],
                                   reverse=True))
        ordered_keys = ordered_keys[:14]
        ordered_keys = list(sorted(ordered_keys))
        values = defaultdict(lambda: np.zeros(len(exit_results)))
        for i, d in enumerate(exit_results):
            for k in d:
                values[k][i] += d[k]

        fig, ax = plt.subplots()

        x = np.asarray(range(len(exit_results)))
        m = [values[k] for k in ordered_keys]

        number_of_plots = len(ordered_keys)
        ax.set_prop_cycle("color", reversed(plt.cm.Paired(np.linspace(0, 1, number_of_plots))))

        try:
            ax.stackplot(x,
                         m,
                         labels=ordered_keys,
                         linewidth=0,
                         )
            lgd = ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=2, mode="expand", borderaxespad=0.)
            ax.set_ylim(0, 600000)
            plt.title(self._title)
            plt.savefig(filename, bbox_extra_artists=(lgd,), bbox_inches='tight')
        except:
            print("Failed to draw exit times")
        plt.close()

    def update_time(self, event):
        self.current_times[event.pid][self.mode[event.pid]] += event.timestamp - self.last_change[event.pid]
        self.last_change[event.pid] = event.timestamp

    def update_vcpu_pid(self, event):
        if not self.pid_vcpu:
            self.pid_vcpu = event.pid
        else:
            assert self.pid_vcpu == event.pid

    def update_iothread_pid(self, event):
        # if not self.pid_iothread:
            self.pid_iothread = event.pid
        # else:
        #     assert self.pid_iothread == event.pid

    def start_transaction(self, event):
        # assert self.mode[event.pid] in (self.MODE_INIT, self.MODE_VM)

        if self.mode[event.pid] != self.MODE_INIT:
            self.update_time(event)

        self.results.append(copy.deepcopy(self.current_times))
        self.current_times.clear()

        self.count_switch.append(self.current_switch)
        self.current_switch = 0

        self.count_syscalls.append(self.current_syscalls)
        self.current_syscalls = 0

        self.exits_results.append(copy.deepcopy(self.current_exits))
        self.current_exits.clear()

    def event_exit(self, event):
        assert self.mode[event.pid] in (self.MODE_INIT, self.MODE_VM)
        self.update_time(event)
        self.mode[event.pid] = self.MODE_KERNEL
        self.update_vcpu_pid(event)

        self.last_exit = event

    def event_enter(self, event):
        assert self.mode[event.pid] in (self.MODE_INIT, self.MODE_KERNEL,)
        self.update_time(event)
        self.mode[event.pid] = self.MODE_VM
        self.update_vcpu_pid(event)

        if self.last_exit:
            delta_time = event.timestamp - self.last_exit.timestamp
            self.current_exits[self.last_exit.reason] += delta_time

    def event_syscall_enter(self, event):
        assert self.mode[event.pid] in (self.MODE_INIT, self.MODE_USER)
        if event.event == "sys_ppoll":
            self.update_iothread_pid(event)

        # assert self.mode in self.MODE_USER
        self.update_time(event)
        self.mode[event.pid] = self.MODE_KERNEL

        self.current_syscalls += 1

    def event_syscall_exit(self, event):
        assert self.mode[event.pid] in (self.MODE_INIT, self.MODE_KERNEL)
        self.update_time(event)
        self.mode[event.pid] = self.MODE_USER
        # self.update_user(event)

    def event_sched_switch(self, event):
        for param in event.info.split():
            if "next_pid" in param:
                next_pid = int(param.split("=")[1])
            elif "prev_pid" in param:
                prev_pid = int(param.split("=")[1])

        # update previous proc
        self.current_times[prev_pid][self.mode[prev_pid]] += event.timestamp - self.last_change[prev_pid]
        self.last_change[next_pid] = event.timestamp

        # count syscalls
        self.current_switch += 1


def latency_split_to_time_portions(traces, output_dir, title):
    """
    :param str title:
    :param Traces traces:
    :param str output_dir:
    :return:
    """
    time_spliter = TestTimes(title)
    for e in traces.get_test_events():
        # print(e)
        if e.source == e.EVENT_SOURCE_GUEST:
            if e.event == "sys_sendto" and "netperf" in e.procname:
                time_spliter.start_transaction(e)
            elif e.event == "sys_recvfrom" and "netperf" in e.procname:
                pass
        elif e.source == e.EVENT_SOURCE_HOST:
            if e.cpuNum != "002":
                continue

            if e.event == e.EVENT_KVM_EXIT:
                time_spliter.event_exit(e)
            elif e.event == e.EVENT_KVM_ENTRY:
                time_spliter.event_enter(e)
            elif e.event.startswith("sys"):
                if "->" in e.info:
                    # retrun from syscall
                    time_spliter.event_syscall_exit(e)
                else:
                    # call syscall
                    time_spliter.event_syscall_enter(e)
            elif e.event == "sched_switch":
                time_spliter.event_sched_switch(e)
    time_spliter.csv_cpu_times(os.path.join(output_dir, "times.csv"))
    time_spliter.graph_cpu_times(os.path.join(output_dir, "times.png"))
    time_spliter.graph_exit_times(os.path.join(output_dir, "exits.png"))
    time_spliter.graph_kernel_events(os.path.join(output_dir, "kernel_events.png"))
    time_spliter.csv_kernel_events(os.path.join(output_dir, "kernel_events.csv"))


def throughput_split_to_time_portions(traces, output_dir, title):
    """
    :param str title:
    :param Traces traces:
    :param str output_dir:
    :return:
    """
    time_spliter = TestTimes(title)
    for e in traces.get_test_events():
        # print(e)
        if e.source == e.EVENT_SOURCE_GUEST:
            pass

        elif e.source == e.EVENT_SOURCE_HOST:
            if e.cpuNum != "002":
                continue
            if e.event == e.EVENT_KVM_EXIT:
                if "HLT" in e.reason or (e.note and "KICK" in e.note.reason):
                    time_spliter.start_transaction(e)
                time_spliter.event_exit(e)
            elif e.event == e.EVENT_KVM_ENTRY:
                time_spliter.event_enter(e)
            elif e.event.startswith("sys"):
                if "->" in e.info:
                    # retrun from syscall
                    time_spliter.event_syscall_exit(e)
                else:
                    # call syscall
                    time_spliter.event_syscall_enter(e)
            elif e.event == "sched_switch":
                time_spliter.event_sched_switch(e)
    time_spliter.csv_cpu_times(os.path.join(output_dir, "times.csv"))
    time_spliter.graph_cpu_times(os.path.join(output_dir, "times.png"))
    time_spliter.graph_exit_times(os.path.join(output_dir, "exits.png"))
    time_spliter.graph_kernel_events(os.path.join(output_dir, "kernel_events.png"))
    time_spliter.csv_kernel_events(os.path.join(output_dir, "kernel_events.csv"))

if __name__ == "__main__":
    import sys

    exit_stats_main(sys.argv[1])
