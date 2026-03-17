# Oracle fusion upgrade

This workspace adds an Oracle-facing planning API.

## Added endpoint

- `POST /api/oracle/plan`
- `GET /api/oracle/health`

## Purpose

Expose AAE as a candidate-generation and evaluation engine for Oracle-OS.
The endpoint does not execute host actions and does not replace Oracle verification.
