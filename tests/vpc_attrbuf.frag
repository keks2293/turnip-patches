#version 450

/* Fragment half of the VPC attribute-buffer probe (tests/vpc-attrbuf.c, journal 40.35).
 *
 * It reads all sixteen varyings, and each of them twice as a factor of its own multiply: reading an
 * input is not enough to keep it on the interface, because `nir_opt_varyings` moves the add that
 * used it up into the VS and leaves one packed fetch behind (see main() below, and journal 42.1,
 * which found the probe carrying one vec4 for exactly that reason).
 *
 * uLoop is a specialization constant, so the same SPIR-V serves both regimes:
 * uLoop = 0 leaves the fragment side almost free (the vertex tract is then the limiter,
 * which is what the arms are compared in), and uLoop > 0 puts ALU work behind the
 * varyings, which is the regime where a vertex-side buffer would be expected to matter
 * differently: the consumer drains slowly instead of quickly.  The same binary in both
 * arms also means the comparison cannot be a shader difference.
 */

layout(constant_id = 0) const uint uLoop = 0u;

layout(location = 0)  in vec4 v0;
layout(location = 1)  in vec4 v1;
layout(location = 2)  in vec4 v2;
layout(location = 3)  in vec4 v3;
layout(location = 4)  in vec4 v4;
layout(location = 5)  in vec4 v5;
layout(location = 6)  in vec4 v6;
layout(location = 7)  in vec4 v7;
layout(location = 8)  in vec4 v8;
layout(location = 9)  in vec4 v9;
layout(location = 10) in vec4 v10;
layout(location = 11) in vec4 v11;
layout(location = 12) in vec4 v12;
layout(location = 13) in vec4 v13;
layout(location = 14) in vec4 v14;
layout(location = 15) in vec4 v15;

layout(location = 0) out vec4 fragColor;

void main()
{
   /* Every input is multiplied by itself before anything combines it, so that each one needs a value
    * at its own point of use.  This has to be said out loud because a plain sum does not: a chain of
    * adds is one of the operations `nir_opt_varyings` moves from the FS into the VS
    * (can_move_alu_across_interp(), nir/nir_opt_varyings.c:3738-3795, with an unlimited budget here
    * - tu_shader.cc:3878), and the interface then collapses to one vec4 that carries the sum.  That
    * is what this file did until journal 42.1 read its own disassembly: `inputs:
    * VARYING_SLOT_VAR0` only, so the arms of journal 40.35 measured an interface one vec4 wide, not
    * sixteen.  The multiply is not moved, which the interface sweep of tests/gen-varyings-spv.sh
    * (same form, `v * v`) verifies arm by arm in results/synthetics/varyings/interface-check.txt. */
   vec4 a = v0 * v0 + v1 * v1 + v2 * v2 + v3 * v3;
   vec4 b = v4 * v4 + v5 * v5 + v6 * v6 + v7 * v7;
   vec4 c = v8 * v8 + v9 * v9 + v10 * v10 + v11 * v11;
   vec4 d = v12 * v12 + v13 * v13 + v14 * v14 + v15 * v15;

   vec4 acc = a + b + c + d;
   for (uint i = 0u; i < uLoop; ++i)
      acc = fract(acc * 1.0009) + acc * 0.5;

   fragColor = fract(acc);
}
