# Peek - Screen Recorder and Screenshot with Annotation

Cross platform screen recorder with an easy to use interface and annotation features written in Python and PySide6.

Inspired by [Peek](https://github.com/phw/peek).

<br/>

![Peek recording itself](https://raw.githubusercontent.com/firatkiral/pypeek/main/data/peek-recording-itself.gif)

<br/>

A developer, designer, or a student, you may need to record or capture your screen to create tutorials, report bugs, provide technical support or simply reflect on your own work and progress. And if you have different operating systems on your different machines, it would be great if you could use the same tool on all of them. That's why I created Peek.

Peek is a simple screen recorder that allows you to record your screen as gif or mp4, capture a screenshot as jpg, and annotate your recordings with drawing, text, arrows, and highlights.

Annotation tool is very useful when you want to highlight a specific area or draw attention to a specific part of your recording. You can add text, arrows or shapes to your recording. Range slider allows you to trim your recording to a desired length. You can create a complete recording with annotation without leaving the app.

![Peek is excited](https://raw.githubusercontent.com/firatkiral/pypeek/main/data/peek-too-excited.gif)

## Features

- Record your screen as gif or mp4
- Capture a screenshot as jpg or png
- Record a selected area or the whole screen
- Annotation features like drawing, text, arrows, and highlights
- Delay recording start with a countdown
- Limit recording to a fixed time

<br/>

[Blog post](https://kiral.net/peek-simplify-screen-recordings/)

<br/>

## Download The App:

[Apple Store](https://apps.apple.com/us/app/peek-screen-recorder/id1670786300)

[Microsoft Store](https://apps.microsoft.com/store/detail/XP8CD3D3Q50MS2)

<br/>


## Install in Python:

### Requirements:

- Python 3.10 or later

- Ffmpeg [Optional], it will be downloaded if not found in system path.

- Windows, MacOS, Ubuntu on Xorg ([How to switch to Xorg](https://itsfoss.com/switch-xorg-wayland/))

*Need help for Ubuntu **Wayland** support. If you are interested, please create a pull request or open an issue.*

#### Known Issues:

- On Ubuntu (on Xorg), if you get *"qt.qpa.plugin: Could not load the Qt platform plugin "xcb"..."* error, install the following packages:

```console
sudo apt install libxcb-*
```

<br/>

### Intallation:

```console
pip install pypeek
```

### Usage:

```console
pypeek
```

### Create a desktop shortcut:
Make sure you run the pypeek command at least once before creating a shortcut.

```console
pypeek --shortcut
```

### Import as a module:

```python
import pypeek

pypeek.show()
```

### Run as a module:

```console
python -m pypeek
```

### Update:

```console
pip install --upgrade pypeek
```

### Uninstall:

```console
pip uninstall pypeek
```

<br/>

## License
Peek Copyright © 2023

Peek is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Peek is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Peek. If not, see <https://www.gnu.org/licenses/>.