from utils.sensors import Sensor
from utils.vms import VM
from utils.graphs import Graph


class NetPerf(Sensor):
    def __init__(self, graph: Graph):
        super(NetPerf, self).__init__(graph)
        self.runtime = 10
        self.test = ""

    def test_params(self, *args, **kargs):
        return ""

    def run_netperf(self, vm: VM, title, x, *args, **kargs):
        netperf_command = "netperf -H {ip} -l {runtime} -t {test_type} -v 0 {test_params}".format(
            ip=vm.ip_host,
            runtime=self.runtime,
            test_type=self.test,
            test_params=self.test_params(*args, **kargs)
        )
        output = vm.remote_command(netperf_command)
        # sample output:
        # MIGRATED TCP STREAM TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to 192.168.221.1 () port 0 AF_INET : demo
        # 2612.95
        value = float(output.split("\n")[1])
        self.graph.add_data(title, x, value)

    def test_after(self, vm: VM, title, x):
        pass

    def test_before(self, vm: VM):
        pass


class NetPerfTCP(NetPerf):
    def __init__(self, graph: Graph):
        super(NetPerfTCP, self).__init__(graph)
        self.test = "TCP_STREAM"

    def test_params(self, msg_size):
        return " -- -m {}".format(msg_size)
