# aegean.greek

::: aegean.greek

## Sentence-policy registries

The facade also exports two immutable mappings that document the supported rule
contracts:

- `POLICY_IDS` maps each named policy to its stable identity. It also contains the
  `explicit` identity used when complete source `sentence_id` runs supply boundaries.
- `POLICY_RULES` maps the five inferred policies (`default`, `prose`, `verse`,
  `inscription`, and `papyrus`) to their plain-language rule descriptions.

Use these mappings for inspection and provenance; do not modify or interpret a rule
identity as a measured confidence value.
