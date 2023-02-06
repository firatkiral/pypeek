import os, sys, subprocess, zipfile

def get_ffmpeg():
    zip_file = f"data/ffmpeg/{sys.platform}.zip"
    install_dir = "dist/ffmpeg"
    os.makedirs(install_dir, exist_ok=True)
    with zipfile.ZipFile(zip_file, mode="r") as zipf:
        zipf.extractall(install_dir)

def deploy():
    get_ffmpeg()
    subprocess.call(['pyinstaller', 'peek.spec', '-y'])
    

if __name__ == '__main__':
    deploy()