# smolt

Small minimal-overhead logging toolkit.

## Introduction

Would you like to do printf-style logging on a microcontroller without the firmware needing to spend time doing string formatting?
Format and print floating point values without pulling in large and slow formatting routines?
Have logging be fast enough you can use it from interrupt handlers without the additional latency becoming an issue?
Leave the format strings out of the flash entirely?

Smolt is a small header-only C++ library with no dependencies beyond a C++20 compiler with STL. All use of STL is `constexpr`.

When you make a log call, the format string and other metadata is given a tag ID, so the only data that needs to be sent or stored is the tag ID and the format arguments.
The host side utilities can then use the tag ID to look up all the metadata from the .elf file and handle string formatting.

## Features
- Formatting of values on the host with [Python's format string syntax](https://docs.python.org/3/library/string.html#formatstrings).
  - Currently supports integral and floating point types up to 32 bit.
- Optional metadata attached to messages.
  - Source location.
- Pluggable transports.
  - `transport::itm`
    - Streaming logging over ARM ITM over SWO or parallel trace.
  - `transport::ringbuffer`
    - Logging to internal ringbuffer for later readout.
  - `transport::blackhole`
    - Dummy transport. Allows leaving logging calls sprinkled through the code without them needing to do anything.
  - Custom transports only have to implement `log_tag(uint32_t)` and `log_value(uint32_t)`.
- CLI utility
  - Receive and format log messages over ITM from [Orbuculum](https://github.com/orbcode/orbuculum) and other sources that relay ITM messages over TCP.
- GDB plugin
  - Read out and format log messages from a ringbuffer in target memory.

## TODO
- Support for more argument types:
  - `uint64_t`, `int64_t`, `double`
  - `std::string_view`
  - `std::span`
    - With a custom formatter that allows e.g. formatting buffers as hex bytes.
- More transports:
  - `transport::tee`
    - Allows feeding a single logger into multiple transports.
- More metadata that can be attached to messages:
  - Severity (info, warning, error, etc…).
- Documentation.
- Tests.

## Usage

### Example firmware
[Try it in Compiler Explorer](https://godbolt.org/z/WPP3a81Mn).

```cpp
#include <limits>
#include <numbers>

#include <smolt.h>
using namespace smolt::info;

constexpr smolt::logger logger { smolt::transport::itm {} };

//smolt::transport::ringbuffer<256> log_buf;
//constexpr smolt::logger logger { log_buf };

//constexpr smolt::logger logger { smolt::transport::blackhole {} };

int main() {
    logger.log<"uint32_t max: {}", loc()>(std::numeric_limits<uint32_t>::max());
    logger.log<"uint32_t min: {}", loc()>(std::numeric_limits<uint32_t>::min());
    logger.log<"int32_t max: {}", loc()>(std::numeric_limits<int32_t>::max());
    logger.log<"int32_t min: {}", loc()>(std::numeric_limits<int32_t>::min());
    logger.log<"pi: {}", loc()>(std::numbers::pi_v<float>);

    while (true) {}
}
```

### CLI usage
```console
% smolt cflags
-I/Users/zyp/.pyenv/versions/3.12.0/lib/python3.12/site-packages/smolt/include
% smolt list example.elf
08000285: example.cpp:19 "pi: {}", float
08000281: example.cpp:18 "int32_t min: {}", long
08000279: example.cpp:16 "uint32_t min: {}", unsigned long
08000275: example.cpp:15 "uint32_t max: {}", unsigned long
0800027d: example.cpp:17 "int32_t max: {}", long
% smolt itm example.elf 
23:26:12 example.cpp:15 uint32_t max: 4294967295
23:26:12 example.cpp:16 uint32_t min: 0
23:26:12 example.cpp:17 int32_t max: 2147483647
23:26:12 example.cpp:18 int32_t min: -2147483648
23:26:12 example.cpp:19 pi: 3.1415927410125732
```

### GDB usage
```
(gdb) python import smolt.gdb

(gdb) run

The program being debugged has been started already.
Start it from the beginning? (y or n) y

Starting program: example.elf 
^C
Program received signal SIGINT, Interrupt.
main () at example.cpp:21
21	    while (true) {}

(gdb) smolt rb log_buf

example.cpp:15 uint32_t max: 4294967295
example.cpp:16 uint32_t min: 0
example.cpp:17 int32_t max: 2147483647
example.cpp:18 int32_t min: -2147483648
example.cpp:19 pi: 3.1415927410125732
(gdb) 
```

## How does it work?

A tag is effectively a dummy function that will never be called and therefore doesn't need to do anything, so it'll only contain a single return instruction and therefore only take up 2-4 bytes of flash.
The reason it exists is so that we can use its address as a tag ID.

By making a function template for a tag, the compiler will emit these functions on demand whenever we ask for its address.
Whatever template arguments are passed to the function template becomes part of the function identifier and therefore goes into the mangled symbol name.

This means that the source can easily create tags with arbitrary metadata attached, and the host side tools can easily retrieve the metadata by finding and decoding the tag symbols from the resulting .elf.
