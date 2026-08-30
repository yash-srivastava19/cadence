# What to improve

`Cache.get` decides what stays in a fixed-size cache and what gets thrown
out. Right now it is least-recently-used: whatever was touched most recently
is kept.

The score is the fraction of requests that were already cached.

## What you may change

Only the code between the `CADENCE:BEGIN` and `CADENCE:END` markers. The
class must keep the name `Cache`, take `capacity` in its constructor, and
expose `get(key) -> bool` that returns whether the key was already held.

## What you may not change

The workload, the capacity, or how the score is computed. Do not import
anything that is not in the standard library, and do not read the trace ahead
of time -- a real cache does not know what is coming.

## Worth knowing

The traffic is not uniform. A small set of keys is asked for constantly, and
every so often something walks a large range of cold keys once and never
returns to them.
