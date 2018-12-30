from functools import lru_cache


@lru_cache()
def read_cpu_speed():
    """
    return cpu speed in MHz
    :return:
    """
    with open("/proc/cpuinfo") as f:
        for l in f:
            if l.startswith("cpu MHz"):
                _, speed = l.split(":")
                return float(speed)