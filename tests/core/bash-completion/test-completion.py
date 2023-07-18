import os
import asyncio
import contextlib
import re
import sys


class Pty:
    def __init__(self):
        self._loop = asyncio.get_running_loop()
        self._parent, self.child = os.openpty()

    def close(self):
        self.close_parent()
        self.close_child()

    def close_parent(self):
        if self._parent is not None:
            os.close(self._parent)
            self._parent = None

    def close_child(self):
        if self.child is not None:
            os.close(self.child)
            self.child = None

    async def read(self, size):
        fut = self._loop.create_future()
        def reader():
            try:
                data = os.read(self._parent, size)
            except Exception as e:
                fut.set_exception(e)
            else:
                fut.set_result(data)
            finally:
                self._loop.remove_reader(self._parent)
        self._loop.add_reader(self._parent, reader)
        return await fut

    async def write(self, data):
        fut = self._loop.create_future()
        def writer():
            try:
                written = os.write(self._parent, data)
            except Exception as e:
                fut.set_exception(e)
            else:
                fut.set_result(written)
            finally:
                self._loop.remove_writer(self._parent)

        self._loop.add_writer(self._parent, writer)
        return await fut


class TermReader:
    def __init__(self, pty):
        self._pty = pty
        self._buf = bytearray()

    async def expect(self, search):
        while True:
            if m := re.search(search, self._buf):
                print(f"Found {search}. Eaten: {self._buf[:m.endpos]}")
                del self._buf[:m.endpos]
                return True
            try:
                self._buf.extend(await asyncio.wait_for(self._pty.read(4096), timeout=2))
            except asyncio.TimeoutError:
                print(f"Did not find {search}. Available: {self._buf}")
                return False


class Shell:
    @staticmethod
    def prepare_tty():
        os.setsid()
        # Force being controlled by terminal
        tmp_fd = os.open(os.ttyname(0), os.O_RDWR)
        os.close(tmp_fd)

    @staticmethod
    async def create(pty, init):
        environ = os.environ.copy()
        p = await asyncio.create_subprocess_exec(
            '/bin/bash', '--init-file', init, '-i',
            stdout=pty.child, stdin=pty.child, stderr=pty.child,
            close_fds=True,
            preexec_fn=Shell.prepare_tty,
            env=environ)
        pty.close_child()
        return Shell(p)

    def __init__(self, process):
        self._process = process

    async def kill(self):
        self._process.terminate()
        await asyncio.sleep(1)
        self._process.kill()

    async def aclose(self):
        killer = asyncio.create_task(self.kill())
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._process.wait(), timeout=1.5)
        killer.cancel()


async def run(init, executable):
    with contextlib.closing(Pty()) as pty:
        async with contextlib.aclosing(await Shell.create(pty, init)):
            reader = TermReader(pty)
            assert await reader.expect(rb'prompt[$] ')
            print(await pty.write(f'{executable} -b \t\t'.encode('ascii')))
            assert await reader.expect(b'\a') # Bell
            assert await reader.expect(rb'counterrevolutionary  *electroencephalogram  *uncharacteristically')


asyncio.run(run(sys.argv[1], sys.argv[2]))
