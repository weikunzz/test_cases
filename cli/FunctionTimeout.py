import multiprocessing
import signal
import os
import sys
import psutil


# kill subprocess and chidren of it via subprocess id
def kill_subprocess(sub_pid):
    try:
        p = psutil.Process(sub_pid)
    except psutil.NoSuchProcess:
        return

    children = p.children(recursive=True)
    children.append(p)
    for child in children:
        try:
            os.kill(child.pid, signal.SIGKILL)
        except OSError:
            # do nothing when process does not exist anymore
            pass


class TimeOut(Exception):
    """
	from FunctionTimeout import TimeOut
    Traceback (most recent call last):
        File "<stdin>", line 1, in <module>
        File "FunctionTimeout.py", line 62, in wrappee
            raise TimeOut(self.timeout)
    TimeOut: TimeOut: 10s
    """
    def __init__(self, timeout):
        err = "%ss" % str(timeout)
        Exception.__init__(self, err)



class FunctionTimeout(object) :
    def __init__(self, timeout = 60, is_exit=True) :
        self.timeout = timeout
        self.is_exit = is_exit

    def __call__(self, original_func) :
        decorator_self = self

        def wrappee(*args, **kwargs) :
            q = multiprocessing.Queue()
            q.put(None)

            real_args = args
            real_kwargs = kwargs

            def __run(func, real_args, real_kwargs) :
                result = func(*real_args, **real_kwargs)
                q.get()
                q.put(result)

            proc_args = (original_func, real_args, real_kwargs)
            proc_task = multiprocessing.Process(target = __run, args = proc_args)
            proc_task.start()

            proc_task.join(decorator_self.timeout)
            if proc_task.is_alive():
                kill_subprocess(proc_task.ident)
                if self.is_exit:
                    print "Error(553): Unknown error: Timeout"
                    sys.exit(1)
                else:
                    raise TimeOut(self.timeout)

            if proc_task.exitcode:
                sys.exit(proc_task.exitcode)

            return q.get()

        return wrappee
