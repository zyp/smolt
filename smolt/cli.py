import click
import pathlib
import shlex

from .meta import ELF

from .itm import start_itm

@click.group(context_settings = {'show_default': True})
@click.version_option()
def cli():
    pass

@cli.command()
@click.argument('elf', type=click.Path(exists = True, dir_okay = False, path_type = pathlib.Path))
# TODO: JSON option?
def list(elf):
    '''Read ELF file and list available tags.'''

    for tag in ELF(elf).tags():
        print(f'{tag.addr:08x}: {tag.loc} "{tag.fmt}", {", ".join(tag.args)}')

@cli.command()
@click.argument('elf', type=click.Path(exists = True, dir_okay = False, path_type = pathlib.Path))
@click.option('--itm-channel', type = int, default = 24, help = 'First ITM channel to use.')
@click.option('--hostname', default = 'localhost', help = 'Hostname to connect to.')
@click.option('--port', type = int, default = 3443, help = 'Port to connect to.')
# TODO: Include/exclude timestamp
# TODO: Include/exclude source location
def itm(elf, itm_channel, hostname, port):
    '''Receive log messages over ITM.'''

    start_itm(elf, itm_channel, (hostname, port))

@cli.command()
def cflags():
    '''Get header include path, pkg-config style.'''

    path = pathlib.Path(__file__).parent.absolute() / 'include'

    # TODO: This should probably be handled better, I don't expect it'll work on windows.
    print(shlex.quote(f'-I{path}'))
