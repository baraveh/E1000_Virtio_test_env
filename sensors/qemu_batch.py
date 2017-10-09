from utils.sensors import Sensor, SensorBeforeAfter
from utils.vms import Qemu


class QemuBatchQmpSensor(SensorBeforeAfter):
    def _get_value(self, vm: Qemu):
        try:
            return vm.qmp.command("query-batch")
        except:
            return {'batchCount': 0, 'packetCount': 0, 'descriptorsCount':0}


class QemuBatchSizeSensor(QemuBatchQmpSensor):
    def _delta(self, value1, value2):
        batchCount = value2['batchCount'] - value1['batchCount']
        packetCount = value2['packetCount'] - value1['packetCount']

        if batchCount == 0:
            return 0
        return packetCount / batchCount


class QemuBatchDescriptorsSizeSensor(QemuBatchQmpSensor):
    def _delta(self, value1, value2):
        batchCount = value2['batchCount'] - value1['batchCount']
        descriptorsCount = value2['descriptorsCount'] - value1['descriptorsCount']

        if batchCount == 0:
            return 0
        return descriptorsCount / batchCount


class QemuBatchCountSensor(QemuBatchQmpSensor):
    def _delta(self, value1, value2):
        batchCount = value2['batchCount'] - value1['batchCount']

        return batchCount
