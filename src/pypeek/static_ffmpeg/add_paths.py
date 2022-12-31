"""
add_paths() Adds ffmpeg and ffprobe to the path, overriding any system ffmpeg/ffprobe.
"""


import os
from .run import get_or_fetch_platform_executables_else_raise


def add_paths() -> None:
    """Add the ffmpeg executable to the path"""
    ffmpeg, _ = get_or_fetch_platform_executables_else_raise()
    os.environ["PATH"] = os.pathsep.join([os.path.dirname(ffmpeg), os.environ["PATH"]])
