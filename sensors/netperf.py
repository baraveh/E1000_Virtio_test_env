import logging

from utils.sensors import Sensor
from utils.shell_utils import run_command_check, run_command
from utils.vms import VM
from utils.graphs import Graph

logger = logging.getLogger(__name__)

NETPERF_CORE = 3


def netserver_start(core = NETPERF_CORE):
    run_command("sudo taskset -c {} netserver".format(core))


def netserver_stop():
    run_command("sudo killall netserver")


class NetPerf(Sensor):
    def __init__(self, graph: Graph, runtime=10):
        super(NetPerf, self).__init__(graph)
        self.runtime = runtime
        self.test = ""

    def test_params(self, *args, vm_params="", **kargs):
        return ""

    def run_netperf(self, vm: VM, title="", x="", remote_ip=None, *args, **kargs):
        if not remote_ip:
            remote_ip = vm.ip_host

        logger.info("Netperf run: %d seconds, %s, params=%s", self.runtime, self.test, self.test_params(*args, vm_param=vm.netperf_test_params, **kargs))
        netperf_command = "netperf -H {ip} -l {runtime} -t {test_type} -v 0 {test_params}".format(
            ip=remote_ip,
            runtime=self.runtime,
            test_type=self.test,
            test_params=self.test_params(*args, vm_param=vm.netperf_test_params, **kargs)
        )
        output = vm.remote_command(netperf_command)
        # sample output:
        # MIGRATED TCP STREAM TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to 192.168.221.1 () port 0 AF_INET : demo
        # 2612.95
        value = float(output.split("\n")[1])
        if self.graph:
            self.graph.add_data(title, x, value)
        else:
            return value

    def test_after(self, vm: VM, title, x):
        pass

    def test_before(self, vm: VM):
        pass


class NetPerfTCP(NetPerf):
    def __init__(self, *args, **kargs):
        super(NetPerfTCP, self).__init__(*args, **kargs)
        self.test = "TCP_STREAM"

    def test_params(self, msg_size, vm_param=""):
        return " -- -m {} {}".format(msg_size, vm_param)


class NetPerfUDP(NetPerf):
    def __init__(self, *args, **kargs):
        super(NetPerfUDP, self).__init__(*args, **kargs)
        self.test = "UDP_STREAM"

    def test_params(self, msg_size, vm_param=""):
        return " -- -m {}".format(msg_size)


class NetPerfTCPNoDelay(NetPerfTCP):
    def test_params(self, msg_size, vm_param=""):
        return " -- -m {} -D L,R".format(msg_size)


class NetPerfLatency(NetPerf):
    def __init__(self, *args, **kargs):
        super(NetPerfLatency, self).__init__(*args, **kargs)
        self.test = "TCP_RR"

    def test_params(self, msg_size, vm_param=""):
        return " -- -r {},64".format(msg_size)


class NetPerfTcpTSO(NetPerfTCP):
    def run_netperf(self, vm: VM, title="", x="", remote_ip=None, *args, **kargs):
        try:
            vm.remote_command(
                "echo {} > /proc/sys/net/ipv4/tcp_tso_size".format(kargs["msg_size"])
            )
        except:
            pass
        return super().run_netperf(vm, *args, title=title, x=x, remote_ip=remote_ip, **kargs)