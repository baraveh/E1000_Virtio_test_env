from time import sleep

from utils.graphs import Graph
from utils.sensors import Sensor
from utils.vms import Qemu


class PacketNumberSensor(Sensor):
    def __init__(self, packet_count_graph: Graph, packet_size_graph: Graph):
        self.packet_count_graph = packet_count_graph
        self.packet_size_graph = packet_size_graph

    def set_column_names(self, titles):
        self.packet_count_graph.set_column_names(titles)
        self.packet_size_graph.set_column_names(titles)

    def set_x_tics(self, labels, values):
        self.packet_count_graph.set_x_tics(labels=labels, values=values)
        self.packet_size_graph.set_x_tics(labels=labels, values=values)

    def create_graph(self, retries):
        self.packet_count_graph.create_graph(retries)
        self.packet_size_graph.create_graph(retries)

    def test_before(self, vm: Qemu):
        vm.change_qemu_parameters({"count_packets_from_guest_on": 1})

    def test_after(self, vm: Qemu, title, x):
        vm.change_qemu_parameters({"count_packets_from_guest_on": 0})
        sleep(0.5)
        with open("/tmp/qemu_packets_count", "rb") as f:
            packet_count = int.from_bytes(f.read(8), byteorder='little', signed=False)
            total_size = int.from_bytes(f.read(8), byteorder='little', signed=False)

        self.packet_count_graph.add_data(title, x, packet_count)
        self.packet_size_graph.add_data(title, x, float(total_size)/(float(packet_count)+0.01))
