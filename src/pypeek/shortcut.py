import os, subprocess, platform, static_ffmpeg, shutil

static_ffmpeg.add_paths() # download ffmpeg if necessary

dir_path = os.path.dirname(os.path.realpath(__file__))

# The name of the shortcut
shortcut_name = "Peek"

def win():
    # The path to the script file
    script_path = r"pypeek"

    # The path to the icon file
    icon_path = f"{dir_path}/icon/peek.ico"

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

    # # Save the script to a file
    # script_path = f"{dir_path}/pypeek.command"
    # with open( script_path, 'w') as f:
    #     f.write('#!/bin/bash\n')
    #     f.write('pypeek\n')
    
    # # Make the script executable
    # subprocess.run(["chmod", "+x", script_path])

    # # The path to the icon file
    # icon_path = f"{dir_path}/icon/peek.icns"

    

    # # Create a symbolic link to the script
    # link_path = os.path.join(desktop_path, shortcut_name)
    # subprocess.run(["ln", "-s", script_path, link_path])

    # Set the icon for the symbolic link
    script = f'''
tell application "Terminal"
    activate
    do script "pypeek;"
end tell
'''

    subprocess.run(["osacompile", "-o", f"{desktop_path}/peek.app", "-e", script])
    shutil.copy(f"{dir_path}/icon/peek.icns", f"{desktop_path}/peek.app/Contents/Resources/applet.icns")


def main():
    if platform.system() == 'Windows':
        win()
    elif platform.system() == 'Darwin':
        mac()
    else:
        pass