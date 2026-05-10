from multiprocessing.managers import SyncManager
import multiprocessing as mp
import atexit, cpij.server as ijserver
from queue import Queue
from threading import Lock


class QueueManager(SyncManager):
    pass


QueueManager.register("input_queue")
QueueManager.register("output_queue")
QueueManager.register("get_lock")

_init_method = None


def init_method():
    global _init_method
    if not _init_method:
        if ijserver.is_server_running():
            l = lock()
            l.acquire()
            to_imagej().put(
                {ijserver.PYIMAGEJ_KEY_COMMAND: ijserver.PYIMAGEJ_CMD_GET_INIT_METHOD}
            )
            _init_method = from_imagej().get()[ijserver.PYIMAGEJ_KEY_OUTPUT]
            l.release()

    return _init_method


def lock() -> Lock:
    """
    Helper method to synchronzie requests with the ImageJ server.

    A lock should be acquired before sending data to the server, and released after
    receiving the result.

    Returns
    ---------
    A Lock connected to the ImageJ server.
    """
    return _manager().get_lock()


def to_imagej() -> Queue:
    """
    Helper method to send data to the ImageJ server

    Returns
    ---------
    A Queue connected to the ImageJ server. Only its put method should be called.
    """
    return _manager().input_queue()


def from_imagej() -> Queue:
    """
    Helper method to retrieve data from the ImageJ server

    Returns
    ---------
    A Queue connected to the ImageJ server. Only its get method should be called.
    """
    return _manager().output_queue()


def init_pyimagej(init_string):
    """
    Start the pyimagej daemon thread if it isn't already running.

    Parameters
    ----------
    init_string : str, optional
        This can be a path to a local ImageJ installation, or an initialization string per imagej.init(),
        e.g. sc.fiji:fiji:2.1.0
    """
    to_imagej().put(
        {
            ijserver.PYIMAGEJ_KEY_COMMAND: ijserver.PYIMAGEJ_CMD_START,
            ijserver.PYIMAGEJ_KEY_INPUT: init_string,
        }
    )
    result = from_imagej().get()
    if result == ijserver.PYIMAGEJ_STATUS_STARTUP_FAILED:
        _shutdown_imagej()
        # Wait for the server to shut down
        while ijserver.is_server_running():
            pass
        return False

    global _init_method
    _init_method = init_string
    return True


def _manager() -> QueueManager:
    """
    Helper method to return a QueueManager connected to the ImageJ server
    """
    if not ijserver.is_server_running():
        raise RuntimeError("No ImageJ server instance available")

    manager = QueueManager(
        address=("127.0.0.1", ijserver.SERVER_PORT), authkey=ijserver._SERVER_KEY
    )
    manager.connect()
    return manager


def _shutdown_imagej():
    """
    Helper method to send the shutdown signal to ImageJ. Intended to be called
    at process exit.
    """
    if ijserver.is_server_running():
        to_imagej().put({ijserver.PYIMAGEJ_KEY_COMMAND: ijserver.PYIMAGEJ_CMD_EXIT})


def start_imagej_server():
    """
    If the ImageJ server is not already running, spawns the server in a new
    Process. Blocks until the server is up and running.
    """
    if ijserver.is_server_running():
        return

    ctx = mp.get_context("spawn")
    p = ctx.Process(target=ijserver.main)
    p.start()

    # wait for the server to start up
    ijserver.wait_for_server_startup()

    # Ensure server shuts down when main app closes
    atexit.register(_shutdown_imagej)
