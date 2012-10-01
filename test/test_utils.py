from subprocess import Popen, PIPE
import sys


class ProcessTimedout(Exception):
    """
    Raised if a process timeout.
    """


class ProcessError(Exception):
    """
    Raised if a process fail.
    """


def timed_process(args, timeout=None, env=None):
    """
    Execute a command using :py:mod:`subprocess` module,
    if timeout is specified the process is killed if it does
    not terminate in the maxim required time.

    Parameters:

    args
        the command to run, in a list format

    timeout
        the maximum time to wait for the process to terminate
        before killing it

    env
        a dictionary representing the environment
    """
    if env is None:
        env = {"PATH": "/usr/bin:/usr/sbin:/bin:/sbin", }
    try:
        proc = Popen(args, stdout=PIPE, stderr=PIPE, shell=False, env=env)
    except OSError:
        error = sys.exc_info()[1]
        raise ProcessError("OSError %s" % error)
    except ValueError:
        error = sys.exc_info()[1]
        raise ProcessError("ValueError %s" % error)
    if timeout is None:
        out, err = proc.communicate()
        return (proc.poll(), out, err)
    maxt = time.time() + timeout
    while proc.poll() is None and time.time() < maxt:
        time.sleep(CHECK_TIME)
    if proc.poll() is None:
        try:
            getattr(proc, "send_signal")
            proc.send_signal(signal.SIGKILL)
        except AttributeError:
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except OSError:  # process already gone
                pass
        raise ProcessTimedout("Process %s timed out after %s seconds." %
                              (" ".join(args), timeout))
    else:
        out, err = proc.communicate()
        return (proc.poll(), out, err)
