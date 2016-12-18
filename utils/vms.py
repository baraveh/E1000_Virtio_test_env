import logging
import os
from utils.shell_utils import run_command_output, run_command_check, run_command_remote, run_command_async
from time import sleep
from tempfile import NamedTemporaryFile
import signal

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class VM:
    BOOTUP_WAIT = 10
    USER = "user"

    def __init__(self, path, guest_ip, host_ip):
        self.path = path
        self.ip_guest = guest_ip
        self.ip_host = host_ip

    def setup(self):
        logger.info("Setup VM: %s", self)
        raise NotImplementedError()

    def teardown(self):
        logger.info("Teardown VM: %s", self)
        raise NotImplementedError()

    def run(self):
        logger.info("Running VM: %s", self)
        raise NotImplementedError()

    def remote_command(self, command):
        return run_command_remote(self.ip_guest, self.USER, command)


class Qemu(VM):
    QEMU_EXE = ""
    QEMU_E1000 = "e1000"
    QEMU_VIRTIO = "virtio-net-pci"

    def __init__(self, disk_path, guest_ip, host_ip, cpu_num = "1", cpu_to_pin = "2"):
        super(Qemu, self).__init__(self, disk_path, guest_ip, host_ip)

        self.cpu_to_pin = cpu_to_pin
        # self.cpu_num = cpu_num
        self.mac_address = "52:54:00:a0:e5:1c"
        self.vnc_number = "10"

        self.ethernet_dev = "e1000" # can be "virtio-net-pci" or "e1000"
        self.vhost = False
        self.sidecore = False

        # auto config
        self.tap_device = ''
        self.pidfile = NamedTemporaryFile()

    def create_tun(self):
        """
        create tun device and assign it an IP
        """
        current_user = os.environ["USER"]

        output = run_command_output("sudo tunctl -u {user}".format(user=current_user))
        self.tap_device = output.split("'")[1]

        run_command_check("sudo  ip link set {tap} up".format(tap=self.tap_device))
        run_command_check("sudo ip a a {host_ip}/24 dev {tap}".format(host_ip=self.ip_host,
                                                                      tap=self.tap_device))

    def delete_tun(self):
        run_command_check("sudo tunctl -d {tap}".format(tap=self.tap_device))

    def load_kvm(self):
        run_command_check("sudo modprobe intel_kvm")

    def unload_kvm(self):
        run_command_check("sudo modprobe -r intel_kvm")

    def setup(self):
        self.load_kvm()
        self.create_tun()

    def teardown(self):
        self.delete_tun()
        self.unload_kvm()

    def run(self):
        if self.vhost:
            vhost_param = ",vhost=on"
        else:
            vhost_param = ""

        if self.sidecore:
            sidecore_param = "-enable-e1000-sidecore"
        else:
            sidecore_param = ""

        qemu_command = "taskset -c {cpu} {qemu_exe} -enable-kvm {sidecore} -k en-us -m 4096 "\
                       "-drive_file='{disk}',if=none,id=drive-virtio-disk0,format=qcow2 "\
                       "-device virtio-blk-pci,scsi=off,bus=pci.0,addr=0x5,drive=drive-virtio-disk0,id=virtio-disk0,bootindex=1 "\
                       "-netdev tap,ifname={tap},id=net0,script=no{vhost} "\
                       "-device {dev_type},netdev=net0,mac={mac} -pidfile {pidfile}"\
                       "-vnc :{vnc}".format(
                            cpu=self.cpu_to_pin,
                            qemu_exe=self.QEMU_EXE,
                            sidecore=sidecore_param,
                            disk=self.path,
                            tap=self.tap_device,
                            vhost=vhost_param,
                            dev_type=self.ethernet_dev,
                            pidfile=self.pidfile.name,
                            vnc=self.vnc_number
                       )
        run_command_async(qemu_command)
        sleep(self.BOOTUP_WAIT)

    def change_qemu_parameters(self, configs):
        # TODO: set parameters
        self.signal_qemu()

    def signal_qemu(self):
        self.pidfile.seek(0)
        pid = int(self.pidfile.read().strip())
        os.kill(pid, signal.SIGUSR1)


class VMware(VM):
    def setup(self):
        pass

    def run(self):
        pass

    def teardown(self):
        pass

