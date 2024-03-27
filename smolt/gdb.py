import gdb

from .meta import ELF

class CmdSmolt(gdb.Command):
    def __init__(self):
        super().__init__('smolt', gdb.COMMAND_DATA, gdb.COMPLETE_COMMAND, True)

class CmdSmoltRb(gdb.Command):
    def __init__(self):
        super().__init__('smolt rb', gdb.COMMAND_DATA, gdb.COMPLETE_SYMBOL, False)

    def invoke(self, arg, from_tty):
        args = gdb.string_to_argv(arg)
        if len(args) != 1:
            print('Usage: smolt rb <log buffer>')
            return

        buf = gdb.parse_and_eval(args[0])

        # Get buffer contents from target.
        depth = int(buf.type.template_argument(0))
        write_idx = int(buf['write_idx'])
        tag_idx = int(buf['tag_idx'])
        data = [int(buf['data']['_M_elems'][i]) for i in range(depth)]

        # Rotate buffer so tag_idx is at the beginning.
        data = [*data[tag_idx:], *data[:tag_idx]]

        # Strip any incomplete data at the end.
        if tag_idx != write_idx:
            data = data[:-((tag_idx - write_idx) % depth)]

        elf = ELF(gdb.current_progspace().executable_filename)

        entries = []

        it = iter(data)

        while True:
            try:
                tag_id = next(it)
                if not tag_id:
                    break

                tag = elf.tag(tag_id)
                if tag is None:
                    print(f'Got unknown tag')
                    break

                entries.append(tag.message(it))

            except StopIteration:
                break

        for msg in reversed(entries):
            print(msg.tag.loc, msg.format())

CmdSmolt()
CmdSmoltRb()
