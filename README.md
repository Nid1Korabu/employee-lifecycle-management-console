# Employee Lifecycle Management Console

A synthetic-data-driven employee lifecycle management application built with Python, Streamlit, Pandas, and SQLite.

The console demonstrates employee pre-boarding, onboarding task management, approval-based access provisioning, equipment assignment, offboarding, exception detection, validation, and audit traceability.

## Key Features

- **Employee lifecycle:** Manage employee records, pre-boarding, active employment, and offboarding.
- **Task management:** Track onboarding and offboarding tasks with dependency checks.
- **Access provisioning:** Record approved access grants and revoke access during offboarding.
- **Asset management:** Assign, acknowledge, and recover employee equipment.
- **Exception detection:** Identify five seeded operational anomaly types.
- **Validation:** Run structural and integrity checks against the operational database.
- **Audit trail:** Record workflow actions for traceability.
- **Synthetic data generation:** Generate reproducible datasets at configurable scale.
- **Exports:** Generate CSV, JSON, SQL seed, validation summary, and source manifest files.

## Technology Stack

- Python 3.12+
- Streamlit 1.66.1
- Pandas 3.1.0
- SQLite

## Project Structure

```text
employee_lifecycle_console/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── docs/
│   └── data_dictionary.md
├── src/
│   ├── __init__.py
│   ├── database.py
│   ├── generator.py
│   ├── validation.py
│   └── workflows.py
└── tests/
    └── test_smoke.py
```

Generated databases and exports are created locally inside `data/` and are excluded from Git.

## Setup and Installation

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd employee_lifecycle_console
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

## Generate Synthetic Data

Generate the full demonstration dataset:

```bash
python -m src.generator --scale 1000 --seed 20261112
```

For a smaller development dataset:

```bash
python -m src.generator --scale 50 --seed 20261112
```

The generator creates synthetic employee lifecycle records, tasks, dependencies, access grants, assets, assignments, and audit events.

Generated exports include CSV and JSON files, a SQL seed file, a validation summary, a source manifest, and a separate ground-truth file.

## Run the Application

```bash
python -m streamlit run app.py
```

Open the local Streamlit URL displayed in the terminal, normally:

```text
http://localhost:8501
```

## Run Tests

```bash
python -m unittest discover -s tests -v
```

The test suite covers anomaly detection, foreign-key integrity, ground-truth separation, data volume, and structural checks.

## Reproducibility

The generator uses a fixed random seed and a fixed synthetic reference date (`2026-11-12`) by default.

To verify reproducibility:

```bash
python -m src.generator --scale 1000 --seed 20261112 --verify-reproducibility
```

**Note:** This command regenerates temporary comparison datasets to verify exported file checksums.

## Seeded Anomaly Scenarios

The demonstration dataset includes five labelled scenarios:

1. Access granted before the employee start date or without approval.
2. Duplicate asset assignment.
3. Active access grant retained by a terminated employee.
4. Circular task dependency.
5. Recovered asset still assigned.

Anomaly detectors inspect operational database records. They do not use the separate ground-truth file to produce findings.

## Data and Privacy

This project uses synthetic demonstration data only. It does not require or use real employee personal information or external HR systems.

## Scope and Future Enhancements

This is a local demonstration prototype. It is not connected to production HRIS platforms, identity providers, ticketing systems, shipping providers, or hardware inventory services.

A production implementation would require authenticated users, role-based authorization, transactional APIs, notification services, and integration monitoring.