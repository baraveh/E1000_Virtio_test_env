import logging
import os
from subprocess import CalledProcessError

from qemu.qmp import QEMUMonitorProtocol
from utils.machine import Machine, localRoot
from utils.shell_utils import run_command_output, run_command_check, run_command_remote, run_command_async, run_command
from time import sleep
from tempfile import NamedTemporaryFile
import signal

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class VM(Machine):
    BOOTUP_WAIT = 50  # 15
    POWEROFF_WAIT = 3
    USER = "user"

    def __init__(self, path, guest_ip, host_ip):
        super(VM, self).__init__(guest_ip, self.USER)
        self.path = path
        self.ip_guest = guest_ip
        self.ip_host = host_ip
        self.bootwait = self.BOOTUP_WAIT
        self.netperf_test_params = ""
        self.guest_configure_commands = list()

    def get_info(self, old_info=None):
        DISK_PATH = "disk_path"
        info = super().get_info(old_info)

        if not self.enabled:
            info.update({k: old_info[k] for k in (DISK_PATH,)})
        else:
            info[DISK_PATH] = self.path
        return info

    def _run(self):
        raise NotImplementedError()

    def configure_guest(self):
        for cmd in self.guest_configure_commands:
            self.remote_command(cmd)

    def shutdown(self):
        self.remote_root_command("poweroff")
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

    BOOTUP_WAIT = 30

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
        self.mem = "8192"

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
        self.kernel = r"../vms/vmlinuz" #r"../linux/arch/x86/boot/bzImage"
        # self.initrd = r"../vms/initrd.img"
        # self.initrd = r"/homes/bdaviv/repos/msc-ng/vm-files/kernels/initrd.img-4.13.9-ng+"
        self.initrd = r"../vms/initrd.img" # r"../vms/initrd.img"
        self.kernel_cmdline = r"BOOT_IMAGE=/vmlinuz-5.4.0-73-generic root=/dev/mapper/ubuntu--vg-ubuntu--lv ro maybe-ubiquity"
        self.kernel_cmdline_additional = ""

        self.nic_additionals = ""
        self.qemu_additionals = ""

        self.disable_kvm_poll = False

        self.guest_e1000_ng_flag = 0

        self.qmp = None

    def get_info(self, old_info=None):
        KERNEL_FILE = "kernel_file"
        KERNEL_GIT = "kernel_git"
        KERNEL_CMD = "kernel_cmd"

        QEMU_FILE = "qemu_file"
        QEMU_GIT = "qemu_git"

        NIC_TYPE = "nic_type"
        CPU_PIN = "cpu_pin"
        MEM = "mem"
        NICE = "nice"

        keys = (KERNEL_FILE, KERNEL_GIT, KERNEL_CMD, QEMU_FILE, QEMU_GIT, NIC_TYPE, CPU_PIN, MEM, NICE)

        info = super().get_info(old_info)

        if not self.enabled:
            info.update({k: old_info[k] for k in keys})
        else:
            #info[KERNEL_FILE] = self.kernel
            #info[KERNEL_GIT] = run_command_output("git -C {directory} rev-parse --short HEAD".format(
            #    directory=os.path.dirname(self.kernel)
            #)).strip()
            info[KERNEL_CMD] = self.kernel_cmdline

            info[QEMU_FILE] = self.exe
            #info[QEMU_GIT] = run_command_output("git -C {directory} rev-parse --short HEAD".format(
            #    directory=os.path.dirname(self.exe)
            #)).strip()

            info[NIC_TYPE] = self.ethernet_dev
            info[CPU_PIN] = self.cpu_to_pin
            info[MEM] = self.mem
            info[NICE] = (self.is_io_thread_nice, self.io_nice)
        return info

    def run(self, configure_guest=True):
        super().run(configure_guest)

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
            run_command("sudo brctl delif {br} {iff}".format(br=self.bridge, iff=self.tap_device))
        while True:
            try:
                run_command_check("sudo tunctl -d {tap}".format(tap=self.tap_device))
                break
            except:
                sleep(1)

    def load_kvm(self):
        run_command_check("sudo modprobe kvm-intel")
        if self.disable_kvm_poll:
            run_command_check("echo 0 | sudo tee /sys/module/kvm/parameters/halt_poll_ns")

    def unload_kvm(self):
        sleep(1)
        run_command("sudo modprobe -r kvm-intel")

    def _clean_cpu(self):
        run_command("echo 0 |sudo tee /sys/devices/system/cpu/cpu{cpu}/online".format(
            cpu=self.cpu_to_pin
        ), shell=True)
        run_command("echo 1 |sudo tee /sys/devices/system/cpu/cpu{cpu}/online".format(
            cpu=self.cpu_to_pin
        ), shell=True)

    def setup(self):
        super().setup()
        self.load_kvm()
        self.create_tun()
        self._configure_host()
        self._clean_cpu()

    def teardown(self):
        try:
            self.shutdown()
            self.qmp.close()
        except:
            pass
        self.qmp = QEMUMonitorProtocol(('127.0.0.1', 1235))
        self._pid = None
        self._reset_host_configuration()
        sleep(20)
        self.delete_tun()
        sleep(2)
        self.unload_kvm()
        super().teardown()

    def _get_temp_nic_additional(self):
        return ""

    def _run(self):
        assert self.exe

        self.qmp = QEMUMonitorProtocol(('127.0.0.1', 1235))
        self.pidfile = NamedTemporaryFile()

        if self.vhost:
            vhost_param = ",vhost=on"
            # HACK HACK HACK
            localRoot.remote_command("chown :kvm /dev/vhost-net")
            localRoot.remote_command("chmod 660 /dev/vhost-net")
        else:
            vhost_param = ""

        if self.sidecore:
            sidecore_param = "-enable-e1000-sidecore"
        else:
            sidecore_param = ""

        self.pidfile.close()
        self.pidfile = NamedTemporaryFile()

        kernel_spicific_boot = ""
        kernel_command_line = self.kernel_cmdline_additional
        if "e1000.NG_flags" not in self.kernel_cmdline_additional and self.guest_e1000_ng_flag != 0:
            kernel_command_line += " e1000.NG_flags={}".format(self.guest_e1000_ng_flag)
        if self.kernel:
            kernel_spicific_boot = "-kernel {kernel} -initrd {initrd} -append '{cmdline} {cmdline_more}'".format(
                kernel=self.kernel,
                initrd=self.initrd,
                cmdline=self.kernel_cmdline,
                cmdline_more=kernel_command_line
            )

        qemu_command = "sudo taskset -c {cpu} numactl -m 0 {qemu_exe} -enable-kvm {sidecore} -k en-us -m {mem} " \
                       "{kernel_additions} " \
                       "{qemu_additionals} " \
                       "-drive file='{disk}',if=none,id=drive-virtio-disk0,format=qcow2 " \
                       "-device virtio-blk-pci,scsi=off,bus=pci.0,addr=0x5,drive=drive-virtio-disk0,id=virtio-disk0,bootindex=1 " \
                       "-netdev tap,ifname={tap},id=net0,script=no{vhost} " \
                       "-object iothread,id=iothread0 " \
                       "-device {dev_type},netdev=net0,mac={mac}{nic_additionals} " \
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
            # "-pidfile {pidfile} " \
        )
        run_command_async(qemu_command)
        sleep(0.5)
        if self.qemu_config:
            self.change_qemu_parameters()
        sleep(0.5)
        if self.io_thread_cpu:
            command = "sudo taskset -p -c {} {}".format(self.io_thread_cpu, self.get_pid())
            run_command_check(command)
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
        super().configure_guest()

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
        super().configure_guest()
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
    # BOOTUP_WAIT = 50

    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.e1000_options = dict()
        self.large_queue = False
        self.static_itr = False
        self.queue_size = 0

    def _get_temp_nic_additional(self):
        return "," + ",".join(("%s=%s" % (k, v) for k, v in self.e1000_options.items()))

    def configure_guest(self):
        logger.info("**********: %s", self.guest_configure_commands)
        super().configure_guest()
        if self.large_queue:
            self.remote_command("sudo ethtool -G eth0 rx {}".format(self.queue_size))
            self.remote_command("sudo ethtool -G eth0 tx {}".format(self.queue_size))
        if self.static_itr:
            self.remote_command("sudo ethtool -C eth0 rx-usecs 4000")

    def get_info(self, old_info=None):
        E1000_OPTIONS = "e1000_options"
        LARGE_QUEUE = "large_queue"
        STATIC_ITR = "static_itr"
        QUEUE_SIZE = "queue_size"
        keys = (E1000_OPTIONS, LARGE_QUEUE, STATIC_ITR, QUEUE_SIZE)

        info = super().get_info(old_info)

        if not self.enabled:
            info.update({k: old_info[k] for k in keys})
        else:
            info.update({k: getattr(self, k) for k in keys})

        return info


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
            "NG_interrupt_mode": 0,  # 0 - normal,
                                     # 1 - batch,
                                     # 2 - smart timer reference to end of recv,
                                     # 3 - smart timer reference to last interrupt (as normal)
            "NG_parabatch": "off",
            "NG_vcpu_send_latency": "on",  # skip context switch to iothread if low latency mode detected
            # "NG_interuupt_momentum": 1,
            # "NG_interuupt_momentum_max": 20,
            "NG_disable_iothread_lock": "off",  # disable taking iothread lock in e1000 mmio

            "NG_disable_TXDW": "off" # disable TXDW interrupt on TX finish
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


class QemuE1000NGBest(QemuE1000NG):
    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.e1000_options.update({
            "NG_no_checksum": "on",
            "NG_no_tcp_seg": "on",
            "NG_tx_iothread": "on",
            "NG_parahalt": "on",
            "NG_interrupt_mode": 0,
            "NG_interrupt_mul": 0,
            "mitigation": "off",
            "NG_disable_rdt_jump": "on",
            "NG_vsend": "on",
            "NG_pcix": "on",
        })
        self.guest_e1000_ng_flag = 1


class QemuE1000NGAdaptive(QemuE1000NG):
    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.e1000_options.update({
            "NG_no_checksum": "on",
            "NG_no_tcp_seg": "on",
            "NG_tx_iothread": "on",
            # "NG_parahalt": "on",
            "NG_interrupt_mode": 3,
            "NG_interrupt_mul": 1,
            # "mitigation": "off",
            "NG_disable_rdt_jump": "on",
            "NG_vsend": "on",
            "NG_pcix": "on",
        })
        self.guest_e1000_ng_flag = 1


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
        super().setup()
        run_command_check("sudo service vmware start")
        sleep(1)

    def _run(self):
        command = "vmrun -T ws start {} nogui".format(self.path)
        run_command_check(command)

    def teardown(self):
        self.shutdown()
        run_command_check("sudo service vmware stop")
        sleep(1)
        super().teardown()


virtualBox_count = 0
class VirtualBox(VM):
    BOOTUP_WAIT = 30
    POWEROFF_WAIT = 10

    def setup(self):
        global virtualBox_count
        super().setup()
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
        super().teardown()

    def _run(self):
        command = "VBoxManage startvm {} --type headless".format(self.path)
        run_command_check(command)
