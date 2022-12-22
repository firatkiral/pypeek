import os, subprocess, platform, static_ffmpeg, shutil

static_ffmpeg.add_paths() # download ffmpeg if necessary

dir_path = os.path.dirname(os.path.realpath(__file__))

def win():
    shortcut_name = "Peek"
    script_path = r"pypeek-gui"
    icon_path = f"{dir_path}/icon/peek.ico"
    desktop_path = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
    shortcut_path = os.path.join(desktop_path, shortcut_name + ".lnk")

    script = f'''
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
    $Shortcut.TargetPath = "{script_path}"
    $Shortcut.IconLocation = "{icon_path}"
    $Shortcut.Save()
    '''
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-Command", script])

def mac():
    desktop_path = os.path.expanduser("~/Desktop")

    script = f'''
        tell application "Terminal"
            activate
            do script "pypeek; exit;"
        end tell
        '''

    subprocess.run(["osacompile", "-o", f"{desktop_path}/Peek.app", "-e", script])
    shutil.copy(f"{dir_path}/icon/peek.icns", f"{desktop_path}/peek.app/Contents/Resources/applet.icns")

def create_shortcut():
    if platform.system() == 'Windows':
        win()
    elif platform.system() == 'Darwin':
        mac()
    else:
        pass