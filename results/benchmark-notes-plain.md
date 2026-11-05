# Benchmark Results
Date: 25 June 2026

## What I was doing
I built a script (the "harness") that measures how long my pipeline takes
to respond, automatically, many times over, and saves every result.
I ran it two ways: COLD (everything asleep, has to wake up) and
WARM (everything already awake).

---

## COLD TEST (5 runs) - the slow case
When all 4 functions are asleep, they each have to wake up one after
another before the user gets an answer.

Run 1: 20.6s   <- first run is always the slowest (cold cache, etc.)
Run 2: 11.2s
Run 3:  9.9s
Run 4: 11.1s
Run 5:  9.4s

So a cold pipeline takes about 9 to 11 seconds (ignoring the first run).

Things I learned:
- The FIRST run is always much slower than the rest. The first wake-up
  after a long sleep is the worst. I may drop run 1 when reporting
  (waiting for my supervisor to confirm).
- Even the other runs vary a bit (9.4 to 11.2s). That variation is
  exactly why I need to measure many times, not just once.
- The total time the user waits is a couple of seconds MORE than the
  pipeline's own internal timing. That extra bit is the orchestrator
  itself waking up (it also sleeps). Worth mentioning when I write up.

---

## WARM TEST (50 runs) - the fast case
When things are already awake, the answer comes back almost instantly.

Run 1:      11.3s   <- still cold (first request woke everything up)
Runs 2-50:  ~0.06s  <- basically instant once warm

The real warm speed is about 0.06 seconds (60 milliseconds).

A nice extra: I could watch the pipeline "wake up" during the test.
It went from 4 functions asleep -> 3 -> 2 -> 1 as each one woke and
stayed awake to serve the next request. Good clean proof of how
warming works.

Note on the averages: the simple average looks like 0.29s, but that's
misleading because run 1 (11.3s) drags it up. The MIDDLE value (median)
is 0.06s, which is the honest warm number. Good example of why I should
report the median, not just the average.

---

## THE BIG PICTURE (the headline)
COLD pipeline:  ~9-11 seconds
WARM pipeline:  ~0.06 seconds
Difference:     roughly 150 times slower when cold.

That huge gap IS the problem my project is about. It's also the prize:
if my predictor can keep the right functions warm at the right time,
I can turn that ~10-second wait into something close to instant.