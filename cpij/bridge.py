from multiprocessing.managers import SyncManager
import multiprocessing as mp
import atexit, cpij.server as ijserver

class QueueManager(SyncManager): pass
QueueManager.register('input_queue')
QueueManager.register('output_queue')
QueueManager.register('get_lock')

_to_ij_queue = None
_from_ij_queue = None
_sync_lock = None


def lock():
    """
    Helper method to synchronzie requests with the ImageJ server.

    A lock should be acquired before sending data to the server, and released after
    receiving the result.

    Returns
    ---------
    A Lock connected to the ImageJ server.
    """
    _init_queues()
    global _sync_lock
    return _sync_lock

def to_imagej():
    """
    Helper method to send data to the ImageJ server

    Returns
    ---------
    A Queue connected to the ImageJ server. Only its put method should be called.
    """
    _init_queues()
    global _to_ij_queue
    return _to_ij_queue


def from_imagej():
    """
    Helper method to retrieve data from the ImageJ server

    Returns
    ---------
    A Queue connected to the ImageJ server. Only its get method should be called.
    """
    _init_queues()
    global _from_ij_queue
    return _from_ij_queue


def init_pyimagej(init_string):
    """
    Start the pyimagej daemon thread if it isn't already running.

    Parameters
    ----------
    init_string : str, optional
        This can be a path to a local ImageJ installation, or an initialization string per imagej.init(),
        e.g. sc.fiji:fiji:2.1.0
    """
    to_imagej().put({ijserver.PYIMAGEJ_KEY_COMMAND: ijserver.PYIMAGEJ_CMD_START,
                     ijserver.PYIMAGEJ_KEY_INPUT: init_string})
    result = from_imagej().get()
    if result == ijserver.PYIMAGEJ_STATUS_STARTUP_FAILED:
        return False
    return True


def _init_queues():
    """
    Helper method to cache intput/output queues for this process to communicate
    with the ImageJ server.
    """
    global _to_ij_queue, _from_ij_queue, _sync_lock
    if _to_ij_queue is None:
        if not ijserver.is_server_running():
            raise RuntimeError("No ImageJ server instance available")

        manager = QueueManager(address=('127.0.0.1', ijserver.SERVER_PORT), authkey=ijserver._SERVER_KEY)
        manager.connect()
        _to_ij_queue = manager.input_queue()
        _from_ij_queue = manager.output_queue()
        _sync_lock = manager.get_lock()


def _shutdown_imagej_on_close():
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

    ctx = mp.get_context('spawn')
    p = ctx.Process(target=ijserver.main)
    p.start()

    # wait for the server to start up
    ijserver.wait_for_server_startup()

    # Ensure server shuts down when main app closes
    atexit.register(_shutdown_imagej_on_close)