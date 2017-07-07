from utils.shell_utils import run_command_remote, run_prepare_command, run_command_remote_ex


class Machine:
    def __init__(self, remote_ip, remote_user):
        self._user = remote_user
        self._remote_ip = remote_ip

    def remote_command(self, command, **kargs):
        return run_command_remote(self._remote_ip, self._user, command, **kargs)

    def remote_command_prepare(self, command):
        return run_prepare_command(self._remote_ip, self._user, command)

    def remote_command_ex(self, command):
        return run_command_remote_ex(self._remote_ip, self._user, command)


localRoot = Machine("127.0.0.1", "root")
