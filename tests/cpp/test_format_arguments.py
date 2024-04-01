import pytest
import string

from util import CompilerError

@pytest.fixture
def build(target_compile):
    def _exec(type):
        source = string.Template('''
            #include <smolt.h>
            #include <cstdint>

            smolt::logger logger { smolt::transport::itm {} };

            void test($type value) {
                logger.log<"value: {}">(value);
            }
        ''').substitute(type = type)

        target_compile(source)

    return _exec

@pytest.mark.parametrize('type', [
    'uint8_t',
    'uint16_t',
    'uint32_t',
    'uint64_t',
    'int8_t',
    'int16_t',
    'int32_t',
    'int64_t',
    'float',
    'double',
    'std::span<uint8_t>',
    'std::span<uint8_t, 16>',
    'std::span<uint32_t>',
    'std::span<uint32_t, 16>',
    'std::span<uint64_t>',
    'std::span<uint64_t, 16>',
    'std::string_view',
])
def test_format_argument_type(build, type):
    build(type = type)

    # TODO: Validate the generated tag in the ELF.

@pytest.mark.parametrize('type', [
    'void*',
])
def test_format_argument_unsupported_type(build, type):
    with pytest.raises(CompilerError):
        build(type = type)
