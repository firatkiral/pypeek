import os, subprocess, platform, static_ffmpeg

static_ffmpeg.add_paths() # download ffmpeg if necessary

dir_path = os.path.dirname(os.path.realpath(__file__))

# The path to the script file
script_path = r"pypeek"

# The name of the shortcut
shortcut_name = "Peek"

# The path to the icon file
icon_path = f"{dir_path}/icon/peek.ico"

def win():
    # The directory where the shortcut should be created
    desktop_path = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')

    # The path to the shortcut file
    shortcut_path = os.path.join(desktop_path, shortcut_name + ".lnk")

    # Create a shortcut to the script using powershell
    script = f'''
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
    $Shortcut.TargetPath = "{script_path}"
    $Shortcut.IconLocation = "{icon_path}"
    $Shortcut.Save()
    '''
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-Command", script])

def mac():
    # The directory where the shortcut should be created
    desktop_path = os.path.expanduser("~/Desktop")

    # Create a symbolic link to the script
    link_path = os.path.join(desktop_path, shortcut_name)
    subprocess.run(["ln", "-s", script_path, link_path])

    # Set the icon for the symbolic link
    script = f'''
        tell application "Finder"
            set theFile to POSIX file "{link_path}"
            set theIcon to POSIX file "{icon_path}"
            tell folder (the container of theFile)
                set theIcon of theFile to theIcon
            end tell
        end tell
    '''
    subprocess.run(["osascript", "-e", script])


def main():
    if platform.system() == 'Windows':
        win()
    elif platform.system() == 'Darwin':
        mac()
    else:
        pass