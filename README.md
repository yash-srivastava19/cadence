# cadence
Finding new solutions using LLMs(not RL)

- new solutions in Math/CS
- as functions/small scripts that can be auto-evaluated.
- restricting it to python.
- the auto-eval results are scalar that we can optimize for.
- any problem we encounter, we'll take inspiration from the paper.

### worklog
18/05/2025: 
worked on researching what kind of problems exists that fit the description, and laid down the structure(and boilerplate) for the project, named it cadence. Some of the interesting problems I found out were:

1. root finding.
2. prime factorization.  
3. inverse of a matrix.
4. fft optimization.
5. minimum makesplan scheduling with precedence.
6. rectangle packing.
7. collatz conjecture iteration count.
8. digital root calculation.

Will try to find more that fits this description, and work on one file at a time. We have the foundations laid down, just need to fill in an run experiments.

19/05/2025:
Worked on basic versions of all the db, eval, llm, sampler(not evolve because it will be based on problem). Used SQLite for DB, and apply_diff uses `re`. The work is going on nice, and now would like to continue and run them in a pipeline.