## De-identification Output Review — Issues and Normalization Plan

### Issues found (from comparing outputs)

1) Over-aggressive PERSON detection on non-names
- Header redacted as a person: `Kamal Diagnostic Center` → `[NAME1]` (see metadata entity: PERSON with original_text including header).
- Repeated table words treated as names: many occurrences of "Absent/Absen" were tagged as PERSON and replaced with `[NAMEx]`, e.g. line shows `Blood [NAME3]Chemical Examination` where `Absent Absen` was replaced, corrupting structure.

2) Misclassification of medical degree as LOCATION
- `MD` in `MBBS, MD Pathologist` was classified as LOCATION and replaced → `MBBS, [LOCATION] Pathologist`.

3) Layout/format corruption around replacements
- Newlines/spacing were swallowed around PERSON replacements, causing concatenation: `Blood [NAME3]Chemical Examination` (missing newline/spacing between sections).
- Multi-line name spans captured with following credential text (e.g., `A. K. Asthana\nDMLT`) leading to odd punctuation/line-joins in output.

4) REFERRED_BY extraction overly broad
- Output shows `Referred By: [REFERRED_BY]: 14/05/2021` with an extra colon and tight spacing; the regex likely captures up to `Date` inconsistently.

5) Inconsistent path separators in metadata
- `source` uses `/`, whereas `raw_text_path` and `redacted_text_path` use `\\`. This is minor but inconsistent across platforms.

6) Module naming typo could cause confusion
- File `src/pii_anonynizer.py` is misspelled (should be `pii_anonymizer.py`). Not breaking by itself but error-prone.

7) Analyzer config includes custom entity types without custom recognizers
- `pii_detector.detect_pii` passes `REFERRED_BY/REG_NO/UHID` to Presidio analyzer while also doing custom regex extraction. This can cause duplication or undefined behavior unless custom recognizers are registered.

8) PERSON placeholder numbering policy not explicit
- Operators define PERSON replacement as `[NAME]` but outputs/metadata show `[NAME1]`, `[NAME2]`… Numbering appears to be applied elsewhere without explicit mapping policy.


### Combined remediation approach (NER + patterns + regex)

- **Core NER model tuning**: keep Presidio’s analyzer backed by spaCy but retrain/fine-tune PERSON/ORG labels with clinic-style documents so facility headers and credential lines are labeled accurately. Introduce annotated examples for tables to teach the model that repeated tokens like “Absent” are O (outside) labels.
- **Pattern-based custom recognizers**: register Presidio `PatternRecognizer` instances for `REFERRED_BY`, `REG_NO`, `UHID`, and credential phrases. Each recognizer specifies token-level patterns (e.g., `Token('Referred') + Token('By') + NamePattern`) and assigns confidence scores higher than regex fallbacks when the pattern matches.
- **Regular-expression safety net**: employ regex rules for deterministic fields (IDs, dates) and for post-processing layout (e.g., boundary-aware substitutions that preserve whitespace). Regex also powers deny/allow lists and validates extracted spans before anonymization.
- **Post-detection arbitration**: combine NER outputs with pattern matches by using Presidio’s decision engine: when conflicts occur, prefer the pattern recognizer for deterministic fields, fall back to regex if NER confidence is below threshold, and discard detections that violate denylist validations.

### Exact plan to normalize these errors

1) Reduce false-positive PERSON detections in clinical tables
- Retrain the spaCy PERSON model component (or add rule-based `EntityRuler`) with annotated lab reports so tokens like `Absent/Absen` are explicitly tagged as outside the PERSON label.
- Add a denylist-driven regex validator that drops PERSON hits whose lowercase form matches lab terminology (e.g., `absent`, `present`, `clear`, `pale`, `hpf`, `r.b.c`, `pus`, `bacteria`).
- Wrap these validators into a Presidio `PatternRecognizer` scoring override so PERSON detections lacking name cues (`Patient Name`, `Mr.`/`Dr.` prefixes, capitalized word pairs) are down-weighted below the acceptance threshold.

2) Distinguish organizations and credentials
- Extend the NER model with labeled ORG examples for diagnostic centers; adjust Presidio analyzer entity list to include ORG with a custom replacement policy (`[ORG]` or passthrough per compliance rules).
- Register a credential `PatternRecognizer` that matches sequences like `, MD`, `, MBBS`, `DMLT` using token patterns and flags them as NON-PII (`score=0`) so downstream anonymization leaves them untouched.
- Add a regex-based post-check: when LOCATION hits are only two letters and directly follow `MBBS,`, demote their score to below threshold.

3) Preserve layout during anonymization
- Before anonymization, run a regex pass to insert sentinel markers at line breaks (`__LINEBREAK__`) so replacements cannot merge adjacent lines; remove markers afterward.
- Sort entities by start index and apply replacements from right-to-left using Presidio’s anonymizer extension hook to prevent index drift.
- Enforce boundary-aware substitution: if the matched span ends without whitespace, inject a single space or newline depending on the original layout metadata captured during detection.

4) Tighten REFERRED_BY pattern recognizer
- Define a Presidio `PatternRecognizer` using a pattern list for `Referred By` lines that captures only the name token sequence and stops at keywords like `Date` or a date regex.
- Keep a regex fallback identical to `r"Referred By[:\s]*([A-Za-z .,-]+?)(?:\s+Date\b|\s+\d{1,2}/\d{1,2}/\d{2,4}|$)"`, but invoke it only if the pattern recognizer does not fire.
- Normalize whitespace in the matched span before anonymization so the output renders as `Referred By: [REFERRED_BY] Date: ...`.

5) Normalize metadata paths
- Emit POSIX-style paths consistently or include both raw OS path and normalized path fields. For cross-platform use, prefer `/` in JSON while using OS-specific paths internally.

6) Correct module name and imports
- Rename `src/pii_anonynizer.py` → `src/pii_anonymizer.py` and update imports (`from .pii_anonymizer import anonymize_text`).

7) Align analyzer entities with recognizers
- Register Presidio `PatternRecognizer` instances for `REFERRED_BY`, `REG_NO`, `UHID` so they participate in the main analyzer pipeline with well-defined scores.
- Remove those entity labels from the analyzer’s default list unless their recognizers are registered, preventing undefined-class errors.
- Deprecate the manual regex append helper once the recognizers are stable; retain regex-only unit tests to ensure parity.

8) Standardize placeholder policy
- Use a post-processing step that aggregates analyzer results by entity type and assigns placeholders via deterministic sequencing (`[NAME1]`, `[NAME2]`, etc.), leveraging regex to substitute counted placeholders into both text and metadata.
- Document the mapping generation in metadata so each placeholder links back to the anonymized span, supporting audit trails while remaining compliant.

9) Add regression checks
- Add a simple comparison test that asserts medical keywords and units remain unchanged, line counts stay stable within ±1, and placeholders don’t merge headings (e.g., no `]Chemical`).

10) Optional: Tune LOCATION recognizer
- Reduce LOCATION confidence or add negative examples to avoid matching short two-letter tokens like `MD` when surrounded by credentials.


Implementation order (safe, minimal-change first):
1) Tighten `REFERRED_BY` regex (Issue 4) and add denylist + credential whitelist (Issues 1–2).
2) Layout-preserving replacement logic (Issue 3).
3) Placeholder numbering centralization (Issue 8).
4) Analyzer entity list alignment (Issue 7).
5) Path normalization in metadata (Issue 5).
6) Module rename and import fix (Issue 6).
7) Optional LOCATION tuning and ORG handling (Issues 2 & 10).


### Implementation progress (current changes)

- Updated `src/pii_detector.py` to register Presidio `PatternRecognizer`s for `REFERRED_BY`, `REG_NO`, `UHID`, and facility-style `ORG` headers, while layering regex fallback and denylist/whitelist heuristics that suppress table tokens, reclassify diagnostic centers, and drop credential abbreviations from LOCATION hits.
- Adjusted `src/deidentify_pipeline.py` to preserve leading/trailing whitespace during replacements, add `[ORG]` substitution support, and normalize metadata paths via POSIX-style serialization; this prevents layout corruption and cross-platform path mismatches.
- Added `src/pii_anonymizer.py`, mirroring the anonymizer helpers and extending operator mappings to handle the new `ORG` placeholder, then removed the misspelled `pii_anonynizer.py` file.
- Kept regex-based fallbacks to guarantee UHID/Reg/Referrer capture even if NER misses them, but results are now deduplicated against analyzer detections.
- Outstanding (future): training a domain-specific NER model and automating regression comparisons remain open follow-up items.


### Latest adjustments (2025-11-07)

- Extended NER + patterns by adding a `PERSON` pattern recognizer and regex fallback that specifically targets `Patient Name:` lines so patient names are always captured even when the base model misses them.
- Hardened PERSON post-processing to strip trailing credentials/newlines and to drop detections that degenerate into lab terms; added ORG span trimming so non-PII tokens (e.g., `Patient`) remain in the header.
- Tightened REFERRED_BY/REG_NO/UHID trimming logic to discard label-only spans and require digit-bearing identifiers, preventing `[REFERRED_BY]: [REFERRED_BY]` and `[REG_NO]. no.` artifacts.
- Attempted to regenerate the pipeline outputs, but execution is blocked by missing optional dependencies (`presidio_image_redactor` for image workflows, `fitz`/PyMuPDF for OCR). Verification is pending until at least PyMuPDF is installed or OCR extraction is mocked for testing.
- LOCATION recognizers now include an address-pattern `PatternRecognizer`, a denylist-driven validator for clinical terms, and post-checks that reject short or label-like spans so headings such as `Patient Name` remain intact.
- PHONE detections now require numeric strings with ≥7 digits, reject decimal measurements, and skip hits occurring in measurement contexts (units like `mg/dl`, `ng/mL`, `%`) to avoid redacting lab ratios.


### Post-remediation QA findings (2025-11-07)

- **Re-test required**: the above anomalies should be resolved by the latest recognizer/regex updates, but fresh outputs could not be generated because the environment lacks `fitz` (PyMuPDF) and `presidio_image_redactor`. Once these dependencies are satisfied (or the pipeline is run in mock mode), rerun `src.deidentify_pipeline.deidentify('input/lab2.pdf')` and confirm the patient name is replaced, labels remain, and credentials stay visible.
- **Credential handling watch list**: even with the credential whitelist applied, keep an eye on signatures like `MBBS, MD`—if future samples show lingering over-redaction, consider expanding the whitelist and adding assertion-based tests.


### New findings (location & phone entities)

- **Location false positives**: multiple spans labelled LOCATION are not actual addresses (e.g., `Kamal Diagnostic Center\n\nPatient`, `Sul`, or the literal label `Patient Name`). These produce artifacts like `[LOCATION] Name:` in the redacted text and remove clinical context.
- **Phone-number overreach**: numeric lab ratios such as `0.64 1.5-3.5` and measurement units (`2.10 ng/mL`) are being detected as PHONE_NUMBER because they mimic digit patterns with separators.
- **Legitimate contact details**: true phone lines (`011-03849283`) should still be redacted, so any mitigation must retain sensitivity to those patterns.


### Enhanced resolution approach

1) **Tiered recognizers for LOCATION**
- Register an address-specific `PatternRecognizer` that fires only on patterns containing street keywords (`Road`, `Block`, `City`, etc.), commas, or postal markers; assign higher confidence to these deterministic matches.
- Add an ORG-specific recognizer for facility names and reclassify any spaCy LOCATION hits that contain facility keywords into ORG to avoid `[LOCATION] Name` replacements.
- Introduce a denylist validator (e.g., {`patient`, `name`, `sul`, `lube`, `test`, `profile`}) that drops LOCATION hits whose normalized tokens intersect the denylist or fall below a minimum token count.
- Enforce a minimum structural pattern: keep LOCATION hits only if they contain at least one space and either a comma or a digit; otherwise discard.

2) **Robust phone detection**
- Replace the generic PHONE_NUMBER entity request with a custom pattern set requiring ≥7 digits after stripping separators, allowing optional country/area prefixes, and rejecting values with decimal points or alphabetic units.
- Add a context filter that suppresses phone detections occurring within measurement contexts (tokens like `mg/dl`, `ng/mL`, `%`, `Ratio`) or inside table rows.
- Retain regex fallback for canonical phone lines (`\+?\d{2,4}-\d{6,8}`) so documented contact numbers remain protected.

3) **Post-detection safeguards**
- After aggregation, run a post-processor that examines LOCATION/PHONE spans: if the redaction would result in `[LOCATION] Name` or `[PHONE]` inside a lab value row, drop or downgrade the detection.
- Log discarded spans in metadata under a `skipped_entities` list for auditing, enabling future tuning without silently losing evidence.

4) **Testing strategy**
- Create fixture snippets covering true addresses, fake positives (`Patient Name`), lab ratios, and real phone lines; assert the normalized redaction output keeps labels but masks legitimate contact data.
- Automate regression tests that grep for `[LOCATION] Name` and `[PHONE]` in scientific tables to ensure the rules continue to hold.

