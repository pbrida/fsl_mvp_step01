import sys

if sys.platform == "win32":
    from .tz.win import tzres as tzres
    from .tz.win import tzwin as tzwin
    from .tz.win import tzwinlocal as tzwinlocal
