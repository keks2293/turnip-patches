"""Stub for the register module meson generates from a6xx.xml into the build directory
(which this checkout does not have).

`freedreno_dev_info.py` does `from a6xx import *`, and `freedreno_devices.py` then only
*stores* `A6XXRegs.REG_*` in its regtables - it never needs a real encoding.  Two things
make the proxy more than a dummy:

* `__all__` has to be explicit: `from a6xx import *` asks the module for the list of names
  it exports, and a module-level `__getattr__` alone is not iterable.
* every distinct register name must stringify/`int()` to a *distinct* value, because
  `A6xxGPUInfo.__init__` de-duplicates regtables by `int(offset)` and raises
  "duplicate raw magic reg" otherwise.  A constant 0 makes every register the same one.
"""

__all__ = ["A6XXRegs", "A7XXRegs", "A8XXRegs", "CP_REG_UNPACK_SHORT"]

_IDS = {}


def _uid(name):
    if name not in _IDS:
        _IDS[name] = len(_IDS) + 1
    return _IDS[name]


class _Any:
    def __init__(self, name):
        self.name = name

    def __getattr__(self, item):
        return _Any(self.name + "." + item)

    # Some regtables write REG_X+1 or REG_X|FLAG.  Keeping the expression in the name keeps
    # the derived register a distinct one for the duplicate check.
    def __add__(self, other):
        return _Any(f"{self.name}+{other}")

    __radd__ = __add__

    def __or__(self, other):
        return _Any(f"{self.name}|{other}")

    __ror__ = __or__

    def __lshift__(self, other):
        return _Any(f"{self.name}<<{other}")

    def __and__(self, other):
        return _Any(f"{self.name}&{other}")

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name

    def __int__(self):
        return _uid(self.name)

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self is other


A6XXRegs = _Any("A6XXRegs")
A7XXRegs = _Any("A7XXRegs")
A8XXRegs = _Any("A8XXRegs")
CP_REG_UNPACK_SHORT = _Any("CP_REG_UNPACK_SHORT")
