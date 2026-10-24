# Common document coverage (extension v0.6.0)

This is a synthetic regression matrix, not a claim to support every document or country. All examples are generated locally with fictional values, no official logos or real scans. No document is uploaded to a hosted service by these tests.

| Document | Tested fields |
|---|---|
| Aadhaar | Name, birth date, address, grouped uncertain identifier |
| PAN | Name, parent name, birth date, PAN |
| Passport | Given name, surname, passport number, birth date, machine-readable line |
| Driving licence | Name, licence number, address |
| Voter ID | Name, EPIC number, address |
| Ration card | Name, ration number, address |
| Bank statement | Account-holder name, account number, IFSC, address |
| Payment card | Cardholder name, unlabelled Luhn-valid card number |
| Payslip | Employee name/ID, UAN, net salary |
| Medical report | Patient name, UHID, diagnosis, blood group |
| Insurance | Name, policy number, birth date |
| Utility bill | Customer name, consumer number, billing address |
| Invoice | Customer name, shipping address, GSTIN, email |
| Education certificate | Student name, admission number, birth date |
| Vehicle registration | Name, registration number, address |
| Resume | Full name, email, mobile, address |
| Benign invoice control | Invoice number/date, quantity and total should remain |

## Logic

`privacygate/document_fields.py` adds conservative English label/value recognition to OCR and PDF text-layer inspection. It handles values on the same or immediately following line, and up to three indented postal-address lines. Spatial OCR rows supplement reading order. Document-number candidates require numeric or masked characters; formats are not treated as proof of issuance. Birth dates, health fields, personal financial values and financial identifiers receive explicit labels in the preview. Existing Aadhaar/PAN/email/mobile/account rules and all-page local Gemma vision still run. The new rules do not change text-only scanning.

Every located finding seeds an editable default mask, including uncertain candidates. Luhn-valid 13-19-digit card shapes and 30-44-character machine-readable identity-line shapes are also flagged without labels; this does not decode or authenticate them. Names without labels, handwriting, signatures, portraits and QR payloads continue to depend on vision or manual inspection. Prompt instructions for these features are not verified detectors. No OCR-confidence shortcut skips vision.

The PDF text layer can expose hidden fields even when OCR misses them; these appear without a fabricated bounding box. The user must locate them manually or mask the whole page. Raster exports exclude source PDF objects and text.

## Tests

```sh
python -m unittest discover -s tests -p test_document_fields.py -v
python scripts/benchmark_documents.py --require-perfect
```

The unit matrix generates 17 layouts, injects synthetic word geometry, checks at least 98% of each expected field's rendered text ink is inside same-type masks, and verifies selected export pixels are black. These are deterministic localization/export tests, not native OCR accuracy tests.

The second command requires native local Tesseract and tests each layout both as PNG and as a raster PDF rendered through the production PDF path: 34 cases. It reports aggregate coverage and misses without transcripts, and checks a benign invoice for false positives. macOS CI runs this as a required gate on Python 3.10 and 3.13. Missing OCR exits BLOCKED_UNVERIFIED. Broad live-Gemma document recall and target-Mac memory/latency remain unverified.

## Limits

English printed labels only; no established multilingual, handwritten, skewed, low-resolution, arbitrary-column or international-format coverage. Inline fields may be conservatively covered together. Unlabelled sensitive facts can be missed. Other 12-digit references, institutional addresses or business identifiers can be flagged conservatively. Sensitive identifiers may be needed for a task: masks remain editable and require explicit visual approval. Every page must still be checked before export or attachment. The current 5-page/6-MiB upload limits remain.

After updating: restart the local bridge, reload the extension, and rescan original files. Old prepared exports do not gain new masks.
