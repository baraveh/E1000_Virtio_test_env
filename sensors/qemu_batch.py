from utils.sensors import Sensor, SensorBeforeAfter
from utils.vms import Qemu


class QemuBatchSizeSensor(SensorBeforeAfter):
    def _get_value(self, vm: Qemu):
        return vm.qmp.command("query-batch")

    def _delta(self, value1, value2):
        batchCount = value2['batchCount'] - value1['batchCount']
        packetCount = value2['packetCount'] - value1['packetCount']

        if batchCount == 0:
            return 0
        return packetCount / batchCount


class QemuBatchDescriptorsSizeSensor(SensorBeforeAfter):
    def _get_value(self, vm: Qemu):
        return vm.qmp.command("query-batch")

    def _delta(self, value1, value2):
        batchCount = value2['batchCount'] - value1['batchCount']
        descriptorsCount = value2['descriptorsCount'] - value1['descriptorsCount']

        if batchCount == 0:
            return 0
        return descriptorsCount / batchCount


class QemuBatchCountSensor(SensorBeforeAfter):
    def _get_value(self, vm: Qemu):
        return vm.qmp.command("query-batch")

    def _delta(self, value1, value2):
        batchCount = value2['batchCount'] - value1['batchCount']

        return batchCount
