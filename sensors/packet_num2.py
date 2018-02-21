from utils.sensors import SensorBeforeAfter
from utils.vms import VM, Qemu


class PacketInfoSensor(SensorBeforeAfter):
    INFO_NIC = 0
    INFO_RX_BYTES = 1 # from qemu
    INFO_RX_PACKETS = 2
    INFO_TX_BYTES = 9 # to qemu
    INFO_TX_PACKETS = 10
    INFO_VALUES = (INFO_RX_BYTES, INFO_RX_PACKETS, INFO_TX_BYTES, INFO_TX_PACKETS)

    def __init__(self, *args, **kargs):
        super(PacketInfoSensor, self).__init__(*args, **kargs)
        self.interesting_value = None

    def _get_value(self, vm: Qemu):
        assert self.interesting_value is not None
        assert self.interesting_value in self.INFO_VALUES
        with open("/proc/net/dev") as f:
            for line in f:
                values = [val.strip(":") for val in line.split()]
                if values[self.INFO_NIC] == vm.tap_device:
                    return int(values[self.interesting_value])

    def _delta(self, value1, value2):
        return value2 - value1


class PacketTxBytesSensor(PacketInfoSensor):
    def __init__(self, *args, **kargs):
        super(PacketTxBytesSensor, self).__init__(*args, **kargs)
        self.interesting_value = self.INFO_TX_BYTES


class PacketTxPacketsSensor(PacketInfoSensor):
    def __init__(self, *args, **kargs):
        super(PacketTxPacketsSensor, self).__init__(*args, **kargs)
        self.interesting_value = self.INFO_TX_PACKETS


class PacketRxBytesSensor(PacketInfoSensor):
    def __init__(self, *args, **kargs):
        super(PacketRxBytesSensor, self).__init__(*args, **kargs)
        self.interesting_value = self.INFO_RX_BYTES


class PacketRxPacketsSensor(PacketInfoSensor):
    def __init__(self, *args, **kargs):
        super(PacketRxPacketsSensor, self).__init__(*args, **kargs)
        self.interesting_value = self.INFO_RX_PACKETS
