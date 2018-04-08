import logging
import os
from subprocess import CalledProcessError

from qemu.qmp import QEMUMonitorProtocol
from utils.machine import Machine
from utils.shell_utils import run_command_output, run_command_check, run_command_remote, run_command_async, run_command
from time import sleep
from tempfile import NamedTemporaryFile
import signal

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class VM(Machine):
    BOOTUP_WAIT = 35 #15
    POWEROFF_WAIT = 3
    USER = "user"

    def __init__(self, path, guest_ip, host_ip):
        super(VM, self).__init__(guest_ip, self.USER)
        self.path = path
        self.ip_guest = guest_ip
        self.ip_host = host_ip
        self.name = None
        self.bootwait = self.BOOTUP_WAIT
        self.netperf_test_params = ""

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
        sleep(self.bootwait)
        if configure_guest:
            self.configure_guest()


class Qemu(VM):
    QEMU_EXE = ""

    QEMU_E1000_DEBUG_PARAMETERS_FILE = "/tmp/e1000_debug_parameters"

    QEMU_E1000 = "e1000"
    QEMU_VIRTIO = "virtio-net-pci"

    BOOTUP_WAIT = 10

    def __init__(self, disk_path, guest_ip, host_ip, cpu_to_pin="2"):
        super(Qemu, self).__init__(disk_path, guest_ip, host_ip)
        self._pid = None

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
        self.pidfile = None

        self.qemu_config = dict()
        self.bridge = None
        self.exe = self.QEMU_EXE

        self.is_io_thread_nice = False
        self.io_nice = 1  # nice value to set

        self.root = Machine(self._remote_ip, "root")

        # self.kernel = r"/home/bdaviv/repos/e1000-improv/linux-3.13.0/arch/x86/boot/bzImage"
        # self.kernel = r"/homes/bdaviv/repos/msc-ng/linux-4.13.9/arch/x86/boot/bzImage"
        self.kernel = r"/homes/bdaviv/repos/msc-ng/linux-4.14.4/arch/x86/boot/bzImage"
        # self.initrd = r"/homes/bdaviv/repos/e1000-improv/vms/initrd.img-3.13.11-ckt22+"
        # self.initrd = r"/homes/bdaviv/repos/msc-ng/vm-files/kernels/initrd.img-4.13.9-ng+"
        self.initrd = r"/homes/bdaviv/repos/msc-ng/vm-files/kernels/initrd.img-4.14.4-ng+"
        self.kernel_cmdline = r"BOOT_IMAGE=/vmlinuz-3.13.11-ckt22+ root=/dev/mapper/tapuz3--L1--vg-root ro"
        self.kernel_cmdline_additional = ""

        self.nic_additionals = ""
        self.qemu_additionals = ""

        self.qmp = None

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
        try:
            self.shutdown()
            self.qmp.close()
        except:
            pass
        self.qmp = QEMUMonitorProtocol(('127.0.0.1', 1235))
        self._pid = None
        self._reset_host_configuration()
        self.delete_tun()
        sleep(2)
        self.unload_kvm()

    def _get_temp_nic_additional(self):
        return ""

    def _run(self):
        assert self.exe

        self.qmp = QEMUMonitorProtocol(('127.0.0.1', 1235))
        self.pidfile = NamedTemporaryFile()

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

        kernel_spicific_boot = ""
        if self.kernel:
            kernel_spicific_boot = "-kernel {kernel} -initrd {initrd} -append '{cmdline} {cmdline_more}'".format(
                kernel=self.kernel,
                initrd=self.initrd,
                cmdline=self.kernel_cmdline,
                cmdline_more=self.kernel_cmdline_additional
            )

        qemu_command = "taskset -c {cpu} {qemu_exe} -enable-kvm {sidecore} -k en-us -m {mem} " \
                       "{kernel_additions} " \
                       "{qemu_additionals} " \
                       "-drive file='{disk}',if=none,id=drive-virtio-disk0,format=qcow2 " \
                       "-device virtio-blk-pci,scsi=off,bus=pci.0,addr=0x5,drive=drive-virtio-disk0,id=virtio-disk0,bootindex=1 " \
                       "-netdev tap,ifname={tap},id=net0,script=no{vhost} " \
                       "-object iothread,id=iothread0 " \
                       "-device {dev_type},netdev=net0,mac={mac}{nic_additionals} " \
                       "-pidfile {pidfile} " \
                       "-vnc :{vnc} " \
                       "-monitor tcp:127.0.0.1:1234,server,nowait,nodelay " \
                       "-qmp tcp:127.0.0.1:1235,server,nowait,nodelay " \
                       "".format(  # -monitor tcp:1234,server,nowait,nodelay
            cpu=self.cpu_to_pin,
            qemu_exe=self.exe,
            sidecore=sidecore_param,
            kernel_additions=kernel_spicific_boot,
            qemu_additionals=self.qemu_additionals,
            disk=self.path,
            tap=self.tap_device,
            vhost=vhost_param,
            dev_type=self.ethernet_dev,
            mac=self.mac_address,
            nic_additionals=self.nic_additionals + self._get_temp_nic_additional(),
            pidfile=self.pidfile.name,
            vnc=self.vnc_number,
            mem=self.mem,
        )
        run_command_async(qemu_command)
        sleep(0.5)
        if self.qemu_config:
            self.change_qemu_parameters()
        if self.is_io_thread_nice:
            self.set_iothread_nice()
        sleep(1)
        self.qmp.connect()

    def set_iothread_nice(self, nice=None):
        if nice is None:
            nice = self.io_nice
        run_command_remote("127.0.0.1", "root", "renice -n {} -p {}".format(nice, self.get_pid()))

    def change_qemu_parameters(self, config=None):
        if config:
            self.qemu_config.update(config)
        if self.io_thread_cpu:
            command = "taskset -p -c {} {}".format(self.io_thread_cpu, self.get_pid())
            run_command_check(command)

        with open(self.QEMU_E1000_DEBUG_PARAMETERS_FILE, "w") as f:
            for name, value in self.qemu_config.items():
                f.write("{} {}\n".format(name, value))
                logger.debug("set qemu option: %s=%s", name, value)
        self._signal_qemu()

    def get_pid(self):
        if self._pid:
            return self._pid
        with open(self.pidfile.name, "r") as f:
            pid = int(f.read().strip())
        self._pid = pid
        return pid

    def _signal_qemu(self):
        pid = self.get_pid()
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
        self.nic_additionals = ',pcix=true'

    def _configure_host(self):
        try:
            run_command_check("echo 1 | sudo tee /proc/sys/debug/tun/no_tcp_checksum_on", shell=True)
        except CalledProcessError:
            pass

    def _reset_host_configuration(self):
        try:
            run_command_check("echo 0 | sudo tee /proc/sys/debug/tun/no_tcp_checksum_on", shell=True)
        except CalledProcessError:
            pass

    def configure_guest(self):
        commands = (
            "echo 1 | sudo tee /proc/sys/debug/kernel/srtt_patch_on",
            "echo 1 | sudo tee /proc/sys/net/ipv4/tcp_srtt_patch",
        )
        for cmd in commands:
            try:
                self.remote_command(cmd)
            except CalledProcessError:
                pass

        if self.addiotional_guest_command:
            self.remote_command(self.addiotional_guest_command)


class QemuLargeRing(QemuE1000Max):
    def configure_guest(self):
        super(QemuLargeRing, self).configure_guest()
        self.remote_command("sudo ethtool -G eth0 rx 4096")
        self.remote_command("sudo ethtool -G eth0 tx 4096")


class QemuNG(Qemu):
    QEMU_E1000_BETTER = 'e1000-82545em'
    BOOTUP_WAIT = 7

    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.e1000_options = dict()
        self.large_queue = False
        self.static_itr = False
        self.queue_size = 0

    def _get_temp_nic_additional(self):
        return "," + ",".join(("%s=%s" % (k, v) for k, v in self.e1000_options.items()))

    def configure_guest(self):
        super().configure_guest()
        if self.large_queue:
            self.remote_command("sudo ethtool -G eth0 rx {}".format(self.queue_size))
            self.remote_command("sudo ethtool -G eth0 tx {}".format(self.queue_size))
        if self.static_itr:
            self.remote_command("sudo ethtool -C eth0 rx-usecs 4000")


class QemuE1000NG(QemuNG):
    def __init__(self, *args, **kargs):
        super(QemuE1000NG, self).__init__(*args, **kargs)
        self.e1000_options = {
            "NG_no_checksum": "on",
            "NG_no_tcp_seg": "on",
            "NG_pcix": "on",
            "NG_tx_iothread": "on",
            "NG_vsend": "on",
            "NG_tso_offloading": "on",
            "NG_drop_packet": "off",
            "NG_interrupt_mul": 10,  #1,  # 10
            "NG_interrupt_mode": 0,  #1  # 0
            "NG_parabatch": "off",
        }

        self.ethernet_dev = self.QEMU_E1000
        # self.ethernet_dev = 'e1000-82545em'

        self.addiotional_guest_command = None
        self.is_io_thread_nice = False
        self.io_nice = 5  # nice value to set
        # self.kernel = r"/homes/bdaviv/repos/msc-ng/linux-4.13.9/arch/x86/boot/bzImage"
        # self.initrd = r"/homes/bdaviv/repos/msc-ng/vm-files/kernels/initrd.img-4.13.9-ng+"

    def configure_guest(self):
        super().configure_guest()
        commands = (
            "echo 1 | sudo tee /proc/sys/debug/kernel/srtt_patch_on", # old location
            # "echo 1 | sudo tee /proc/sys/net/ipv4/tcp_srtt_patch", # new location
            # "echo 1 | sudo tee /proc/sys/net/ipv4/tcp_srtt_patch", # new location
        )
        for cmd in commands:
            try:
                self.remote_command(cmd)
            except CalledProcessError:
                pass

        if self.addiotional_guest_command:
            self.remote_command(self.addiotional_guest_command)


class QemuLargeRingNG(QemuE1000NG):
    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.ethernet_dev = 'e1000-82545em'
        self.large_queue = True
        self.static_itr = True


class QemuVirtioNG(QemuNG):
    def __init__(self):
        super().__init__()
        self.e1000_options = {
            "NG_drop_packet": "on"
        }
        self.ethernet_dev = self.QEMU_VIRTIO


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
