import os, subprocess, platform, sys, shutil

if getattr(sys, 'frozen', False):
    dir_path = os.path.abspath(os.path.dirname(sys.executable))
elif __file__:
    dir_path = os.path.abspath(os.path.dirname(__file__))
desktop_path = os.path.expanduser("~/Desktop")

def win():
    shortcut_name = "peek"
    icon_path = f"{dir_path}/icon/peek.ico"
    shortcut_path = os.path.join(desktop_path, shortcut_name + ".lnk")

    script = f'''
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
    $Shortcut.TargetPath = "pypeek-gui.exe"
    $Shortcut.IconLocation = "{icon_path}"
    $Shortcut.Save()
    '''
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-Command", script])

def mac():
    script = f'''
        tell application "Terminal"
            if not (exists window 1) then reopen
            do script "pypeek-gui" in window 1
        end tell 
        '''

    subprocess.run(["osacompile", "-o", f"{desktop_path}/peek.app", "-e", script])
    shutil.copy(f"{dir_path}/icon/peek.icns", f"{desktop_path}/peek.app/Contents/Resources/applet.icns")

def create_shortcut():
    if sys.platform == 'win32':
        win()
    elif sys.platform == 'darwin':
        mac()
    else:
        print(f"{sys.platform} is not supported yet.")
        pass