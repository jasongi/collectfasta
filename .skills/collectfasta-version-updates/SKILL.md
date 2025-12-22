---
name: collectfasta-version-updates
description: Update Collectfasta's supported Python/Django versions across CI, packaging metadata, and changelog when new runtimes are released or deprecated. Use for tasks like adjusting GitHub Actions test matrices, setup.cfg classifiers, python_requires, and documenting support changes.
---

# Collectfasta Version Updates

## Update the CI matrix

- Edit `.github/workflows/test-suite.yaml`.
- Verify supported Django/Python combinations using https://docs.djangoproject.com/en/dev/faq/install/#what-python-version-can-i-use-with-django and only include compatible pairs.
- Add new Python/Django versions to the matrix and live-test job.
- Remove EOL Python versions and unsupported Django versions.
- Keep version ranges pinned to minor series (e.g., `>=6.0,<6.1`).

## Update package metadata

- Edit `setup.cfg`.
- Update `python_requires` to match the minimum supported Python.
- Update `Programming Language :: Python :: X.Y` classifiers.
- Add `Framework :: Django :: X.Y` classifiers for supported series.
- Update `mypy` `python_version` to the minimum supported Python.

## Update the changelog

- Add a new entry at the top of `CHANGELOG.md`.
- Mention added/removed Python and Django versions and CI/metadata updates.

## Create a branch and push changes

- Create a new git branch for the change and commit to that branch.
- Push the branch to the remote; never push directly to `master`.
