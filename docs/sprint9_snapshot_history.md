# Sprint 9 — Snapshot History

## Purpose

Sprint 9 adds historical tracking for canonical job postings using dbt snapshots.

The snapshot preserves meaningful changes to job postings over time.

## Snapshot Model

`job_postings_snapshot`

## Source Model

`int_job_posting_deduped`

## Grain

One row per historical version of a canonical job posting.

## Current Version

A current snapshot row is identified by: dbt_valid_to IS NULL