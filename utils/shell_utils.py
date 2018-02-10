import logging
import subprocess
import shlex

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def run_command(command_string, shell=False, cwd=None):
    logger.debug("Run command: %s", command_string)
    if shell:
        args = command_string
    else:
        args = shlex.split(command_string)
    return subprocess.call(args, shell=shell, cwd=cwd)


def run_command_ex(command_string, shell=False, **kargs):
    logger.debug("Run command: %s", command_string)
    return subprocess.Popen(shlex.split(command_string), shell=shell, **kargs)


def run_command_check(command_string, shell=False, cwd=None):
    logger.debug("Run command (checked): %s", command_string)
    if not shell:
        cmd = shlex.split(command_string)
    else:
        cmd = command_string
    return subprocess.check_call(cmd, shell=shell, cwd=cwd)


def run_command_output(command_string, shell=False, log_output=True, cwd=None):
    logger.debug("Run command (checked): %s", command_string)
    if shell:
        args = command_string
    else:
        args = shlex.split(command_string)
    output = subprocess.check_output(args, shell=shell, cwd=cwd)
    if log_output:
        logger.debug("Command output: %s", output)
    return output.decode()


def run_prepare_command(servername, user, command):
    full_command = 'ssh {user}@{host} \'{command}\''.format(host=servername, user=user, command=command)
    return full_command


def run_command_remote(servername, user, command, **kargs):
    full_command = run_prepare_command(servername, user, command)
    return run_command_output(full_command, **kargs)


def run_command_remote_ex(servername, user, command):
    full_command = run_prepare_command(servername, user, command)
    return run_command_ex(full_command)


def run_command_async(command, output_file=None, cwd=None):
    logger.debug("Run command (async): %s", command)
    subprocess.Popen(shlex.split(command), stdout=output_file, cwd=cwd)
