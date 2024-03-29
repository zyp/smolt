from elftools.elf.elffile import ELFFile

from cpp_symbol_parser.parser import Parser

parser = Parser()

from dataclasses import dataclass
from typing import List

import struct

type_struct_formats = {
    'char': '<b3x',
    'signed char': '<b3x',
    'unsigned char': '<B3x',
    'short': '<h2x',
    'unsigned short': '<H2x',
    'int': '<i',
    'unsigned int': '<I',
    'long': '<l',
    'unsigned long': '<L',
    'long long': '<q',
    'unsigned long long': '<Q',
    'float': '<f',
    'double': '<d',
}

@dataclass
class Tag:
    addr: int
    fmt: str
    args: List[str]
    loc: str

    def message(self, it):
        args = []
        for arg_type in self.args:
            st = struct.Struct(type_struct_formats[arg_type])
            buf = bytearray()
            for _ in range(0, st.size, 4):
                buf.extend((next(it) % 2**32).to_bytes(4, 'little'))
            value, = st.unpack(buf)
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
