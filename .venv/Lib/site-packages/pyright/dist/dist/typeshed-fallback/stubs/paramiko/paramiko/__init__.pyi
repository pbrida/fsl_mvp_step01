from typing import Final

from paramiko import util as util
from paramiko.agent import Agent as Agent
from paramiko.agent import AgentKey as AgentKey
from paramiko.channel import Channel as Channel
from paramiko.channel import ChannelFile as ChannelFile
from paramiko.client import (
    AutoAddPolicy as AutoAddPolicy,
)
from paramiko.client import (
    MissingHostKeyPolicy as MissingHostKeyPolicy,
)
from paramiko.client import (
    RejectPolicy as RejectPolicy,
)
from paramiko.client import (
    SSHClient as SSHClient,
)
from paramiko.client import (
    WarningPolicy as WarningPolicy,
)
from paramiko.common import io_sleep as io_sleep
from paramiko.config import SSHConfig as SSHConfig
from paramiko.config import SSHConfigDict as SSHConfigDict
from paramiko.ecdsakey import ECDSAKey as ECDSAKey
from paramiko.ed25519key import Ed25519Key as Ed25519Key
from paramiko.file import BufferedFile as BufferedFile
from paramiko.hostkeys import HostKeys as HostKeys
from paramiko.message import Message as Message
from paramiko.pkey import PKey as PKey
from paramiko.proxy import ProxyCommand as ProxyCommand
from paramiko.rsakey import RSAKey as RSAKey
from paramiko.server import ServerInterface as ServerInterface
from paramiko.server import SubsystemHandler as SubsystemHandler
from paramiko.sftp import SFTPError as SFTPError
from paramiko.sftp_attr import SFTPAttributes as SFTPAttributes
from paramiko.sftp_client import SFTP as SFTP
from paramiko.sftp_client import SFTPClient as SFTPClient
from paramiko.sftp_file import SFTPFile as SFTPFile
from paramiko.sftp_handle import SFTPHandle as SFTPHandle
from paramiko.sftp_server import SFTPServer as SFTPServer
from paramiko.sftp_si import SFTPServerInterface as SFTPServerInterface
from paramiko.ssh_exception import (
    AuthenticationException as AuthenticationException,
)
from paramiko.ssh_exception import (
    BadAuthenticationType as BadAuthenticationType,
)
from paramiko.ssh_exception import (
    BadHostKeyException as BadHostKeyException,
)
from paramiko.ssh_exception import (
    ChannelException as ChannelException,
)
from paramiko.ssh_exception import (
    ConfigParseError as ConfigParseError,
)
from paramiko.ssh_exception import (
    CouldNotCanonicalize as CouldNotCanonicalize,
)
from paramiko.ssh_exception import (
    PasswordRequiredException as PasswordRequiredException,
)
from paramiko.ssh_exception import (
    ProxyCommandFailure as ProxyCommandFailure,
)
from paramiko.ssh_exception import (
    SSHException as SSHException,
)
from paramiko.transport import SecurityOptions as SecurityOptions
from paramiko.transport import Transport as Transport

__version__: Final[str]
__author__: Final[str]
__license__: Final[str]
key_classes: list[type[PKey]]
