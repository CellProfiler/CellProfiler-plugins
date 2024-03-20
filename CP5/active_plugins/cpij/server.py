from pathlib import Path
from multiprocessing.managers import SyncManager
from queue import Queue
from cellprofiler_core.image import Image
from cellprofiler_core.setting.text.alphanumeric.name.image_name import ImageName
from cellprofiler_core.setting.text import (
    Filename,
    Directory,
    Alphanumeric,
    Integer,
    Float,
)
from cellprofiler_core.setting.subscriber import ImageSubscriber
from cellprofiler_core.setting import ValidationError
import jpype, imagej, multiprocessing, socket, threading, time
import skimage.io


"""
Constants for communicating with pyimagej
"""
PYIMAGEJ_KEY_COMMAND = "KEY_COMMAND"  # Matching value indicates what command to execute
PYIMAGEJ_KEY_INPUT = "KEY_INPUT"  # Matching value is command-specific input object
PYIMAGEJ_KEY_OUTPUT = "KEY_OUTPUT"  # Matching value is command-specific output object
PYIMAGEJ_CMD_START = "COMMAND_START"  # Start the PyImageJ instance + JVM
PYIMAGEJ_CMD_GET_INIT_METHOD = (
    "COMMAND_GET_INIT_METHOD"  # Get the initialization string used for PyImageJ
)
PYIMAGEJ_CMD_SCRIPT_PARSE = "COMMAND_SCRIPT_PARAMS"  # Parse a script file's parameters
PYIMAGEJ_SCRIPT_PARSE_INPUTS = "SCRIPT_PARSE_INPUTS"  # Script input dictionary key
PYIMAGEJ_SCRIPT_PARSE_OUTPUTS = "SCRIPT_PARSE_OUTPUTS"  # Script output dictionary key
PYIMAGEJ_CMD_SCRIPT_RUN = "COMMAND_SCRIPT_RUN"  # Run a script
PYIMAGEJ_SCRIPT_RUN_FILE_KEY = "SCRIPT_RUN_FILE_KEY"  # The script filename key
PYIMAGEJ_SCRIPT_RUN_INPUT_KEY = (
    "SCRIPT_RUN_INPUT_KEY"  # The script input dictionary key
)
PYIMAGEJ_SCRIPT_RUN_CONVERT_IMAGES = (
    "SCRIPT_RUN_CONVERT_IMAGES"  # Whether images should be converted or not
)
PYIMAGEJ_CMD_EXIT = "COMMAND_EXIT"  # Shut down the pyimagej daemon
PYIMAGEJ_STATUS_CMD_UNKNOWN = (
    "STATUS_COMMAND_UNKNOWN"  # Returned when an unknown command is passed to pyimagej
)
PYIMAGEJ_STATUS_STARTUP_COMPLETE = (
    "STATUS_STARTUP_COMPLETE"  # Returned after initial startup before daemon loop
)
PYIMAGEJ_STATUS_STARTUP_FAILED = (
    "STATUS_STARTUP_FAILED"  # Returned when imagej.init fails
)
PYIMAGEJ_STATUS_SHUTDOWN_COMPLETE = (
    "STATUS_SHUTDOWN_COMPLETE"  # Returned when imagej + jpype JVM have closed
)
INIT_LOCAL = "Local"
INIT_ENDPOINT = "Endpoint"
INIT_LATEST = "Latest"
INPUT_CLASS = "INPUT"
OUTPUT_CLASS = "OUTPUT"

SERVER_PORT = 45923
# FIXME this needs to be encrypted somehow
_SERVER_KEY = b"abracadabra"

_in_queue = Queue()
_out_queue = Queue()
_sync_lock = threading.Lock()


class QueueManager(SyncManager):
    pass


QueueManager.register("input_queue", callable=lambda: _in_queue)
QueueManager.register("output_queue", callable=lambda: _out_queue)
QueueManager.register("get_lock", callable=lambda: _sync_lock)


class Character(Alphanumeric):
    """
    A Setting for text entries of size one
    """

    def __init__(self, text, value, *args, **kwargs):
        super().__init__(text, value, *args, **kwargs)

    def test_valid(self, pipeline):
        """
        Restrict value to single character
        """
        super().test_valid(pipeline)
        if len(self.value) > 1:
            raise ValidationError("Only single characters can be used.", self)


class Boolean(Integer):
    """
    A helper setting for boolean values, converting 0 to False and any other number to True
    """

    def __init__(self, text, value, *args, **kwargs):
        super().__init__(
            text,
            value,
            doc="""\
Enter '0' for \"False\" and any other value for \"True\"
""",
            *args,
            **kwargs,
        )

    def get_value(self, reraise=False):
        v = super().get_value(reraise)
        if v == 0:
            return False

        return True


def _preprocess_script_inputs(ij, input_map, convert_images):
    """
    Helper method to convert pythonic inputs to something that can be handled by ImageJ

    In particular this is necessary for image inputs which won't be auto-converted by Jpype

    Parameters
    ----------
    ij : imagej.init(), required
        ImageJ entry point (from imagej.init())
    input_map: map, required
        map of input names to values
    convert_images: boolean, required
        boolean indicating if image inputs and outputs should be auto-converted to appropriate numeric types
    """
    for key in input_map:
        if isinstance(input_map[key], Image):
            cp_image = input_map[key].get_image()
            # CellProfiler images are typically stored as floats which can cause unexpected results in ImageJ.
            # By default, we convert to 16-bit int type, unless we're sure it's 8 bit in which case we use that.
            if convert_images:
                if input_map[key].scale == 255:
                    cp_image = skimage.img_as_ubyte(cp_image)
                else:
                    cp_image = skimage.img_as_uint(cp_image)
            input_map[key] = ij.py.to_dataset(cp_image)


def _convert_java_to_python_type(ij, return_value):
    """
    Helper method to convert ImageJ/Java values to python values that can be passed between via queues (pickled)

    Parameters
    ----------
    ij : imagej.init(), required
        ImageJ entry point
    return_value : supported Java type, required
        A value to convert from Java to python

    Returns
    ---------
    An instance of a python type that can safely cross queues with the given value, or None if no valid type exists.
    """
    if return_value is None:
        return None
    return_class = return_value.getClass()
    type_string = str(return_class.toString()).split()[1]

    image_classes = (
        jpype.JClass("ij.ImagePlus"),
        jpype.JClass("net.imagej.Dataset"),
        jpype.JClass("net.imagej.ImgPlus"),
    )

    if type_string == "java.lang.String" or type_string == "java.lang.Character":
        return str(return_value)
    elif (
        type_string == "java.lang.Integer"
        or type_string == "java.lang.Long"
        or type_string == "java.lang.Short"
    ):
        return int(return_value)
    elif type_string == "java.lang.Float" or type_string == "java.lang.Double":
        return float(return_value)
    elif type_string == "java.lang.Boolean":
        if return_value:
            return True
        else:
            return False
    elif type_string == "java.lang.Byte":
        return bytes(return_value)
    elif bool(
        (
            img_class
            for img_class in image_classes
            if issubclass(return_class, img_class)
        )
    ):
        # TODO actualize changes in a virtual ImagePlus. Remove this when pyimagej does this innately
        if issubclass(return_class, jpype.JClass("ij.ImagePlus")):
            ij.py.synchronize_ij1_to_ij2(return_value)
        py_img = ij.py.from_java(return_value)

        # HACK
        # Workaround for DataArrays potentially coming back with Java names. Fixed upstream in:
        # https://github.com/imagej/pyimagej/commit/a1861b6c1658d6751fa314650b13411f956549ab
        py_img.name = ij.py.from_java(py_img.name)
        return py_img

    # Not a supported type
    return None


def convert_java_type_to_setting(param_name, param_type, param_class):
    """
    Helper method to convert ImageJ/Java class parameter types to CellProfiler settings

    Parameters
    ----------
    param_name : str, required
        The name of the parameter
    param_type : str, required
        The Java class name describing the parameter type
    param_class: str, required
        One of {input_class} or {output_class}, based on the parameter use

    Returns
    ---------
    One or more Settings of a type appropriate for param_type, named with param_name. Or None if no valid conversion exists.
    """
    type_string = param_type.split()[1]
    img_strings = ("ij.ImagePlus", "net.imagej.Dataset", "net.imagej.ImgPlus")
    if INPUT_CLASS == param_class:
        param_label = param_name
        if type_string == "java.lang.String":
            return Alphanumeric(param_label, "")
        if type_string == "java.lang.Character":
            return Character(param_label, "")
        elif type_string == "java.lang.Integer":
            return Integer(param_label, 0, minval=-(2**31), maxval=((2**31) - 1))
        elif type_string == "java.lang.Long":
            return Integer(param_label, 0, minval=-(2**63), maxval=((2**63) - 1))
        elif type_string == "java.lang.Short":
            return Integer(param_label, 0, minval=-32768, maxval=32767)
        elif type_string == "java.lang.Byte":
            return Integer(param_label, 0, minval=-128, maxval=127)
        elif type_string == "java.lang.Boolean":
            return Boolean(param_label, 0)
        elif type_string == "java.lang.Float":
            return Float(param_label, minval=-(2**31), maxval=((2**31) - 1))
        elif type_string == "java.lang.Double":
            return Float(param_label, minval=-(2**63), maxval=((2**63) - 1))
        elif type_string == "java.io.File":
            param_dir = Directory(f"{param_label} directory", allow_metadata=False)

            def set_directory_fn_app(path):
                dir_choice, custom_path = param_dir.get_parts_from_path(path)
                param_dir.join_parts(dir_choice, custom_path)

            param_file = Filename(
                param_label,
                param_label,
                get_directory_fn=param_dir.get_absolute_path,
                set_directory_fn=set_directory_fn_app,
                browse_msg=f"Choose {param_label} file",
            )
            return (param_dir, param_file)
        elif bool(
            (img_string for img_string in img_strings if type_string == img_string)
        ):
            return ImageSubscriber(param_label)
    elif OUTPUT_CLASS == param_class:
        if bool(
            (img_string for img_string in img_strings if type_string == img_string)
        ):
            return ImageName(
                "[OUTPUT, " + type_string + "] " + param_name,
                param_name,
                doc="""
            You may use this setting to rename the indicated output variable, if desired.
            """,
            )

    return None


def _start_imagej_process():
    """Python script to run when starting a new ImageJ process.

    All commands are initiated by adding a dictionary with a {pyimagej_key_command} entry to the {input_queue}. This
    indicating which supported command should be executed. Some commands may take additional input, which is specified
    in the dictionary with {pyimagej_key_input}.

    Outputs are returned by adding a dictionary to the {output_queue} with the {pyimagej_key_output} key, or
    {pyimagej_key_error} if an error occurred during script execution.

    NB: must be run from the main thread in order to eventually shut down the JVM.

    Supported commands
    ----------
    {pyimagej_cmd_start} : start the pyimagej instance if it's not already running
        inputs: initialization string for imagej.init()
        outputs: either {pyimagej_status_startup_complete} or {pyimagej_status_startup_failed} as appropriate
    {pyimagej_cmd_script_parse} : parse the parameters from an imagej script.
        inputs: script filename
        outputs: dictionary with mappings
            {pyimagej_script_parse_inputs} -> dictionary of input field name/value pairs
            {pyimagej_script_parse_outputs} -> dictionary of output field name/value pairs
    {pyimagej_cmd_script_run} : takes a set of named inputs from CellProfiler and runs the given imagej script
        inputs: dictionary with mappings
            {pyimagej_script_run_file_key} -> script filename
            {pyimagej_script_run_input_key} -> input parameter name/value dictionary
        outputs: dictionary containing output field name/value pairs
    {pyimagej_cmd_exit} : shut down the pyimagej daemon.
        inputs: none
        outputs: {pyimagej_status_shutdown_complete}

    Return values
    ----------
    {pyimagej_status_cmd_unknown} : unrecognized command, no further output is coming
    """

    manager = QueueManager(address=("127.0.0.1", SERVER_PORT), authkey=_SERVER_KEY)
    manager.connect()
    input_queue = manager.input_queue()
    output_queue = manager.output_queue()

    ij = False
    script_service = None
    init_string = None

    # Main daemon loop, polling the input queue
    while True:
        command_dictionary = input_queue.get()
        cmd = command_dictionary[PYIMAGEJ_KEY_COMMAND]
        if cmd == PYIMAGEJ_CMD_START and not ij:
            init_string = command_dictionary[PYIMAGEJ_KEY_INPUT]
            try:
                if init_string:
                    # Attempt to initialize with the given string
                    ij = imagej.init(init_string)
                else:
                    ij = imagej.init()
                    init_string = INIT_LATEST
                if not ij:
                    init_string = None
                    output_queue.put(PYIMAGEJ_STATUS_STARTUP_FAILED)
                else:
                    script_service = ij.script()
                    output_queue.put(PYIMAGEJ_STATUS_STARTUP_COMPLETE)
            except jpype.JException as ex:
                # Initialization failed
                output_queue.put(PYIMAGEJ_STATUS_STARTUP_FAILED)
                jpype.shutdownJVM()
        elif cmd == PYIMAGEJ_CMD_GET_INIT_METHOD:
            output_queue.put({PYIMAGEJ_KEY_OUTPUT: init_string})
        elif cmd == PYIMAGEJ_CMD_SCRIPT_PARSE:
            script_path = command_dictionary[PYIMAGEJ_KEY_INPUT]
            script_file = Path(script_path)
            script_info = script_service.getScript(script_file)
            script_inputs = {}
            script_outputs = {}
            for script_in in script_info.inputs():
                script_inputs[str(script_in.getName())] = str(
                    script_in.getType().toString()
                )
            for script_out in script_info.outputs():
                script_outputs[str(script_out.getName())] = str(
                    script_out.getType().toString()
                )
            output_queue.put(
                {
                    PYIMAGEJ_SCRIPT_PARSE_INPUTS: script_inputs,
                    PYIMAGEJ_SCRIPT_PARSE_OUTPUTS: script_outputs,
                }
            )
        elif cmd == PYIMAGEJ_CMD_SCRIPT_RUN:
            script_path = (command_dictionary[PYIMAGEJ_KEY_INPUT])[
                PYIMAGEJ_SCRIPT_RUN_FILE_KEY
            ]
            script_file = Path(script_path)
            input_map = (command_dictionary[PYIMAGEJ_KEY_INPUT])[
                PYIMAGEJ_SCRIPT_RUN_INPUT_KEY
            ]
            convert_types = (command_dictionary[PYIMAGEJ_KEY_INPUT])[
                PYIMAGEJ_SCRIPT_RUN_CONVERT_IMAGES
            ]
            _preprocess_script_inputs(ij, input_map, convert_types)
            script_out_map = (
                script_service.run(script_file, True, input_map).get().getOutputs()
            )
            output_dict = {}
            for entry in script_out_map.entrySet():
                key = str(entry.getKey())
                value = _convert_java_to_python_type(ij, entry.getValue())
                if value is not None:
                    output_dict[key] = value

            output_queue.put({PYIMAGEJ_KEY_OUTPUT: output_dict})
        elif cmd == PYIMAGEJ_CMD_EXIT:
            break
        else:
            output_queue.put(PYIMAGEJ_STATUS_CMD_UNKNOWN)

    # Shut down the imagej process
    if ij:
        ij.dispose()
        jpype.shutdownJVM()
    output_queue.put(PYIMAGEJ_STATUS_SHUTDOWN_COMPLETE)


def _start_server():
    """
    Start the server that will be used for sending communication between ImageJ
    and CellProfiler.

    NB: this method will permanently block its thread.
    """
    m = QueueManager(address=("", SERVER_PORT), authkey=_SERVER_KEY)
    s = m.get_server()
    s.serve_forever()


def _start_thread(target=None, args=(), name=None, daemon=True):
    """
    Create and start a thread to run a given target

    Parameters
    ----------
    target : runnable
        Same as threading.Thread
    args : list
        Same as threading.Thread
    name : string
        Same as threading.Thread
    daemon : whether or not the thread should be a daemon
        Default True
    """
    thread = threading.Thread(target=target, args=args, name=name)
    thread.daemon = daemon
    thread.start()


def is_server_running(timeout=0.25):
    """
    Helper method to determine if the ImageJ server is up and running.

    Parameters
    ----------
    timeout : number, optional (default 0.25)
        Duration in seconds to wait when connecting to server

    Return values
    ----------
    True if there was a response from the server. False otherwise.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex(("localhost", SERVER_PORT)) == 0


def wait_for_server_startup(timeout=15):
    """
    Helper method that blocks until the timeout value is reached, or the ImageJ
    server becomes available for connection.

    Parameters
    ----------
    timeout : number, optional (default 15)
        Duration in seconds to wait for the server to start

    Errors
    ----------
    RuntimeError
        If timeout is exceeded
    """
    max_attempts = timeout * 4
    current_attempt = 0
    while (not is_server_running(0.01)) and (current_attempt < max_attempts):
        time.sleep(0.25)
        current_attempt += 1
        pass

    if current_attempt >= max_attempts:
        raise RuntimeError(f"ImageJ server failed to start within allotted time.")


def main():
    """
    Start the two pyimagej server components:
    - This will create a new "imagej-server" thread that handles inter-process
      communication
    - The main thread will block in a poll listening for that
      communication, and interacting with the Java ImageJ process.

    Because this runs indefinitely until instructed to shut down,
    this method should be called in a new subprocess.
    """
    multiprocessing.freeze_support()

    _start_thread(target=_start_server, name="imagej-server")

    wait_for_server_startup()

    _start_imagej_process()


if __name__ == "__main__":
    main()
