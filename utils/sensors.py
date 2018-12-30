from utils.graphs import Graph
from utils.vms import VM


class Sensor:
    def __init__(self, graph: Graph):
        """
        :param graph: graph to generate
        """
        self.graph = graph

    def test_before(self, vm: VM):
        error = NotImplementedError()
        raise error

    def test_after(self, vm: VM, title, x):
        raise NotImplementedError()

    def set_column_names(self, titles):
        self.graph.set_column_names(titles)

    def set_x_tics(self, labels, values):
        self.graph.set_x_tics(labels=labels, values=values)

    def create_graph(self, retries):
        self.graph.create_graph(retries)

    def load_old_data(self, vm_name):
        self.graph.load_old_results(vm_name)


class SensorBeforeAfter(Sensor):
    def __init__(self, *args, **kargs):
        super(SensorBeforeAfter, self).__init__(*args, **kargs)
        self._value_before = 0

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
        # return value2 - value1

    def test_before(self, vm: VM):
        self._value_before = self._get_value(vm)

    def test_after(self, vm: VM, title, x):
        value2 = self._get_value(vm)
        delta = self._delta(self._value_before, value2)
        self.graph.add_data(title, x, delta)


class DummySensor(Sensor):
    """
    Used to only ceate graph, without data logging
    """
    def test_after(self, vm: VM, title, x):
        pass

    def test_before(self, vm: VM):
        pass

    def load_old_data(self, vm_name):
        pass
