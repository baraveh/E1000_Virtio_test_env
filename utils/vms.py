import logging
import os
from utils.shell_utils import run_command_output, run_command_check, run_command_remote, run_command_async, run_command
from time import sleep
from tempfile import NamedTemporaryFile
import signal

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class VM:
    BOOTUP_WAIT = 35 #15
    POWEROFF_WAIT = 3
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

    def _run(self):
        raise NotImplementedError()

    def configure_guest(self):
        pass

    def shutdown(self):
        self.remote_command("poweroff")
        sleep(self.POWEROFF_WAIT)

    def run(self, configure_guest=True):
        logger.info("Running VM: %s", self)
        self._run()
        sleep(self.BOOTUP_WAIT)
        if configure_guest:
            self.configure_guest()

    def remote_command(self, command):
        return run_command_remote(self.ip_guest, self.USER, command)


class Qemu(VM):
    QEMU_EXE = ""

    QEMU_E1000_DEBUG_PARAMETERS_FILE = "/tmp/e1000_debug_parameters"

    QEMU_E1000 = "e1000"
    QEMU_VIRTIO = "virtio-net-pci"

    BOOTUP_WAIT = 20

    def __init__(self, disk_path, guest_ip, host_ip, cpu_to_pin="2"):
        super(Qemu, self).__init__(disk_path, guest_ip, host_ip)

        self.cpu_to_pin = cpu_to_pin
        # self.cpu_num = cpu_num
        self.mac_address = "52:54:00:a0:e5:1c"
        self.vnc_number = "10"

        self.ethernet_dev = self.QEMU_E1000  # can be "virtio-net-pci" or "e1000"
        self.vhost = False
        self.sidecore = False
        self.mem = "4096"

        self.io_thread_cpu = ""

        # auto config
        self.tap_device = ''
        self.pidfile = NamedTemporaryFile()

        self.qemu_config = dict()
        self.bridge = None
        self.exe = self.QEMU_EXE

        self.io_thread_nice = True

    def create_tun(self):
        """
        create tun device and assign it an IP
        """
        current_user = os.environ["USER"]

        output = run_command_output("sudo tunctl -u {user}".format(user=current_user))
        self.tap_device = output.split("'")[1]
        assert self.tap_device == 'tap0'

        run_command_check("sudo  ip link set {tap} up".format(tap=self.tap_device))
        if self.ip_host and not self.bridge:
            run_command_check("sudo ip a a {host_ip}/24 dev {tap}".format(host_ip=self.ip_host,
                                                                          tap=self.tap_device))
        if self.bridge:
            run_command_check("sudo brctl addif {br} {iff}".format(br=self.bridge, iff=self.tap_device))

    def delete_tun(self):
        if self.bridge:
            run_command_check("sudo brctl delif {br} {iff}".format(br=self.bridge, iff=self.tap_device))
        run_command_check("sudo tunctl -d {tap}".format(tap=self.tap_device))

    def load_kvm(self):
        run_command_check("sudo modprobe kvm-intel")

    def unload_kvm(self):
        sleep(1)
        run_command("sudo modprobe -r kvm-intel")

    def setup(self):
        self.load_kvm()
        self.create_tun()
        self._configure_host()

    def teardown(self):
        self.shutdown()
        self._reset_host_configuration()
        self.delete_tun()
        sleep(2)
        self.unload_kvm()

    def _run(self):
        assert self.QEMU_EXE
        if self.vhost:
            vhost_param = ",vhost=on"
        else:
            vhost_param = ""

        if self.sidecore:
            sidecore_param = "-enable-e1000-sidecore"
        else:
            sidecore_param = ""

        self.pidfile.close()
        self.pidfile = NamedTemporaryFile()

        qemu_command = "taskset -c {cpu} {qemu_exe} -enable-kvm {sidecore} -k en-us -m {mem} " \
                       "-drive file='{disk}',if=none,id=drive-virtio-disk0,format=qcow2 " \
                       "-device virtio-blk-pci,scsi=off,bus=pci.0,addr=0x5,drive=drive-virtio-disk0,id=virtio-disk0,bootindex=1 " \
                       "-netdev tap,ifname={tap},id=net0,script=no{vhost} " \
                       "-device {dev_type},netdev=net0,mac={mac} -pidfile {pidfile} " \
                       "-vnc :{vnc}".format( #-monitor tcp:1234,server,nowait,nodelay
            cpu=self.cpu_to_pin,
            qemu_exe=self.exe,
            sidecore=sidecore_param,
            disk=self.path,
            tap=self.tap_device,
            vhost=vhost_param,
            dev_type=self.ethernet_dev,
            mac=self.mac_address,
            pidfile=self.pidfile.name,
            vnc=self.vnc_number,
            mem=self.mem,
        )
        run_command_async(qemu_command)
        if self.qemu_config:
            sleep(0.5)
            self.change_qemu_parameters()

    def change_qemu_parameters(self, config=None):
        if config:
            self.qemu_config.update(config)
        if self.io_thread_cpu:
            command = "taskset -p -c {} {}".format(self.io_thread_cpu, self._get_pid())
            run_command_check(command)
        if self.io_thread_nice:
            run_command_check("renice -n 2 -p {}".format(self._get_pid()))

        with open(self.QEMU_E1000_DEBUG_PARAMETERS_FILE, "w") as f:
            for name, value in self.qemu_config.items():
                f.write("{} {}\n".format(name, value))
                logger.debug("set qemu option: %s=%s", name, value)
        self._signal_qemu()

    def _get_pid(self):
        with open(self.pidfile.name, "r") as f:
            pid = int(f.read().strip())
        return pid

    def _signal_qemu(self):
        pid = self._get_pid()
        os.kill(pid, signal.SIGUSR1)

    def configure_guest(self):
        pass

    def _configure_host(self):
        pass

    def _reset_host_configuration(self):
        pass


class QemuE1000Max(Qemu):
    def __init__(self, *args, **kargs):
        super(QemuE1000Max, self).__init__(*args, **kargs)
        self.qemu_config = {
            "no_tso_loop_on": 1,
            "no_tcp_csum_on": 1,
            "zero_copy_on": 1,
            "tdt_handle_on_iothread": 1,
            "interrupt_mitigation_multiplier": 10,

            "smart_interrupt_mitigation": 0,
            "smart_interrupt_mitigarion": 0,
            "latency_itr": 0,

            "tx_packets_per_batch": 0,

            "drop_packet_every": 8000,
        }
        self.ethernet_dev = self.QEMU_E1000
        self.addiotional_guest_command = None

    def _configure_host(self):
        run_command_check("echo 1 | sudo tee /proc/sys/debug/tun/no_tcp_checksum_on", shell=True)

    def _reset_host_configuration(self):
        run_command_check("echo 0 | sudo tee /proc/sys/debug/tun/no_tcp_checksum_on", shell=True)

    def configure_guest(self):
        self.remote_command("echo 1 | sudo tee /proc/sys/debug/kernel/srtt_patch_on")
        if self.addiotional_guest_command:
            self.remote_command(self.addiotional_guest_command)


class VMware(VM):
    BOOTUP_WAIT = 15

    def setup(self):
        run_command_check("sudo service vmware start")
        sleep(1)

    def _run(self):
        command = "vmrun -T ws start {} nogui".format(self.path)
        run_command_check(command)

    def teardown(self):
        self.shutdown()
        run_command_check("sudo service vmware stop")
        sleep(1)


virtualBox_count = 0
class VirtualBox(VM):
    BOOTUP_WAIT = 30
    POWEROFF_WAIT = 10

    def setup(self):
        global virtualBox_count
        if virtualBox_count == 0:
            run_command_check("sudo rcvboxdrv start")
            sleep(1)
            run_command_check("VBoxManage hostonlyif create")
            run_command_check("VBoxManage hostonlyif ipconfig vboxnet0 --ip 192.168.56.1")
            run_command_check(
                "VBoxManage dhcpserver modify --ifname vboxnet0 --ip 192.168.56.100 --netmask 255.255.255.0 --lowerip 192.168.56.101 --upperip 192.168.56.150 --enable")
        virtualBox_count += 1

    def teardown(self):
        try:
            self.shutdown()
        except:
            pass
        run_command("VBoxManage controlvm {} acpipowerbutton".format(self.path))
        global virtualBox_count
        virtualBox_count -= 1
        if virtualBox_count == 0:
            run_command("sudo rcvboxdrv stop")
            sleep(1)

    def _run(self):
        command = "VBoxManage startvm {} --type headless".format(self.path)
        run_command_check(command)
