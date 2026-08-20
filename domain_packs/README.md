# Domain packs

StreamPulse's classifier has no built-in notion of "Finance" or "HR" — it matches
incoming records against whichever domain taxonomy is configured here. A domain
pack is a JSON file: keys are domain names, values are lists of short prototype
phrasings for that domain (multiple diverse phrasings per domain improve embedding
match quality over a single sentence).

`demo_business.json` is the bundled reference pack (Finance, Operations, Growth,
People, ESG, IT_Ops, General) used by default and by the shipped evaluation set —
it is an example configuration, not a fixed schema.

To classify against your own taxonomy, write a pack in the same shape and point
`STREAMPULSE_DOMAIN_PACK` at its path:

```json
{
  "DomainName": [
    "a short prototype phrase for this domain",
    "another phrasing, different wording, same meaning"
  ]
}
```

```bash
export STREAMPULSE_DOMAIN_PACK=/path/to/your_pack.json
```

If the env var is unset, or the file is missing or malformed, StreamPulse falls
back to the bundled demo pack and logs a warning.
