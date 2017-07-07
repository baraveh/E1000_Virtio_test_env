import logging

from utils.sensors import Sensor
from utils.vms import VM
from utils.graphs import Graph

logger = logging.getLogger(__name__)


class NetPerf(Sensor):
    def __init__(self, graph: Graph, runtime=10):
        super(NetPerf, self).__init__(graph)
        self.runtime = runtime
        self.test = ""

    def test_params(self, *args, **kargs):
        return ""

    def run_netperf(self, vm: VM, title="", x="", remote_ip=None, *args, **kargs):
        if not remote_ip:
            remote_ip = vm.ip_host

        logger.info("Netperf run: %d seconds, %s, params=%s", self.runtime, self.test, self.test_params(*args, **kargs))
        netperf_command = "netperf -H {ip} -l {runtime} -t {test_type} -v 0 {test_params}".format(
            ip=remote_ip,
            runtime=self.runtime,
            test_type=self.test,
            test_params=self.test_params(*args, **kargs)
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

    def test_params(self, msg_size):
        return " -- -m {}".format(msg_size)


class NetPerfTCPNoDelay(NetPerfTCP):
    def test_params(self, msg_size):
        return " -- -m {} -D L,R".format(msg_size)


class NetPerfLatency(NetPerf):
    def __init__(self, *args, **kargs):
        super(NetPerfLatency, self).__init__(*args, **kargs)
        self.test = "TCP_RR"

    def test_params(self, msg_size):
        return " -- -r {},64".format(msg_size)
