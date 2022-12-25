import os, subprocess, platform, static_ffmpeg, shutil

static_ffmpeg.add_paths() # download ffmpeg if necessary

dir_path = os.path.dirname(os.path.realpath(__file__))
desktop_path = os.path.expanduser("~/Desktop")

def win():
    shortcut_name = "Peek"
    icon_path = f"{dir_path}/icon/peek.ico"
    shortcut_path = os.path.join(desktop_path, shortcut_name + ".lnk")

    script = f'''
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
    $Shortcut.TargetPath = "pypeek-gui"
    $Shortcut.IconLocation = "{icon_path}"
    $Shortcut.Save()
    '''
    # script = f'''
    # $WshShell = New-Object -ComObject WScript.Shell
    # $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
    # $Shortcut.TargetPath = "python"
    # $Shortcut.Arguments = "-m pypeek"
    # $Shortcut.IconLocation = "{icon_path}"
    # $Shortcut.WindowStyle = 7
    # $Shortcut.Save()
    # '''
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-Command", script])

def mac():
    script = f'''
        tell application "Terminal"
            if not (exists window 1) then reopen
            do script "pypeek &;" in window 1
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