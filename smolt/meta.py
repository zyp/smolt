from elftools.elf.elffile import ELFFile

from cpp_symbol_parser.parser import Parser
from cpp_symbol_parser.ast import Name

from dataclasses import dataclass
from typing import List

import struct
import warnings

class TagWarning(UserWarning):
    pass

parser = Parser()

namespace_smolt_type = Name.from_string('smolt::type')
namespace_smolt_meta = Name.from_string('smolt::meta')

class ElementFormatter:
    def __init__(self, data):
        self.data = data
    def __format__(self, format_spec):
        element_spec, sep = format_spec.split('|', 1) if '|' in format_spec else (format_spec, ', ')
        return sep.join(format(element, element_spec) for element in self.data)

def type_struct_format(type):
    name = type.name
    size = type.template_args[0].value if type.template_args else None

    return {
        ('b', None): '?', # bool
        ('s', 8): 'b',    # int8_t
        ('u', 8): 'B',    # uint8_t
        ('s', 16): 'h',   # int16_t
        ('u', 16): 'H',   # uint16_t
        ('s', 32): 'l',   # int32_t
        ('u', 32): 'L',   # uint32_t
        ('s', 64): 'q',   # int64_t
        ('u', 64): 'Q',   # uint64_t
        ('f', 32): 'f',   # float
        ('f', 64): 'd',   # double
    }[name, size]

def get_arg(type, it):
    assert type in namespace_smolt_type
    if type.name == 'span':
        size = type.template_args[1].value
        if size == 0xffffffff:
            size = next(it) % 2**32
        st = struct.Struct(f'<{size}' + type_struct_format(type.template_args[0]))
        buf = bytearray()
        for _ in range(0, st.size, 4):
            buf.extend((next(it) % 2**32).to_bytes(4, 'little'))
        values = st.unpack(buf[:st.size])
        return ElementFormatter(values)
    elif type.name == 'string':
        assert type.template_args[0].template_args[0].value == 8
        size = next(it) % 2**32
        buf = bytearray()
        for _ in range(0, size, 4):
            buf.extend((next(it) % 2**32).to_bytes(4, 'little'))
        return buf[:size].decode('utf-8')
    else:
        st = struct.Struct('<' + type_struct_format(type))
        buf = bytearray()
        for _ in range(0, st.size, 4):
            buf.extend((next(it) % 2**32).to_bytes(4, 'little'))
        value, = st.unpack(buf[:st.size])
        return value

@dataclass(frozen = True)
class Message:
    tag: 'Tag'
    args: any

    def format(self):
        return self.tag.fmt.format(*self.args)

@dataclass(frozen = True)
class Tag:
    addr: int
    fmt: str
    args: List[str]
    loc: str

    def message(self, it):
        return Message(self, [get_arg(type, it) for type in self.args])

    @classmethod
    def from_symbol(cls, addr, symbol):
        ast = parser.parse(symbol)

        fmt = ''
        args = []
        loc = ''

        for arg in ast.name.template_args:
            if arg.type not in namespace_smolt_meta:
                warnings.warn(f'Tag {addr or 0:#010x}: {arg.type!s} not in smolt::meta.', TagWarning)

            match arg.type.name:
                case 'fmt_v0':
                    fmt = bytes(literal.value for literal in arg.values[0].values[0].values).decode()
                case 'loc_v0' if arg.values:
                    filename = bytes(literal.value for literal in arg.values[0].values[0].values).decode()
                    line = arg.values[1].value
                    loc = f'{filename}:{line}'
                case 'args_v0':
                    args = arg.type.template_args
                case _:
                    warnings.warn(f'Tag {addr or 0:#010x}: {arg.type!s} not recognized.', TagWarning)

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
            self._tags[addr] = Tag.from_symbol(addr, sym.name)

    def refresh(self):
        # TODO: Check mtime
        self.read()

    def tags(self):
        return self._tags.values()

    def tag(self, addr):
        return self._tags.get(addr)
