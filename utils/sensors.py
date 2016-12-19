from utils.graphs import Graph
from utils.vms import VM


class Sensor:
    def __init__(self, graph: Graph):
        """
        :param vm: VM to test on
        """
        self.graph = graph

    def test_before(self, vm: VM):
        raise NotImplementedError()

    def test_after(self, vm: VM, title, x):
        raise NotImplementedError()

    def set_column_names(self, titles):
        self.graph.set_column_names(titles)

    def set_x_tics(self, labels, values):
        self.graph.set_x_tics(labels=labels, values=values)

    def create_graph(self, retries):
        self.graph.create_graph(retries)


class SensorBeforeAfter(Sensor):
    def __init__(self, *args, **kargs):
        super(SensorBeforeAfter, self).__init__(self, *args, **kargs)
        self._value = 0

    def _get_value(self, vm: VM):
        """
        get the sensor value from VM
        :return: value
        """
        raise NotImplementedError()

    def _delta(self, value1, value2):
        """
        :param value1: the value before the test
        :param value2: the value after the test
        :return: value to log into graph
        """
        raise NotImplementedError()

    def test_before(self, vm: VM):
        self._value = self._get_value(vm)

    def test_after(self, vm: VM, title, x):
        value2 = self._get_value(vm)
        delta = self._delta(self._value, value2)
        self.graph.add_data(title, x, delta)
