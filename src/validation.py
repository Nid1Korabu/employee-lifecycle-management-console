
from collections import defaultdict
from .database import get_connection


def _cycle_count(conn):
    edges = conn.execute(
        "SELECT predecessor_task_id, successor_task_id FROM dependencies"
    ).fetchall()

    graph = defaultdict(list)
    nodes = set()

    for a, b in edges:
        graph[a].append(b)
        nodes.update((a, b))

    color = {n: 0 for n in nodes}
    cycles = 0

    def visit(n):
        nonlocal cycles

        color[n] = 1

        for nxt in graph[n]:
            if color.get(nxt, 0) == 1:
                cycles += 1
            elif color.get(nxt, 0) == 0:
                visit(nxt)

        color[n] = 2

    for n in nodes:
        if color[n] == 0:
            visit(n)

    return cycles


def detect_findings(db_path="data/employee_lifecycle.db"):
    findings = []

    with get_connection(db_path) as c:

        # 1. Access granted before employee start date or without approval.
        q = """
        SELECT
            g.grant_id,
            g.employee_id,
            'ACCESS_BEFORE_START_OR_APPROVAL' AS issue_type
        FROM access_grants g
        JOIN employees e USING(employee_id)
        WHERE g.granted_at < e.start_date
           OR g.approval_status <> 'APPROVED'
        """
        findings += [dict(r) for r in c.execute(q)]

        # 2. Detect overlapping assignment periods for the same asset.
        # Same-day boundaries are treated as overlapping because
        # assignment timestamps are stored as dates, not exact times.
        q = """
        SELECT DISTINCT
            a.asset_id AS entity_id,
            'DUPLICATE_ASSET_ASSIGNMENT' AS issue_type
        FROM asset_assignments a
        JOIN asset_assignments b
          ON a.asset_id = b.asset_id
         AND a.assignment_id < b.assignment_id
        WHERE date(a.assigned_at)
              <= date(COALESCE(b.returned_at, '9999-12-31'))
          AND date(b.assigned_at)
              <= date(COALESCE(a.returned_at, '9999-12-31'))
        """
        findings += [dict(r) for r in c.execute(q)]

        # 3. Terminated employees with access grants not revoked.
        q = """
        SELECT
            g.grant_id AS entity_id,
            'TERMINATED_EMPLOYEE_ACTIVE_GRANT' AS issue_type
        FROM access_grants g
        JOIN employees e USING(employee_id)
        WHERE e.employment_status = 'TERMINATED'
          AND g.revoked_at IS NULL
        """
        findings += [dict(r) for r in c.execute(q)]

        # 4. Circular task dependencies.
        if _cycle_count(c) > 0:
            findings.append({
                "entity_id": "TASK_GRAPH",
                "issue_type": "TASK_DEPENDENCY_CYCLE"
            })

        # 5. Recovered assets that are still assigned.
        q = """
        SELECT
            asset_id AS entity_id,
            'RECOVERED_ASSET_STILL_ASSIGNED' AS issue_type
        FROM assets
        WHERE asset_status = 'RECOVERED'
          AND assigned_employee_id IS NOT NULL
        """
        findings += [dict(r) for r in c.execute(q)]

    return findings


def run_checks(db_path="data/employee_lifecycle.db"):
    checks = []

    with get_connection(db_path) as c:

        # Foreign-key integrity.
        fk = c.execute("PRAGMA foreign_key_check").fetchall()
        checks.append((
            "Foreign-key integrity",
            len(fk) == 0,
            f"{len(fk)} violations"
        ))

        # Primary-key uniqueness.
        for table, key in [
            ("employees", "employee_id"),
            ("tasks", "task_id"),
            ("access_grants", "grant_id"),
            ("assets", "asset_id"),
            ("audit_events", "audit_event_id")
        ]:
            dup = c.execute(
                f"""
                SELECT COUNT(*)
                FROM (
                    SELECT {key}
                    FROM {table}
                    GROUP BY {key}
                    HAVING COUNT(*) > 1
                )
                """
            ).fetchone()[0]

            checks.append((
                f"Primary-key uniqueness: {table}",
                dup == 0,
                f"{dup} duplicate keys"
            ))

        # Employment date ordering.
        bad_dates = c.execute(
            """
            SELECT COUNT(*)
            FROM employees
            WHERE end_date IS NOT NULL
              AND end_date < start_date
            """
        ).fetchone()[0]

        checks.append((
            "Employment date ordering",
            bad_dates == 0,
            f"{bad_dates} invalid records"
        ))

        # Allowed access approval states.
        invalid = c.execute(
            """
            SELECT COUNT(*)
            FROM access_grants
            WHERE approval_status NOT IN
            ('PENDING', 'APPROVED', 'REJECTED')
            """
        ).fetchone()[0]

        checks.append((
            "Allowed access approval states",
            invalid == 0,
            f"{invalid} invalid states"
        ))

    # Confirm all five anomaly types are detected.
    findings = detect_findings(db_path)
    types = {x["issue_type"] for x in findings}

    expected = {
        "ACCESS_BEFORE_START_OR_APPROVAL",
        "DUPLICATE_ASSET_ASSIGNMENT",
        "TERMINATED_EMPLOYEE_ACTIVE_GRANT",
        "TASK_DEPENDENCY_CYCLE",
        "RECOVERED_ASSET_STILL_ASSIGNED"
    }

    missing = expected - types

    checks.append((
        "Five anomaly detectors executed",
        not missing,
        "Detected: " + ", ".join(sorted(expected & types))
        + ("; missing: " + ", ".join(sorted(missing))
           if missing else "")
    ))

    return checks
