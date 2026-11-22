#!/usr/bin/env python3
"""Read-only DRM state: which connectors/CRTCs exist, which are enabled, and whether any of them
owns a framebuffer - the question ffmpeg's kmsgrab answers with "No usable planes found".

    sudo python3 drm-state.py /dev/dri/card0      # the master-capable node
    python3 drm-state.py /dev/dri/renderD128      # render node: resources only

Why this exists: journal 40.19 recorded that every screenshot taken while RE4 presents is black with
a cursor.  The operator's explanation is that the panel is powered off (`cat
/sys/class/drm/card0-DP-1/dpms` -> Off), and that is also why a capture with no game running is pure
black (one distinct colour) while an earlier capture of the same desktop had 11 654.  A kernel-side
grab needs an enabled CRTC with a framebuffer, so this prints exactly that, from the kernel, without
touching any compositor configuration.
"""
import ctypes as C
import os
import sys

DRM = C.CDLL("libdrm.so.2")
for _f in ("drmModeGetResources", "drmModeGetCrtc", "drmModeGetConnector"):
    getattr(DRM, _f).restype = C.c_void_p


def ptr(x):
    if isinstance(x, int):
        return x
    return getattr(x, "value", 0) or 0


class Res(C.Structure):
    _fields_ = [("min_x", C.c_int), ("min_y", C.c_int), ("max_x", C.c_int), ("max_y", C.c_int),
                ("count_connectors", C.c_int), ("connector_id_ptr", C.POINTER(C.c_uint32)),
                ("count_encoders", C.c_int), ("encoder_id_ptr", C.POINTER(C.c_uint32)),
                ("count_crtcs", C.c_int), ("crtc_id_ptr", C.POINTER(C.c_uint32)),
                ("count_fbs", C.c_int), ("fb_id_ptr", C.POINTER(C.c_uint32))]


class Crtc(C.Structure):
    _fields_ = [("crtc_id", C.c_uint32), ("x", C.c_uint32), ("y", C.c_uint32),
                ("width", C.c_uint32), ("height", C.c_uint32), ("mode_valid", C.c_uint32),
                ("mode", C.c_ubyte * 68), ("ref_count", C.c_uint32), ("fb_id", C.c_uint32),
                ("gamma_size", C.c_uint32)]


class Conn(C.Structure):
    _fields_ = [("connector_id", C.c_uint32), ("type", C.c_uint32), ("type_id", C.c_uint32),
                ("connection", C.c_uint32), ("encoder_id", C.c_uint32),
                ("count_encoders", C.c_uint32), ("encoders_ptr", C.POINTER(C.c_uint32)),
                ("count_modes", C.c_uint32), ("modes_ptr", C.c_void_p)]


CONN_TYPE = {3: "Unknown", 6: "VGA", 10: "DisplayPort", 11: "HDMI", 14: "eDP", 17: "DSI", 22: "Writeback"}


def main(path):
    fd = os.open(path, os.O_RDWR if os.access(path, os.W_OK) else os.O_RDONLY)
    r = ptr(DRM.drmModeGetResources(fd))
    if not r:
        print(f"{path}: drmModeGetResources failed - needs the DRM master node (/dev/dri/cardN)")
        return 1
    res = Res.from_address(r)
    print(f"{path}: connectors={res.count_connectors} crtcs={res.count_crtcs} fbs={res.count_fbs}")
    if res.count_fbs == 0:
        print("  no framebuffer is allocated in the kernel at all: nothing can be captured")
    for i in range(res.count_crtcs if res.crtc_id_ptr else 0):
        cp = ptr(DRM.drmModeGetCrtc(fd, res.crtc_id_ptr[i]))
        if not cp:
            continue
        c = Crtc.from_address(cp)
        print(f"  crtc {c.crtc_id}: enabled={'yes' if c.mode_valid else 'no '} fb={c.fb_id} "
              f"{c.width}x{c.height}")
    for i in range(res.count_connectors if res.connector_id_ptr else 0):
        cp = ptr(DRM.drmModeGetConnector(fd, res.connector_id_ptr[i]))
        if not cp:
            continue
        cc = Conn.from_address(cp)
        state = {0: "unknown", 1: "connected", 2: "disconnected"}.get(cc.connection, cc.connection)
        print(f"  connector {cc.connector_id} {CONN_TYPE.get(cc.type, cc.type)}{cc.type_id}: "
              f"{state} encoder={cc.encoder_id}")
    print("  capture needs: one enabled crtc with fb != 0, or a writeback connector")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/dev/dri/card0"))
