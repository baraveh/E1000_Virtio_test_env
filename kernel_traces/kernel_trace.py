import shlex

import logging
import shutil

from utils.machine import Machine
import os.path
import threading
import subprocess

from utils.shell_utils import run_command, run_command_output

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Trace:
    TRACE_DIR = r"/sys/kernel/debug/tracing/"
    TMP_FILE = '/tmp/trace_host_tmp'

    def __init__(self, target: Machine, target_file):
        self.target = target
        self.running = False
        self.target_file = target_file
        self._thread = threading.Thread(target=thread_read_trace, args=(self,))
        self._read_proc = None

    def _key2path(self, key):
        if not isinstance(key, str):
            key = os.path.join(*key)
        return key

    def write_value(self, key, value, append=False):
        command = "echo {value} {redirect} {key_path}".format(
            value=value,
            key_path=os.path.join(self.TRACE_DIR, self._key2path(key)),
            redirect=[">", ">>"][append]
        )
        self.target.remote_command(command)

    def read_value(self, key, **kargs):
        command = "cat {key_path}".format(
            key_path=os.path.join(self.TRACE_DIR, self._key2path(key))
        )
        return self.target.remote_command(command, **kargs)

    def setup(self):
        self.trace_off()
        self.disable_all_events()
        self.set_clock()
        self.set_tracer()
        self.kprobe_empty()
        self.uprobe_empty()

    def set_buffer_size(self, size):
        self.write_value("buffer_size_kb", size)

    def trace_on(self):
        self.write_value("tracing_on", 1)

    def trace_off(self):
        self.write_value("tracing_on", 0)

    def read_trace_once(self, to_file=True):
        data = self.read_value("trace", log_output=False)
        if to_file:
            with open(self.target_file, "w") as f:
                f.write(data)
        else:
            return data

    def trace_to_local_file(self):
        command = "cat {} > {}".format(
            os.path.join(self.TRACE_DIR, "trace_pipe"),
            self.TMP_FILE
        )
        self._read_proc = self.target.remote_command_ex(command)

    def trace_to_local_file_stop(self):
        self._read_proc.kill()
        self._read_proc.communicate()
        self._read_proc.wait()
        shutil.copyfile(self.TMP_FILE, self.target_file)

    def read_trace_background(self, target_file=None):
        if target_file:
            self.target_file = target_file

        self.running = True
        self._thread.start()

    def read_trace_stop(self, timeout=None):
        self.running = False
        self._thread.join(timeout)

    def set_tracer(self, tracer="nop"):
        self.write_value("current_tracer", tracer)

    def set_clock(self, clock="x86-tsc"):
        self.write_value("trace_clock", clock)

    def disable_all_events(self):
        self.write_value(("events", "enable"), 0)

    def _change_event_status(self, event_path, status):
        """
        :param event_path: without leading events/
        """
        self.write_value(("events", self._key2path(event_path), "enable"), status)

    def enable_event(self, event_path):
        self._change_event_status(event_path, 1)

    def disable_event(self, event_path):
        self._change_event_status(event_path, 0)

    def set_event_filter(self, event_path, fltr=""):
        self.write_value(("events", self._key2path(event_path), "filter"),
                         shlex.quote(fltr))

    def empty_trace(self):
        self.write_value("trace", "")

    def get_trace(self):
        return self.read_value("trace")

    def kprobe_empty(self):
        self.kprobe_disbale()
        self.write_value("kprobe_events", "")

    def kprobe_add(self, s):
        self.write_value("kprobe_events", s, append=True)

    def kprobe_enable(self):
        try:
            self.enable_event("kprobes")
        except subprocess.CalledProcessError:
            pass

    def kprobe_disbale(self):
        try:
            self.disable_event("kprobes")
        except subprocess.CalledProcessError:
            pass

    def uprobe_empty(self):
        self.uprobe_disbale()
        self.write_value("uprobe_events", "")

    def uprobe_add(self, s):
        self.write_value("uprobe_events", s, append=True)

    def uprobe_enable(self):
        try:
            self.enable_event("uprobes")
        except subprocess.CalledProcessError:
            pass

    def uprobe_disbale(self):
        try:
            self.disable_event("uprobes")
        except subprocess.CalledProcessError:
            pass

    def uprobe_add_event(self, event_type, event_name, event_exe, event_func, misc=''):
        command = "objdump -tT {exe} |grep .text|grep -w {func}|cut -f 1 -d \' \'".format(
            exe=event_exe,
            func=event_func
        )
        output=run_command_output(command, shell=True)
        event_addr = int(output, 16)
        event = "{event_type}:{event_name} {event_exe}:0x{event_addr:x} {misc}".format(
            event_type=event_type,
            event_name=event_name,
            event_exe=event_exe,
            event_addr=event_addr,
            misc=misc
        )
        self.uprobe_add(event)

    def trace_marker(self, msg):
        self.write_value("trace_marker", msg)


def thread_read_trace(trace):
    command = trace.target.remote_command_prepare(
        "cat {key_path}".format(
            key_path=os.path.join(trace.TRACE_DIR, "trace")
        )
    )
    logger.debug("Run command: %s\n%s", command, shlex.split(command))
    with subprocess.Popen(shlex.split(command),
                          stdout=subprocess.PIPE) as proc:
        with open(trace.target_file, "wb") as f:
            while trace.running:
                data = proc.stdout.read(1024*5)
                f.write(data)
            data = proc.stdout.read()
            f.write(data)
            proc.stdout.close()
        proc.kill()
