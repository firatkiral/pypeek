import os, sys, subprocess, zipfile

PLATFORM_ZIP_FILES = {
    "win32": "win32.zip",
    "darwin": "darwin.zip",
    "linux": "linux.zip",
}

def get_ffmpeg():
    zip_file = f"data/ffmpeg/{PLATFORM_ZIP_FILES[sys.platform]}"
    install_dir = "dist/ffmpeg"
    os.makedirs(install_dir, exist_ok=True)
    with zipfile.ZipFile(zip_file, mode="r") as zipf:
        zipf.extractall(install_dir)

def deploy():
    get_ffmpeg()
    subprocess.call(['pyinstaller', 'pypeek.spec', '-y'])
    


if __name__ == '__main__':
    deploy()