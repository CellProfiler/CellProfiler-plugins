from multiprocessing.managers import BaseManager
import multiprocessing as mp
import atexit, cpij.server as ijserver

class QueueManager(BaseManager): pass
QueueManager.register('input_queue')
QueueManager.register('output_queue')

_to_ij_queue = None
_from_ij_queue = None


def to_imagej():
    _init_queues()
    global _to_ij_queue
    return _to_ij_queue


def from_imagej():
    _init_queues()
    global _from_ij_queue
    return _from_ij_queue


def init_pyimagej(init_string):
    """
    Start the pyimagej daemon thread if it isn't already running.
    """
    to_imagej().put({ijserver.PYIMAGEJ_KEY_COMMAND: ijserver.PYIMAGEJ_CMD_START,
                     ijserver.PYIMAGEJ_KEY_INPUT: init_string})
    result = from_imagej().get()
    if result == ijserver.PYIMAGEJ_STATUS_STARTUP_FAILED:
        return False
    return True


def server_running(timeout=0.25):
    return ijserver.server_running(timeout)


def _init_queues():
    global _to_ij_queue, _from_ij_queue
    if _to_ij_queue is None:
        if not server_running():
            raise RuntimeError("No ImageJ server instance available")

        manager = QueueManager(address=('127.0.0.1', ijserver.SERVER_PORT), authkey=ijserver._SERVER_KEY)
        manager.connect()
        _to_ij_queue = manager.input_queue()
        _from_ij_queue = manager.output_queue()


def _shutdown_imagej_on_close():
    if server_running():
        to_imagej().put({ijserver.PYIMAGEJ_KEY_COMMAND: ijserver.PYIMAGEJ_CMD_EXIT})


def start_imagej_server():
    """
    If the ImageJ server is not already running, spawns the server in a new
    Process.
    """
    if server_running():
        return

    ctx = mp.get_context('spawn')
    p = ctx.Process(target=ijserver.main)
    p.start()

    # wait for the server to start up
    # FIXME: don't wait indefinitely...
    while not server_running():
        pass

    # Ensure server shuts down when main app closes
    atexit.register(_shutdown_imagej_on_close)