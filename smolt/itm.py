import time

from .meta import ELF

def start_itm(file, itm_channel, itm_addr):
    # Don't include pyorb before we need it to avoid requiring liborb when not used.
    from pyorb import Orb, swMsg

    elf = ELF(file)

    orb = Orb(itm_addr)

    tag = None
    args = []

    while True:
        packet = orb.rx()

        match packet:
            case swMsg() if packet.srcAddr == itm_channel:
                tag = elf.tag(packet.value)
                if tag is None:
                    print(f'Got unknown tag: {packet.value:08x}')

                elif len(args) < len(tag.args):
                    print(f'Insufficient arguments for tag: {tag.fmt:08x}, {args}')

                else:
                    ts = time.strftime('%H:%M:%S')
                    m = tag.message(iter(args))
                    print(ts, tag.loc, m.format())

                args = []

            case swMsg() if packet.srcAddr == itm_channel + 1:
                args.insert(0, packet.value)

            case _:
                continue
