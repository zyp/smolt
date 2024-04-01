import pytest
import subprocess
import sys

from util import CompilerError, CompilerWarning

from smolt import include_path

@pytest.fixture
def host_compile(tmp_path_factory):
    def _exec(source):
        __tracebackhide__ = True

        compiler = [
            'g++',
            '-std=c++20',
            f'-I{include_path}',
            '-fdiagnostics-color',
            '-pedantic',
            '-Wall',
            '-Wextra',
        ]

        path = tmp_path_factory.mktemp('build')
        source_file = path / 'test.cpp'
        executable_file = path / 'test'

        with open(source_file, 'w') as f:
            f.write(source)
    
        res = subprocess.run([*compiler, source_file, '-o', executable_file], capture_output = True, encoding = 'utf-8')
        sys.stderr.write(res.stderr)

        if res.returncode != 0:
            raise CompilerError()

        if 'warning:' in res.stderr:
            raise CompilerWarning()

        return executable_file

    return _exec

@pytest.fixture
def target_compile(tmp_path_factory):
    def _exec(source):
        __tracebackhide__ = True

        assert include_path

        compiler = [
            'arm-none-eabi-g++',
            '-std=c++20',
            f'-I{include_path}',
            '-mcpu=cortex-m4',
            '-O2',
            '-fdiagnostics-color',
            '-pedantic',
            '-Wall',
            '-Wextra',
        ]

        path = tmp_path_factory.mktemp('build')
        source_file = path / 'test.cpp'
        object_file = path / 'test.o'

        with open(source_file, 'w') as f:
            f.write(source)
    
        res = subprocess.run([*compiler, '-c', source_file, '-o', object_file], capture_output = True, encoding = 'utf-8')
        sys.stderr.write(res.stderr)

        if res.returncode != 0:
            raise CompilerError()

        if 'warning:' in res.stderr:
            raise CompilerWarning()

    return _exec
