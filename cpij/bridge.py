from pathlib import Path
import multiprocessing as mp
from multiprocessing import Process
from cellprofiler_core.image import Image
from cellprofiler_core.setting.text.alphanumeric.name.image_name import ImageName
from cellprofiler_core.setting.text import Filename, Text, Directory, Alphanumeric, Integer, Float
from cellprofiler_core.setting.subscriber import ImageSubscriber
import atexit
import imagej
import jpype
import skimage.io

"""
Constants for communicating with pyimagej
"""
PYIMAGEJ_KEY_COMMAND = "KEY_COMMAND"  # Matching value indicates what command to execute
PYIMAGEJ_KEY_INPUT = "KEY_INPUT"  # Matching value is command-specific input object
PYIMAGEJ_KEY_OUTPUT = "KEY_OUTPUT"  # Matching value is command-specific output object
PYIMAGEJ_KEY_ERROR = "KEY_OUTPUT"  # Matching value is command-specific output object
PYIMAGEJ_CMD_SCRIPT_PARSE = "COMMAND_SCRIPT_PARAMS"  # Parse a script file's parameters
PYIMAGEJ_SCRIPT_PARSE_INPUTS = "SCRIPT_PARSE_INPUTS"  # Script input dictionary key
PYIMAGEJ_SCRIPT_PARSE_OUTPUTS = "SCRIPT_PARSE_OUTPUTS"  # Script output dictionary key
PYIMAGEJ_CMD_SCRIPT_RUN = "COMMAND_SCRIPT_RUN"  # Run a script
PYIMAGEJ_SCRIPT_RUN_FILE_KEY = "SCRIPT_RUN_FILE_KEY"  # The script filename key
PYIMAGEJ_SCRIPT_RUN_INPUT_KEY = "SCRIPT_RUN_INPUT_KEY"  # The script input dictionary key
PYIMAGEJ_SCRIPT_RUN_CONVERT_IMAGES = "SCRIPT_RUN_CONVERT_IMAGES" # Whether images should be converted or not
PYIMAGEJ_CMD_EXIT = "COMMAND_EXIT"  # Shut down the pyimagej daemon
PYIMAGEJ_STATUS_CMD_UNKNOWN = "STATUS_COMMAND_UNKNOWN"  # Returned when an unknown command is passed to pyimagej
PYIMAGEJ_STATUS_STARTUP_COMPLETE = "STATUS_STARTUP_COMPLETE"  # Returned after initial startup before daemon loop
PYIMAGEJ_STATUS_STARTUP_FAILED = "STATUS_STARTUP_FAILED"  # Returned when imagej.init fails
INIT_LOCAL = "Local"
INIT_ENDPOINT = "Endpoint"
INIT_LATEST = "Latest"
INPUT_CLASS = "INPUT"
OUTPUT_CLASS = "OUTPUT"


init_display_string = None
imagej_process = None  # A subprocess running pyimagej
to_imagej = None  # Queue to pass data to pyimagej
from_imagej = None  # queue to receive data from pyimagej


def preprocess_script_inputs(ij, input_map, convert_images):
    """Helper method to convert pythonic inputs to something that can be handled by ImageJ

    In particular this is necessary for image inputs which won't be auto-converted by Jpype

    Parameters
    ----------
    ij : imagej.init(), required
        ImageJ entry point (from imagej.init())
    input_map:
        map of input names to values
    convert_images:
        boolean indicating if image inputs and outputs should be auto-converted to appropriate numeric types
    """
    for key in input_map:
        if isinstance(input_map[key], Image):
            cp_image = input_map[key].get_image()
            # CellProfiler images are typically stored as floats which can cause unexpected results in ImageJ.
            # By default, we convert to 16-bit int type, unless we're sure it's 8 bit in which case we use that.
            if convert_images:
                if input_map[key].scale==255:
                    cp_image = skimage.img_as_ubyte(cp_image)
                else:
                    cp_image = skimage.img_as_uint(cp_image)
            input_map[key] = ij.py.to_dataset(cp_image)


def convert_java_to_python_type(ij, return_value):
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

    image_classes = (jpype.JClass('ij.ImagePlus'), jpype.JClass('net.imagej.Dataset'), jpype.JClass('net.imagej.ImgPlus'))

    if type_string == "java.lang.String" or type_string == "java.lang.Character":
        return str(return_value)
    elif type_string == "java.lang.Integer" or type_string == "java.lang.Long" or type_string == "java.lang.Short":
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
    elif bool((img_class for img_class in image_classes if issubclass(return_class, img_class))):
        return ij.py.from_java(return_value)

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
            return Integer(param_label, 0, minval=-2 ** 31, maxval=((2 ** 31) - 1))
        elif type_string == "java.lang.Long":
            return Integer(param_label, 0, minval=-2 ** 63, maxval=((2 ** 63) - 1))
        elif type_string == "java.lang.Short":
            return Integer(param_label, 0, minval=-32768, maxval=32767)
        elif type_string == "java.lang.Byte":
            return Integer(param_label, 0, minval=-128, maxval=127)
        elif type_string == "java.lang.Boolean":
            return Boolean(param_label, 0)
        elif type_string == "java.lang.Float":
            return Float(param_label, minval=-2 ** 31, maxval=((2 ** 31) - 1))
        elif type_string == "java.lang.Double":
            return Float(param_label, minval=-2 ** 63, maxval=((2 ** 63) - 1))
        elif type_string == "java.io.File":
            param_dir = Directory(f'{param_label} directory', allow_metadata=False)
            def set_directory_fn_app(path):
                dir_choice, custom_path = param_dir.get_parts_from_path(path)
                param_dir.join_parts(dir_choice, custom_path)
            param_file = Filename(
                param_label,
                param_label,
                get_directory_fn=param_dir.get_absolute_path,
                set_directory_fn=set_directory_fn_app,
                browse_msg=f'Choose {param_label} file'
                )
            return (param_dir, param_file)
        elif bool((img_string for img_string in img_strings if type_string == img_string)):
            return ImageSubscriber(param_label)
    elif OUTPUT_CLASS == param_class:
        if bool((img_string for img_string in img_strings if type_string == img_string)):
            return ImageName("[OUTPUT, " + type_string + "] " + param_name, param_name, doc=
            """
            You may use this setting to rename the indicated output variable, if desired.
            """
                             )

    return None


def start_imagej_process(input_queue, output_queue, init_string):
    """Python script to run when starting a new ImageJ process.
    
    All commands are initiated by adding a dictionary with a {pyimagej_key_command} entry to the {input_queue}. This
    indicating which supported command should be executed. Some commands may take additional input, which is specified
    in the dictionary with {pyimagej_key_input}.

    Outputs are returned by adding a dictionary to the {output_queue} with the {pyimagej_key_output} key, or
    {pyimagej_key_error} if an error occurred during script execution.
    
    Supported commands
    ----------
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
        outputs: none
    
    Return values
    ----------
    {pyimagej_status_cmd_unknown} : unrecognized command, no further output is coming

    Parameters
    ----------
    input_queue : multiprocessing.Queue, required
        This Queue will be polled for input commands to run through ImageJ
    output_queue : multiprocessing.Queue, required
        This Queue will be filled with outputs to return to CellProfiler
    init_string : str, optional
        This can be a path to a local ImageJ installation, or an initialization string per imagej.init(),
        e.g. sc.fiji:fiji:2.1.0
    """

    ij = False

    try:
        if init_string:
            # Attempt to initialize with the given string
            ij = imagej.init(init_string)
        else:
            ij = imagej.init()
    except jpype.JException as ex:
        # Initialization failed
        output_queue.put(PYIMAGEJ_STATUS_STARTUP_FAILED)
        apype.shutdownJVM()
        return

    script_service = ij.script()

    # Signify output is complete
    output_queue.put(PYIMAGEJ_STATUS_STARTUP_COMPLETE)

    # Main daemon loop, polling the input queue
    while True:
        command_dictionary = input_queue.get()
        cmd = command_dictionary[PYIMAGEJ_KEY_COMMAND]
        if cmd == PYIMAGEJ_CMD_SCRIPT_PARSE:
            script_path = command_dictionary[PYIMAGEJ_KEY_INPUT]
            script_file = Path(script_path)
            script_info = script_service.getScript(script_file)
            script_inputs = {}
            script_outputs = {}
            for script_in in script_info.inputs():
                script_inputs[str(script_in.getName())] = str(script_in.getType().toString())
            for script_out in script_info.outputs():
                script_outputs[str(script_out.getName())] = str(script_out.getType().toString())
            output_queue.put({PYIMAGEJ_SCRIPT_PARSE_INPUTS: script_inputs,
                              PYIMAGEJ_SCRIPT_PARSE_OUTPUTS: script_outputs})
        elif cmd == PYIMAGEJ_CMD_SCRIPT_RUN:
            script_path = (command_dictionary[PYIMAGEJ_KEY_INPUT])[PYIMAGEJ_SCRIPT_RUN_FILE_KEY]
            script_file = Path(script_path)
            input_map = (command_dictionary[PYIMAGEJ_KEY_INPUT])[PYIMAGEJ_SCRIPT_RUN_INPUT_KEY]
            convert_types = (command_dictionary[PYIMAGEJ_KEY_INPUT])[PYIMAGEJ_SCRIPT_RUN_CONVERT_IMAGES]
            preprocess_script_inputs(ij, input_map, convert_types)
            script_out_map = script_service.run(script_file, True, input_map).get().getOutputs()
            output_dict = {}
            for entry in script_out_map.entrySet():
                key = str(entry.getKey())
                value = convert_java_to_python_type(ij, entry.getValue())
                if value is not None:
                    output_dict[key] = value

            output_queue.put({PYIMAGEJ_KEY_OUTPUT: output_dict})
        elif cmd == PYIMAGEJ_CMD_EXIT:
            break
        else:
            output_queue.put({PYIMAGEJ_KEY_ERROR: PYIMAGEJ_STATUS_CMD_UNKNOWN})

    # Shut down the daemon
    ij.getContext().dispose()
    jpype.shutdownJVM()


def close_pyimagej():
    """
    Close the pyimagej daemon thread
    """
    global imagej_process, to_imagej
    if imagej_process is not None:
        to_imagej.put({PYIMAGEJ_KEY_COMMAND: PYIMAGEJ_CMD_EXIT})


def init_pyimagej(init_string):
    """
    Start the pyimagej daemon thread if it isn't already running.
    """
    global imagej_process, to_imagej, from_imagej
    if imagej_process is None:
        to_imagej = mp.Queue()
        from_imagej = mp.Queue()
        # TODO if needed we could set daemon=True
        imagej_process = Process(target=start_imagej_process, name="PyImageJ Daemon",
                                        args=(to_imagej, from_imagej, init_string,))
        imagej_process.start()
        result = from_imagej.get()
        if result == PYIMAGEJ_STATUS_STARTUP_FAILED:
            imagej_process = None
            return False
        else:
            atexit.register(close_pyimagej)  # TODO is there a more CP-ish way to do this?
            return True

if __name__ == '__main__':
    mp.freeze_support()
