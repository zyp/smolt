from elftools.elf.elffile import ELFFile

from cpp_symbol_parser.parser import Parser

parser = Parser()

from dataclasses import dataclass
from typing import List

import struct

@dataclass
class Tag:
    addr: int
    fmt: str
    args: List[str]
    loc: str

    def message(self, it):
        args = []
        for arg_type in self.args:
            value = next(it) % (2**32)
            if arg_type == 'float':
                value, = struct.unpack('<f', struct.pack('<I', value))
            elif not 'unsigned' in arg_type and value >= 2**31:
                value -= 2**32
            args.append(value)

        return Message(self, args)

@dataclass
class Message:
    tag: Tag
    args: any

    def format(self):
        return self.tag.fmt.format(*self.args)

def parse_symbol(addr, symbol):
    ast = parser.parse(symbol)

    fmt = ''
    args = []
    loc = ''

    for arg in ast.name.template_args:
        match arg.type.name:
            case 'fmt_v0':
                fmt = bytes(literal.value for literal in arg.values[0].values[0].values).decode()
            case 'loc_v0' if arg.values:
                filename = bytes(literal.value for literal in arg.values[0].values[0].values).decode()
                line = arg.values[1].value
                loc = f'{filename}:{line}'
            case 'args_v0':
                args = [str(t) for t in arg.type.template_args]

    return Tag(addr, fmt, args, loc)

class ELF:
    def __init__(self, filename):
        self.filename = filename
        self.read()

    def read(self):
        elf = ELFFile.load_from_path(self.filename)
        symtab = elf.get_section_by_name('.symtab')

        self._tags = {}

        for sym in symtab.iter_symbols():
            if not sym.name.startswith('_ZN5smolt3tag'):
                continue

            addr = sym.entry.st_value
            self._tags[addr] = parse_symbol(addr, sym.name)

    def refresh(self):
        # TODO: Check mtime
        self.read()

    def tags(self):
        return self._tags.values()

    def tag(self, addr):
        return self._tags.get(addr)
