# Python sampling profile

Whole fixed-work driver process: imports, in-process warmup, benchmark calls and receipt writing. NOT perf-gated.

Separate statistical Python profile; not timing or a PMU measurement.

Inspect python-sampled.svg and python-sampled.folded. Widths count samples, not function calls or nanoseconds.

Warmup/startup samples have not been filtered out. Native perf has a different sampling scope.
