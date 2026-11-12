
from pathlib import Path
import sqlite3


DB_PATH = Path("data/employee_lifecycle.db")


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS departments (
    department_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS access_roles (
    access_role_id TEXT PRIMARY KEY,
    role_name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS roles (
    role_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    access_role_id TEXT NOT NULL
        REFERENCES access_roles(access_role_id)
);

CREATE TABLE IF NOT EXISTS managers (
    manager_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    department_id TEXT NOT NULL
        REFERENCES departments(department_id)
);

CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    employment_type TEXT NOT NULL
        CHECK(employment_type IN ('FULL_TIME', 'CONTRACTOR')),
    employment_status TEXT NOT NULL
        CHECK(employment_status IN (
            'PREBOARDING', 'ACTIVE', 'TERMINATED'
        )),
    role_id TEXT NOT NULL REFERENCES roles(role_id),
    department_id TEXT NOT NULL
        REFERENCES departments(department_id),
    manager_id TEXT REFERENCES managers(manager_id),
    start_date TEXT NOT NULL,
    end_date TEXT,
    CHECK(end_date IS NULL OR end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS employee_role_history (
    history_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL
        REFERENCES employees(employee_id),
    old_role_id TEXT REFERENCES roles(role_id),
    new_role_id TEXT NOT NULL REFERENCES roles(role_id),
    effective_date TEXT NOT NULL,
    changed_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS onboarding_cases (
    onboarding_case_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL UNIQUE
        REFERENCES employees(employee_id),
    case_status TEXT NOT NULL
        CHECK(case_status IN (
            'NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'ON_HOLD'
        )),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS offboarding_cases (
    offboarding_case_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL UNIQUE
        REFERENCES employees(employee_id),
    termination_date TEXT NOT NULL,
    reason TEXT,
    case_status TEXT NOT NULL
        CHECK(case_status IN ('OPEN', 'IN_PROGRESS', 'COMPLETED'))
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    owner_team TEXT NOT NULL
        CHECK(owner_team IN (
            'HR', 'MANAGER', 'IT', 'FACILITIES', 'SYSTEM'
        )),
    task_status TEXT NOT NULL
        CHECK(task_status IN (
            'PENDING', 'IN_PROGRESS', 'COMPLETED', 'BLOCKED'
        )),
    due_date TEXT,
    completed_at TEXT,
    onboarding_case_id TEXT
        REFERENCES onboarding_cases(onboarding_case_id),
    offboarding_case_id TEXT
        REFERENCES offboarding_cases(offboarding_case_id),
    CHECK(
        onboarding_case_id IS NOT NULL
        OR offboarding_case_id IS NOT NULL
    )
);

CREATE TABLE IF NOT EXISTS dependencies (
    dependency_id TEXT PRIMARY KEY,
    predecessor_task_id TEXT NOT NULL REFERENCES tasks(task_id),
    successor_task_id TEXT NOT NULL REFERENCES tasks(task_id),
    UNIQUE(predecessor_task_id, successor_task_id),
    CHECK(predecessor_task_id <> successor_task_id)
);

CREATE TABLE IF NOT EXISTS access_grants (
    grant_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employees(employee_id),
    access_role_id TEXT NOT NULL
        REFERENCES access_roles(access_role_id),
    granted_at TEXT NOT NULL,
    approved_by TEXT,
    approval_status TEXT NOT NULL
        CHECK(approval_status IN ('PENDING', 'APPROVED', 'REJECTED')),
    revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS assets (
    asset_id TEXT PRIMARY KEY,
    asset_type TEXT NOT NULL,
    serial_number TEXT NOT NULL UNIQUE,
    asset_status TEXT NOT NULL
        CHECK(asset_status IN ('AVAILABLE', 'ASSIGNED', 'RECOVERED')),
    assigned_employee_id TEXT REFERENCES employees(employee_id),
    assigned_at TEXT,
    recovered_at TEXT
);

CREATE TABLE IF NOT EXISTS asset_assignments (
    assignment_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    employee_id TEXT NOT NULL REFERENCES employees(employee_id),
    assigned_at TEXT NOT NULL,
    returned_at TEXT,
    assignment_status TEXT NOT NULL
        CHECK(assignment_status IN ('ACTIVE', 'RETURNED')),
    acknowledged_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
    audit_event_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_time TEXT NOT NULL,
    details TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_status
ON tasks(task_status);

CREATE INDEX IF NOT EXISTS idx_grants_employee
ON access_grants(employee_id);

CREATE INDEX IF NOT EXISTS idx_assets_employee
ON assets(assigned_employee_id);

CREATE INDEX IF NOT EXISTS idx_audit_entity
ON audit_events(entity_type, entity_id);
"""


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def get_connection(db_path=DB_PATH):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        db_path,
        factory=ClosingConnection
    )

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def initialize_database(db_path=DB_PATH):
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
