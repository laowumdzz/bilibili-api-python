"""
IVITools

A Simple IVI file manager & toolbox.

BY Nemo2011 <yimoxia@outlook.com>

Licensed under the GNU General Public License v3+.
"""

__author__ = "Nemo2011 <yimoxia@outlook.com>"
__license__ = "GPLv3+"

import sys
import warnings

from .download import download_interactive_video
from .extract import extract_ivi
from .touch import touch_ivi


def run_args(command: str, args: list[str]):
    if command == "help":
        pass
    elif command == "extract":
        extract_ivi(args[0], args[1])
    elif command == "touch":
        touch_ivi(args[0])
    elif command == "download":
        download_interactive_video(args[0], args[1])
    elif command == "play":
        try:
            import PyQt6
        except ImportError:
            warnings.warn(
                "IVITools Built-in Player require PyQt6 but IVITools can't find it. \nYou can install it by `pip3 install PyQt6`. "
            )
            return
        from .player import main, prepopen

        if len(args) == 0:
            main()
        else:
            prepopen(args[0])
    else:
        raise ValueError("Command not found. Use `ivitools help` for helps. ")


def main():
    if len(sys.argv) == 1:
        return
    try:
        args = sys.argv
        run_args(args[1], args[2:])
    except Exception:
        pass


if __name__ == "__main__":
    main()
