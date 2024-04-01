import pytest
import string

@pytest.fixture
def build(target_compile):
    def _exec(logger_statement):
        source = string.Template('''
            #include <smolt.h>

            $logger_statement

            void test(int value) {
                logger.log<"value: {}">(value);
            }
        ''').substitute(logger_statement = logger_statement)

        target_compile(source)

    return _exec

def test_transport_itm(build):
    build('''
        constexpr smolt::logger logger { smolt::transport::itm {} };
    ''')

def test_transport_itm_custom(build):
    build('''
        constexpr smolt::logger logger { smolt::transport::itm { 16 } };
    ''')

def test_transport_ringbuffer(build):
    build('''
        smolt::transport::ringbuffer<256> log_buf {};
        constexpr smolt::logger logger { log_buf };
    ''')

def test_transport_blackhole(build):
    build('''
        constexpr smolt::logger logger { smolt::transport::blackhole {} };
    ''')
