# When should a decision model refuse to recommend?

CWM is a Python research prototype that connects uncertain decisions to evidence,
stakeholder preferences and an audit trail. It is not a language model and is not
validated for allocating public resources.

## Run an actual refusal

Requires Git and Python 3.10+. No external Python packages required.

```bash
git clone https://github.com/webcixonline-spec/collective-wisdom-model.git
cd collective-wisdom-model
python3 tools/demo_abstention.py
```

The script invokes the real engine for two intended uses. Both must refuse to
recommend with the bundled example. Exit code 2 from the engine means refusal;
the wrapper returns 0 when both expected refusals occur. Output from the engine
is currently in Italian. `Raccomandazione NON emessa` means recommendation withheld.
The script uses a temporary audit directory and deletes it afterwards.

**Why this matters:** an evidence gate passing for a pilot does not automatically
authorize a recommendation. Synthetic stakeholder preferences still block it.
This demonstration verifies a behavior, not the correctness of the policy model.

## Explore and reproduce

```bash
python3 -m cwm interfaccia
# Open http://127.0.0.1:8765 — local interface, currently in Italian.
```

For a persistent audit and reproducibility check:

```bash
python3 -m cwm preregistra
python3 -m cwm analizza --rapido
python3 -m cwm verifica
```

The quick analysis skips study valuation and weight stability; run `analizza`
without `--rapido` for the full analysis. Keep audit keys private. The HMAC audit
does not prevent a key holder from rewriting history: use an external checkpoint
as described in the README. Verification without one has narrower guarantees.

## Help find a counterexample

Can you reproduce a case where a recommendation is issued despite insufficient
evidence or synthetic preferences? Use the **Abstention challenge** issue form.
Include the commit, command, minimal configuration, expected and actual outcome.
For security issues follow SECURITY.md instead. Do not upload private data or keys.

Useful contributions also include checking one source against its original table,
an English translation of one interface section, or one reproducible regression test.
Read CONTRIBUTING.md before changing decision rules. Do not disable safeguards to
produce a more exciting demo.

## Limits

Some estimates have sources; other assumptions and stakeholder preferences are
illustrative. Holdouts are synthetic. The evidence rules and rights constraints
encode choices requiring independent scrutiny. The EMA benchmark checks a narrow
numerical comparison, not real-world decision quality or general superiority.
