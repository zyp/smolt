import pytest
import subprocess
import string

@pytest.fixture
def build_and_run(host_compile):
    def _exec(main_body):
        source = string.Template('''
            #include <smolt.h>
            #include <limits>
            #include <numbers>
            #include <iostream>
            using namespace std::literals;

            struct transport_stdout {
                void log_tag(uint32_t) const {
                    std::cout << std::endl;
                }

                void log_value(uint32_t value) const {
                    std::cout << value << " ";
                }
            };

            [[maybe_unused]]
            constexpr smolt::logger logger { transport_stdout {} };

            int main() {
                $main_body
            }
        ''').substitute(main_body = main_body)

        executable = host_compile(source)

        res = subprocess.run([executable], capture_output = True, encoding = 'utf-8')

        assert res.returncode == 0
        
        *lines, last = res.stdout.split('\n')
        assert last == ''

        return [[int(n) for n in reversed(line.split())] for line in lines]
    
    return _exec

def test_serialize_none(build_and_run):
    assert build_and_run('') == []

def test_serialize_empty(build_and_run):
    assert build_and_run('logger.log<"">();') == [[]]

def test_serialize_bool(build_and_run):
    assert build_and_run('''
        logger.log<"{} {}">(true, false);
    ''') == [
        [1, 0],
    ]

def test_serialize_unsigned(build_and_run):
    assert build_and_run('''
        logger.log<"{}">(std::numeric_limits<uint8_t>::max());
        logger.log<"{}">(std::numeric_limits<uint16_t>::max());
        logger.log<"{}">(std::numeric_limits<uint32_t>::max());
        logger.log<"{}">(std::numeric_limits<uint64_t>::max());
    ''') == [
        [0xff],
        [0xffff],
        [0xffffffff],
        [0xffffffff, 0xffffffff],
    ]

def test_serialize_signed(build_and_run):
    assert build_and_run('''
        logger.log<"{}">(std::numeric_limits<int8_t>::min());
        logger.log<"{}">(std::numeric_limits<int16_t>::min());
        logger.log<"{}">(std::numeric_limits<int32_t>::min());
        logger.log<"{}">(std::numeric_limits<int64_t>::min());
    ''') == [
        [0xffffff80],
        [0xffff8000],
        [0x80000000],
        [0x00000000, 0x80000000],
    ]

def test_serialize_float(build_and_run):
    assert build_and_run('''
        logger.log<"">(std::numbers::pi_v<float>);
    ''') == [
        [0x40490fdb],
    ]

def test_serialize_double(build_and_run):
    assert build_and_run('''
        logger.log<"">(std::numbers::pi_v<double>);
    ''') == [
        [0x54442d18, 0x400921fb],
    ]

def test_serialize_span_u8(build_and_run):
    assert build_and_run('''
        uint8_t data[] = {1, 2, 3, 4, 5};
        logger.log<"{}">(std::span(data));
    ''') == [
        [0x04030201, 0x05],
    ]

def test_serialize_span_u16(build_and_run):
    assert build_and_run('''
        uint16_t data[] = {0x1234, 0x5678, 0x9abc};
        logger.log<"{}">(std::span(data));
    ''') == [
        [0x56781234, 0x9abc],
    ]

def test_serialize_span_float(build_and_run):
    assert build_and_run('''
        float data[] = {std::numbers::pi_v<float>, std::numbers::e_v<float>};
        logger.log<"{}">(std::span(data));
    ''') == [
        [0x40490fdb, 0x402df854],
    ]

def test_serialize_string(build_and_run):
    assert build_and_run('''
        logger.log<"{}">("abcde"sv);
    ''') == [
        [5, 0x64636261, 0x65],
    ]
