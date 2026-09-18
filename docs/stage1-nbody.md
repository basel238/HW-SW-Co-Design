# Stage 1 source study: nbody

**Student review status: REQUIRED.** These notes explain the supplied source;
they do not certify that the student has reviewed it or supply new measurements.
Read the functions below and connect them to your own run's evidence before
using the notes in the submission or demonstration.

## Source and purpose

The baseline is `src/baseline/nbody/run_benchmark.py`, copied unchanged from
pyperformance **1.14.0**. `SOURCES.json` records its origin and the SHA-256:
`d1385e816d7cfea361b7915e2cf70138cd6b84f40df8bd5152638851f7bcac2b`.
Run provenance records the actual source and source-tree hashes separately.

It advances a small gravitational system containing the Sun, Jupiter, Saturn,
Uranus, and Neptune. This is a fixed small-system Python benchmark, not a large
particle simulation or an accuracy study of an astronomical integrator. The
source uses Python lists, tuples, dictionaries, floating-point arithmetic, and
the `pyperf` timing/runner library. The numerical kernel does not use NumPy,
BLAS, or a native vector library. Exponentiation is Python's `**` operation;
the file does not import `math`.

## Data and algorithm

`BODIES` maps five names to `(position, velocity, mass)` tuples. Each position
and velocity is a mutable three-element list; mass is a float. `SYSTEM` is a
list of the same five tuples. `PAIRS = combinations(SYSTEM)` stores the ten
unordered pairs. These structures refer to the same underlying position and
velocity lists: they are not independent copies.

`advance(dt, n)` repeats two phases for each timestep:

1. Visit all ten pairs. Compute coordinate differences and
   `mag = dt * (dx*dx + dy*dy + dz*dz)**(-1.5)`. Scale by the two masses and
   update both bodies' velocity lists. Every pair contributes to both bodies.
2. After **all** pair interactions, update each position using its updated
   velocity. Moving positions inside the pair loop would change the algorithm.

The default public call uses `dt = 0.01` and **20,000 timesteps**. It performs
200,000 pair interactions, 1,200,000 velocity-component assignments, and
300,000 position-component assignments, apart from setup and energy reporting.
This velocity-then-position update is a first-order, semi-implicit Euler form.
Floating-point rounding and update order are part of the baseline behavior.

`report_energy()` sums pairwise negative potential energy and each body's
kinetic energy. `bench_nbody()` calls it immediately before and after
`advance()`, but discards the returned energy values; they are not printed or
used to decide whether the run is correct. A timing result therefore does not
establish numerical correctness by itself.

For variable body count `B` and timestep count `T`, advancement costs
`O(T * B^2)` and the two energy evaluations cost `O(B^2)`. Persistent state is
`O(B)` but the materialized pair list is `O(B^2)`. Here `B = 5` is fixed, so
increasing timesteps scales work approximately linearly. The small data set
does not resemble a bandwidth-scale nbody workload.

## State and measurement boundaries

`bench_nbody(loops, reference, iterations)` first calls
`offset_momentum(BODIES[reference])`, then starts `pyperf.perf_counter()` and
times the requested number of energy/advance/energy sequences. The default
reference is `sun`. Momentum setup is outside the function's returned elapsed
time; energy evaluations are inside it.

`offset_momentum()` sums the **current** velocities of all bodies, including
the reference, then assigns a new reference velocity. For the initial state,
whose Sun velocity is zero, this establishes the intended momentum offset.
Repeated calls are not a general physical reset: the function neither restores
initial positions nor adds a correction to the old reference velocity. Preserve
this exact benchmark behavior when comparing implementations.

The module remains loaded across warmups and measured calls in one worker.
Positions and velocities therefore continue to evolve. A fresh worker/import
creates fresh initial state, but another public benchmark call in that worker
does not. `tools/workload.py` makes this policy explicit in its receipt.

The gated perf region encloses whole public calls plus a small driver loop and
timer/control boundary cost. It excludes import and warmup, but includes the
momentum setup that each public call performs. The function's own returned
elapsed time has the narrower boundary described above. Do not divide gated
counts by an unrelated timing interval and call it exact.

Record the actual configured warmup count, calls, iterations, interpreter,
affinity, and state policy from each run. A longer profile can visit later
simulation states than a short timing worker. Check that the hotspot pattern
is consistent before treating the two as interchangeable experiments.

## Expected hotspots and what profiling must establish

Source inspection predicts that `advance()` dominates because it repeats the
pair and position updates 20,000 times. Python-level samples can localize the
distance expression, six velocity updates, position updates, and unpacking.
Those lines combine arithmetic with Python dispatch, list access/mutation,
boxed-float allocation and reference-count handling.

A native perf profile may therefore show interpreter evaluation, float/list
helpers, allocation/deallocation and power implementation costs. A large
interpreter frame is compatible with valid execution of Python code; valid
symbols and plausible call stacks still need verification. The native graph
is the required perf evidence; supplementary Python sampling helps map it
back to source.

The source alone does **not** establish that the program is FPU-bound, that
power dominates elapsed time, or that a low cache-miss rate rules out every
memory stall. A line's sample share does not isolate the exponentiation on
that line. Relate readable native self-costs, Python call/line evidence, and
accepted counter runs before making such claims. Treat proposed expression
rewrites or representation changes as experiments, with correctness and
unprofiled timing checked independently.

## Questions to answer in the demonstration

1. Why are there ten pairs, and why must positions move only after all pairs?
2. Which lists are shared by `BODIES`, `SYSTEM`, and `PAIRS`, and what state
   survives a warmup or another benchmark call?
3. Which work lies inside the benchmark's own timer and which extra work lies
   inside the gated perf region?
4. What evidence would distinguish expensive Python object handling from
   expensive floating-point hardware, and why is one hot source line insufficient?
