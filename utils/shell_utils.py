import logging
import subprocess
import shlex

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def run_command(command_string, shell=False):
    logger.debug("Run command: %s", command_string)
    return subprocess.call(shlex.split(command_string), shell=shell)


def run_command_check(command_string, shell=False):
    logger.debug("Run command (checked): %s", command_string)
    return subprocess.check_call(shlex.split(command_string), shell=shell)


def run_command_output(command_string, shell=False):
    logger.debug("Run command (checked): %s", command_string)
    output = subprocess.check_output(shlex.split(command_string), shell=shell)
    logger.debug("Command output: %s", output)
    return output.decode()


def run_command_remote(servername, user, command):
    full_command = "ssh {user}@{host} {command}".format(host=servername, user=user, command=command)
    return run_command_output(full_command)


def run_command_async(command, output_file=None):
    logger.debug("Run command (async): %s", command)
    subprocess.Popen(shlex.split(command), stdout=output_file)
