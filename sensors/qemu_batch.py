from utils.sensors import Sensor, SensorBeforeAfter
from utils.vms import Qemu


def get_from_dict(d, *keys):
    for k in keys:
        if k in d:
            return d[k]
    else:
        return 0


class QemuBatchQmpSensor(SensorBeforeAfter):
    def _get_value(self, vm: Qemu):
        try:
            return vm.qmp.command("query-batch")
        except:
            return {'batchCount': 0, 'packetCount': 0, 'descriptorsCount': 0,
                    'batch_count': 0, 'packet_count': 0, 'descriptors_count': 0}


class QemuBatchSizeSensor(QemuBatchQmpSensor):
    def _delta(self, value1: dict, value2: dict):
        batch_count = get_from_dict(value2, 'batchCount', 'batch_count') - \
                      get_from_dict(value1, 'batchCount', 'batch_count')

        packet_count = get_from_dict(value2, 'packetCount', 'packet_count') - \
                       get_from_dict(value1, 'packetCount', 'packet_count')

        if batch_count == 0:
            return 0
        return packet_count / batch_count


class QemuBatchDescriptorsSizeSensor(QemuBatchQmpSensor):
    def _delta(self, value1, value2):
        batch_count = get_from_dict(value2, 'batchCount', 'batch_count') - \
                      get_from_dict(value1, 'batchCount', 'batch_count')
        descriptors_count = get_from_dict(value2, 'descriptorsCount', 'descriptors_count') - \
                            get_from_dict(value1, 'descriptorsCount', 'descriptors_count')

        if batch_count == 0:
            return 0
        return descriptors_count / batch_count


class QemuBatchCountSensor(QemuBatchQmpSensor):
    def _delta(self, value1, value2):
        batch_count = get_from_dict(value2, 'batchCount', 'batch_count') - \
                      get_from_dict(value1, 'batchCount', 'batch_count')

        return batch_count
