import socket

from utils.shell_utils import run_command_remote, run_prepare_command, run_command_remote_ex


class Machine:
    def __init__(self, remote_ip, remote_user):
        self._user = remote_user
        self._remote_ip = remote_ip
        self.name = None
        self.enabled = True

    def remote_command(self, command, **kargs):
        return run_command_remote(self._remote_ip, self._user, command, **kargs)

    def remote_command_prepare(self, command):
        return run_prepare_command(self._remote_ip, self._user, command)

    def remote_command_ex(self, command):
        return run_command_remote_ex(self._remote_ip, self._user, command)

    def remote_root_command(self, command, **kargs):
        return run_command_remote(self._remote_ip, "root", command, **kargs)

    def get_info(self, old_info=None) -> dict:
        ENABLED = "enabled"
        if not self.enabled and old_info is None:
            raise ValueError()

        return {ENABLED: self.enabled}



class LocalRoot(Machine):
    def __init__(self):
        super().__init__("127.0.0.1", "root")
        self.name = "localhost"

    def get_info(self, old_info=None):
        info = dict()
        info["kernel_version"] = self.remote_command("uname -r")
        info["hostname"] = socket.gethostname()
        return info


localRoot = LocalRoot()

