"""The stub of the ERiC library that the tests of the binding, the worker and the service run against.

ericapi_stub.c implements the functions of libericapi.so that steuerbote binds, written from the
ERiC API reference. It is built with the C compiler on first use. The CI builds it beforehand with all
warnings as errors and names it in STEUERBOTE_ERIC_STUB, so a missing compiler fails the run there
instead of skipping the tests.
"""

import atexit
import ctypes
import functools
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).with_name("ericapi_stub.c")
PREBUILT = "STEUERBOTE_ERIC_STUB"
COMPILER_FLAGS = ("-std=c11", "-Wall", "-Wextra", "-Werror", "-O1", "-shared", "-fPIC")
WRONG_PIN = "falsch-123"
"""The PIN the stub refuses with 610201106, as ERiC does for a wrong PIN."""


@functools.cache
def library() -> Path:
	"""The built stub: the prebuilt one the CI names, or one compiled now."""
	prebuilt = os.environ.get(PREBUILT)
	if prebuilt:
		path = Path(prebuilt)
		if not path.is_file():
			raise FileNotFoundError(f"{PREBUILT} names {path}, which does not exist")
		return path
	compiler = shutil.which("cc")
	if compiler is None:
		raise unittest.SkipTest(
			f"no C compiler (cc) to build the ERiC stub from {SOURCE.name}: install one or set {PREBUILT}"
		)
	directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-stub-"))
	atexit.register(shutil.rmtree, directory, ignore_errors=True)
	output = directory / "libericapi.so"
	command = [compiler, *COMPILER_FLAGS, "-o", str(output), str(SOURCE)]
	subprocess.run(command, check=True, capture_output=True)  # noqa: S603 - the compiler found on PATH
	return output


def install(root: Path, years: tuple[int, ...] = (2026,)) -> Path:
	"""A lib directory laid out like ERiC's: the stub, the plugin commonData and a plugin per year."""
	lib = root / "lib"
	plugins = lib / "plugins2"
	plugins.mkdir(parents=True)
	shutil.copyfile(library(), lib / "libericapi.so")
	(plugins / "libcommonData.so").write_bytes(b"")
	for year in years:
		(plugins / f"libcheckUStVA_{year}.so").write_bytes(b"")
	return lib


class Controls:
	"""The stub's own functions: reset, what it received, and its counters of buffers and certificates."""

	def __init__(self, lib_dir: Path):
		self._stub = ctypes.CDLL(str(lib_dir / "libericapi.so"), mode=ctypes.RTLD_GLOBAL)
		self._stub.stub_recorded.restype = ctypes.c_char_p
		self._stub.stub_recorded.argtypes = (ctypes.c_char_p,)
		self._stub.stub_pdf_size.restype = ctypes.c_uint32

	def reset(self) -> None:
		self._stub.stub_reset()

	def recorded(self, key: str) -> str | None:
		value = self._stub.stub_recorded(key.encode())
		return None if value is None else value.decode()

	def fail_buffer(self, after: int = 0) -> None:
		"""Let EricRueckgabepufferErzeugen fail once, after this many buffers were created."""
		self._stub.stub_fail_buffer_after(after)

	@property
	def live_buffers(self) -> int:
		return self._stub.stub_live_buffers()

	@property
	def open_certificates(self) -> int:
		return self._stub.stub_open_certificates()

	@property
	def initialised(self) -> bool:
		return bool(self._stub.stub_initialised())

	@property
	def pdf_size(self) -> int:
		return self._stub.stub_pdf_size()
