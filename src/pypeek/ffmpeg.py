import os, sys, zipfile, stat, requests, datetime

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    SELF_DIR = sys._MEIPASS
elif __file__:
    SELF_DIR = os.path.abspath(os.path.dirname(__file__))

PLATFORM_ZIP_FILES = {
    "win32": "https://raw.githubusercontent.com/firatkiral/pypeek/main/data/ffmpeg_bins/win32.zip",
    "darwin": "https://raw.githubusercontent.com/firatkiral/pypeek/main/data/ffmpeg_bins/darwin.zip",
    "linux": "https://raw.githubusercontent.com/firatkiral/pypeek/main/data/ffmpeg_bins/linux.zip",
}

def check_system():
    """Friendly error if there's a problem with the system configuration."""
    if sys.platform not in PLATFORM_ZIP_FILES:
        raise OSError(f"Please implement static_ffmpeg for {sys.platform}")


def get_platform_http_zip():
    """Return the download link for the current platform"""
    check_system()
    return PLATFORM_ZIP_FILES[sys.platform]

def get_platform_dir():
    """Either get the executable or raise an error"""
    check_system()
    return os.path.join(SELF_DIR, "bin", sys.platform)


def download_file(url, local_path):
    """Downloads a file to the give path."""
    # NOTE the stream=True parameter below
    print(f"Downloading {url} -> {local_path}")
    with requests.get(url, stream=True) as req:
        req.raise_for_status()
        with open(local_path, "wb") as file_d:
            for chunk in req.iter_content(chunk_size=8192 * 16):
                # If you have chunk encoded response uncomment if
                # and set chunk_size parameter to None.
                # if chunk:
                # sys.stdout.write(".")
                print(".", end="", flush=True)
                file_d.write(chunk)
            print(f"\nDownload of {url} -> {local_path} completed.\n")
    return local_path

def get_or_fetch_platform_executables_else_raise(fix_permissions=True):
    """Either get the executable or raise an error, internal api"""
    exe_dir = get_platform_dir()
    installed_crumb = os.path.join(exe_dir, "installed.crumb")
    if not os.path.exists(installed_crumb):
        print(f"Installing ffmpeg to {exe_dir}")
        # All zip files store their platform executables in a folder
        # like "win32" or "darwin" or "linux" inside the executable. So root
        # the install one level up from that same directory.
        install_dir = os.path.dirname(exe_dir)
        os.makedirs(exe_dir, exist_ok=True)
        url = get_platform_http_zip()
        local_zip = exe_dir + ".zip"
        download_file(url, local_zip)
        print(f"Extracting {local_zip} -> {install_dir}")
        with zipfile.ZipFile(local_zip, mode="r") as zipf:
            zipf.extractall(install_dir)
        try:
            os.remove(local_zip)
        except OSError as err:
            print(f"{__file__}: Error could not remove {local_zip} because of {err}")
        with open(installed_crumb, "wt") as filed:  # pylint: disable=W1514
            filed.write(f"installed from {url} on {datetime.datetime.now().__str__()}")
    ffmpeg_exe = os.path.join(exe_dir, "ffmpeg")
    ffprobe_exe = os.path.join(exe_dir, "ffprobe")
    if sys.platform == "win32":
        ffmpeg_exe = f"{ffmpeg_exe}.exe"
        ffprobe_exe = f"{ffprobe_exe}.exe"
    for exe in [ffmpeg_exe, ffprobe_exe]:
        if (
            fix_permissions
            and sys.platform != "win32"
            and (not os.access(exe, os.X_OK) or not os.access(exe, os.R_OK))
        ):
            # Set bits for execution and read for all users.
            exe_bits = stat.S_IXOTH | stat.S_IXUSR | stat.S_IXGRP
            read_bits = stat.S_IRUSR | stat.S_IRGRP | stat.S_IXGRP
            os.chmod(exe, exe_bits | read_bits)
            assert os.access(exe, os.X_OK), f"Could not execute {exe}"
            assert os.access(exe, os.R_OK), f"Could not get read bits of {exe}"
    return ffmpeg_exe, ffprobe_exe

def get_ffmpeg():
    os.makedirs(SELF_DIR, exist_ok=True)
    ffmpeg, _ = get_or_fetch_platform_executables_else_raise()
    os.environ["PATH"] = os.pathsep.join([os.path.dirname(ffmpeg), os.environ["PATH"]])
    return ffmpeg