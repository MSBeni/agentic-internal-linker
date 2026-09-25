# Security Policy

## Supported versions

Until the first stable release, security fixes are applied to the latest commit on `main`.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature for this repository. Do not open a public issue containing exploit details, credentials, private documents, or customer data.

Include the affected version, reproduction steps, expected impact, and any suggested mitigation. You should receive an acknowledgement within seven days.

## Security model

The core package does not perform network requests or execute document content. URL handling is fail-closed, output patches are exact-span validated, and a validation failure returns the original document unchanged.

Applications embedding this package remain responsible for authentication, authorization, tenant isolation, rate limits, file access, logging, and safe storage of documents and catalogs.
