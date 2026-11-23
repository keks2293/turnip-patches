#!/usr/bin/env python3
"""Check what interface each `--varyings` arm really compiles to, before its counters are read.

Reproduce:
  scripts/check-varyings-arms.py | tee results/synthetics/varyings/interface-check.txt

Queue 34 asks what unit `PERF_VPC_SP_COMPONENTS` (VPC 10) and `PERF_SP_EXPORT_VPC_TRANS` (SP 48)
have; the arm is `tests/vpc-attrbuf.c --varyings=N` with the shader pairs of
`tests/gen-varyings-spv.sh`.  Those counters mean nothing unless arm N really has an interface of N
vec4, and two of the three ways this repository built the arm were wrong in a way only the
disassembler shows (journal 42.1): a plain sum of varyings is moved into the vertex shader by
`nir_opt_varyings` - one fetch whatever N is (`can_move_alu_across_interp`,
nir_opt_varyings.c:3738-3795, run at a budget of UINT32_MAX from tu_shader.cc:3878) - and `fract()`
blocks that move but tells the same pass the value lies in [0, 1), which packs part of the
interface into 16-bit slots.  Both failures leave the pipeline running and the counters reading
plausible numbers.

What is read, from the driver's own disassembly of the built probe (`IR3_SHADER_DEBUG=vs,fs`):

  * the FS's input list, `rD.c (VARYING_SLOT_VARk slot=S cm=COMPASK,il=M,b=B)` - the VPC location
    ir3 thinks the fragment shader reads, which is what `pack_inlocs` rewrote into the compiled FS
    (ir3_compiler_nir.c:5274-5290; the print is ir3_shader.c:1266).  An arm is N slots at
    il = 0, 4, 8 ... 4(N-1), each with compmask f and the bary flag;
  * the VS's output list, where ir3 prints `hr` for a half-precision register and `r` otherwise
    (ir3_shader.c:1259) - the column that shows 16-bit packing, which the FS's own line cannot;
  * `SP_VS_OUTPUT_CNTL.OUT` = N + 1 and `VPC_VS_CNTL.STRIDE_IN_VPC` = 4N + 4, expected and not
    read: POSITION is counted too (a6xx.xml:3677-3680, tu_pipeline.cc:1092) and the stride is
    `linkage.max_loc` (tu_pipeline.cc:926-931).  Reading the registers needs FD_RD_DUMP=full plus
    `cffdump -q VPC_VS_CNTL` (docs/howto-measure.md).

One column deliberately absent: the `half`/`full` numbers on the `; FRAG prog ...` line.  They look
like varying counts and are not - they are `max_half_reg + 1` and `max_reg + 1`, register pressure
(ir3_shader.c:1284) - and reading them as varyings is what made three correct arms look broken for
a minute on 23.11.  Nor can the bary.f offsets be scanned: `(rpt3)` stands for three repeated
instructions, so a scan under-counts.

An arm passes on N VS VAR outputs, none half, POSITION present, and the same N read by the FS at
il = 0, 4, ... 4(N-1) with compmask f and bary set.  `--arms` takes a comma-separated list,
`--seconds` how long each arm renders (1 s is enough: the shaders compile at pipeline creation,
before the draw loop).  No hw counter is sampled here.
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys

# The --varyings arms, and the rig's own default pair: `attrbuf` asks for no --varyings at all, and
# is sixteen vec4 wide only since journal 42.1 corrected the form of its fragment shader.
ARMS = ("attrbuf", 1, 2, 4, 8, 16)
WIDTH = {"attrbuf": 16}


def sections(text, want):
    """The native-code listing of the named stage(s) in one IR3_SHADER_DEBUG dump."""
    out = []
    for chunk in text.split("Native code for unnamed ")[1:]:
        name, _, body = chunk.partition(" shader")
        if name in want:
            out.append(body.split("MESA: info: Native code")[0])
    return out


def read_arm(probe, arm, seconds, env):
    """One run of the rig, with its shaders disassembled.  `arm` is N or the name `attrbuf`."""
    n = WIDTH.get(arm, arm)
    argv = [probe, f"--seconds={seconds}"]
    if arm != "attrbuf":
        argv.append(f"--varyings={n}")
    run = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=300)
    dump = run.stdout + run.stderr
    if "hash " not in dump:
        return {"n": n, "error": (dump.strip().splitlines() or ["the probe printed nothing"])[-1]}

    fs = "\n".join(sections(dump, {"FRAG"}))
    vs = "\n".join(sections(dump, {"VERT"}))
    if not fs or not vs:
        return {"n": n,
                "error": "no FRAG/VERT native code in the dump (MESA_SHADER_CACHE_DISABLE?)"}

    fs_in = {}
    for m in re.finditer(r"\((VARYING_SLOT_VAR\d+) slot=\d+ cm=([0-9a-f]+),il=(\d+),b=(\d)\)", fs):
        fs_in[m.group(1)] = (m.group(2), int(m.group(3)), int(m.group(4)))
    # `h?r`, not `hr?`: ir3 prints "hr" for a half-precision output register and "r" otherwise.
    vs_out = re.findall(r"\b(h?r)\d+\.\w \((VARYING_SLOT_VAR\d+)\)", vs)
    vs_pos = "VARYING_SLOT_POS" in vs
    ils = sorted({il for _, il, _ in fs_in.values()})

    return {
        "arm": arm,
        "n": n,
        "fps": next((l.split()[1] for l in dump.splitlines() if l.startswith("fps ")), "?"),
        "vs_out": len(vs_out),
        "vs_half": sum(1 for reg, _ in vs_out if reg == "hr"),
        "vs_pos": vs_pos,
        "fs_in": len(fs_in),
        "fs_cm": "/".join(sorted({cm for cm, _, _ in fs_in.values()})) or "-",
        "fs_bary": sum(1 for _, _, b in fs_in.values() if b),
        "ils": ils,
        "out": n + 1,
        "stride": 4 * n + 4,
        "ok_inloc": set(ils) == {4 * i for i in range(n)},
        "ok_comp": bool(fs_in) and all(cm == "f" and b == 1 for cm, _, b in fs_in.values()),
        "ok_vs": len(vs_out) == n and not any(reg == "hr" for reg, _ in vs_out) and vs_pos,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", default="../build/vpc-attrbuf")
    ap.add_argument("--arms", default=",".join(str(a) for a in ARMS))
    ap.add_argument("--seconds", default="1")
    args = ap.parse_args()

    env = dict(os.environ)
    env["IR3_SHADER_DEBUG"] = "vs,fs"
    # Without this the check silently finds nothing: a shader that comes out of Mesa's disk shader
    # cache is never compiled, so the disassembler has nothing to print.  Observed 23.11 - the
    # first run of a rebuilt arm printed its shaders and every run after it printed nothing, and
    # "no FRAG native code" reads like a broken arm rather than a cache hit
    # (src/util/disk_cache_os.c:1099).
    env["MESA_SHADER_CACHE_DISABLE"] = "true"
    env.setdefault("VK_DRIVER_FILES",
                   os.path.join(os.path.dirname(args.probe), "out", "freedreno_icd.json"))

    print("# What interface each --varyings arm compiles to, read from the driver's disassembly")
    print("# regenerate: scripts/check-varyings-arms.py | tee "
          "results/synthetics/varyings/interface-check.txt")
    with open(args.probe, "rb") as fh:
        probe_sha = hashlib.sha256(fh.read()).hexdigest()[:12]
    print("# probe:      %s sha256=%s; one 1 s run per arm with IR3_SHADER_DEBUG=vs,fs and"
          % (args.probe, probe_sha))
    print("#               MESA_SHADER_CACHE_DISABLE=true (a cached pipeline is never compiled and")
    print("#               so never disassembled). The debug flag does not perturb codegen")
    print("#               (ir3_compiler.h:379-382). No hw counter is sampled here. The shader pairs")
    print("#               are compiled into the probe (tests/varyings_spv.h), so the hash above is")
    print("#               also the identity of the interface being read: a probe built from a")
    print("#               FS_REDUCE=plain or =fract header is a different binary.")
    print("# read:       the FS's input list (the VPC location pack_inlocs gave each varying,")
    print("#               ir3_compiler_nir.c:5274-5290, printed at ir3_shader.c:1266) and the VS's")
    print("#               output list, where `hr` would mean a 16-bit slot (ir3_shader.c:1259).")
    print("# expect:     N VAR outputs from the VS, none half, plus POSITION; the same N read by")
    print("#               the FS at il = 0,4,...,4(N-1) with compmask f and bary=1; and")
    print("#               SP_VS_OUTPUT_CNTL.OUT = N+1, VPC_VS_CNTL.STRIDE_IN_VPC = 4N+4, derived")
    print("#               from N here (tu_pipeline.cc:1092, :926-931) rather than read back.")
    print("# why it matters: a plain sum of varyings is one of the operations nir_opt_varyings moves")
    print("#               out of the FS and into the VS, which leaves a running pipeline whose")
    print("#               interface is one vec4 whatever N is - journal 42.1, and")
    print("#               results/synthetics/varyings/negative-controls.txt for the shape of it.")
    print("")
    print("%-9s %-7s %-12s %-12s %-10s %-16s %-8s %-8s %s"
          % ("arm", "fps", "VS outputs", "FS reads", "FS comp", "FS inloc", "expect", "expect",
             "verdict"))
    print("%-9s %-7s %-12s %-12s %-10s %-16s %-8s %-8s %s"
          % ("(N)", "", "VAR (half)", "VAR (bary)", "mask", "of the slots", "OUT", "stride", ""))
    print("-" * 105)
    bad = 0
    for a in args.arms.split(","):
        arm = a if a in WIDTH else int(a)
        r = read_arm(args.probe, arm, args.seconds, env)
        if "error" in r:
            print("%-5s  %s" % (arm, r["error"]))
            bad += 1
            continue
        verdict = ("ok" if (r["ok_inloc"] and r["ok_comp"] and r["ok_vs"] and r["fs_in"] == r["n"])
                   else "NOT ok")
        if verdict != "ok":
            bad += 1
        inloc = "0..%d by 4" % r["ils"][-1] if (r["ils"] and r["ok_inloc"]) else str(r["ils"])
        print("%-9s %-7s %-12s %-12s %-10s %-16s %-8s %-8s %s"
              % (r["arm"], r["fps"], "%d (%d)" % (r["vs_out"], r["vs_half"]),
                 "%d (%d)" % (r["fs_in"], r["fs_bary"]), r["fs_cm"], inloc,
                 r["out"], r["stride"], verdict))
        if verdict != "ok":
            print("        expected %d VAR outputs (none half) plus POSITION, and the same %d read"
                  " at" % (r["n"], r["n"]))
            print("        il = 0,4,...,%d with compmask f and bary=1; read il %s"
                  % (4 * (r["n"] - 1), r["ils"]))
    print("")
    print("arms that do not build the interface they ask for: %d%s"
          % (bad, "" if bad == 0 else "   - do not sample hw counters for those arms"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
