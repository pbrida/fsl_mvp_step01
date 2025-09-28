from .__meta__ import __version__ as __version__
from .__meta__ import __version_info__ as __version_info__
from .core import Markdown as Markdown
from .core import markdown as markdown
from .core import markdownFromFile as markdownFromFile
from .extensions import Extension as Extension

__all__ = ["Markdown", "markdown", "markdownFromFile"]
