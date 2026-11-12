"""Small transactional workflow actions used by the Streamlit console."""
from datetime import date
from .database import get_connection
import hashlib

def _audit(conn, entity_type, entity_id, action, actor, details):
    aid="AUD-"+hashlib.sha1(f"{entity_type}|{entity_id}|{action}|{details}".encode()).hexdigest()[:16]
    conn.execute("INSERT OR IGNORE INTO audit_events VALUES (?,?,?,?,?,?,?)",(aid,entity_type,entity_id,action,actor,date.today().isoformat(),details))

def complete_task(task_id, actor="SYSTEM", db_path="data/employee_lifecycle.db"):
    with get_connection(db_path) as c:
        row=c.execute("SELECT * FROM tasks WHERE task_id=?",(task_id,)).fetchone()
        if not row: raise ValueError("Task not found")
        blocked=c.execute("""SELECT COUNT(*) FROM dependencies d JOIN tasks p ON p.task_id=d.predecessor_task_id WHERE d.successor_task_id=? AND p.task_status<>'COMPLETED'""",(task_id,)).fetchone()[0]
        if blocked: raise ValueError(f"Cannot complete task: {blocked} prerequisite task(s) are not completed")
        c.execute("UPDATE tasks SET task_status='COMPLETED',completed_at=? WHERE task_id=?",(date.today().isoformat(),task_id))
        _audit(c,"TASK",task_id,"COMPLETED",actor,"Task completed after prerequisite validation")

def provision_access(employee_id, access_role_id, manager_approved, actor="IT", db_path="data/employee_lifecycle.db"):
    with get_connection(db_path) as c:
        emp=c.execute("SELECT employment_status,start_date FROM employees WHERE employee_id=?",(employee_id,)).fetchone()
        if not emp: raise ValueError("Employee not found")
        if not manager_approved: raise ValueError("Manager approval is required before provisioning")
        if emp["employment_status"]!="ACTIVE" or emp["start_date"]>date.today().isoformat(): raise ValueError("Access can be provisioned only for an active employee whose start date has arrived")
        if not c.execute("SELECT 1 FROM access_roles WHERE access_role_id=?",(access_role_id,)).fetchone(): raise ValueError("Access role not found")
        count=c.execute("SELECT COUNT(*) FROM access_grants WHERE employee_id=?",(employee_id,)).fetchone()[0]+1
        grant_id=f"GRANT-{employee_id}-{count:03d}"
        c.execute("INSERT INTO access_grants VALUES (?,?,?,?,?,?,?)",(grant_id,employee_id,access_role_id,date.today().isoformat(),actor,"APPROVED",None))
        _audit(c,"ACCESS_GRANT",grant_id,"PROVISIONED",actor,"Provisioned after manager approval and active-employment checks")
        return grant_id

def assign_asset(employee_id, asset_id, actor="FACILITIES", db_path="data/employee_lifecycle.db"):
    with get_connection(db_path) as c:
        emp=c.execute("SELECT employment_status,start_date FROM employees WHERE employee_id=?",(employee_id,)).fetchone()
        asset=c.execute("SELECT asset_status FROM assets WHERE asset_id=?",(asset_id,)).fetchone()
        if not emp or not asset: raise ValueError("Employee or asset not found")
        if emp["employment_status"]!="ACTIVE" or emp["start_date"]>date.today().isoformat(): raise ValueError("Equipment can be assigned only to an active employee")
        if asset["asset_status"]!="AVAILABLE": raise ValueError("Asset is not available")
        c.execute("UPDATE assets SET asset_status='ASSIGNED',assigned_employee_id=?,assigned_at=? WHERE asset_id=?",(employee_id,date.today().isoformat(),asset_id))
        n=c.execute("SELECT COUNT(*) FROM asset_assignments").fetchone()[0]+1
        assignment_id=f"AAS-ACT-{n:08d}"
        c.execute("INSERT INTO asset_assignments (assignment_id,asset_id,employee_id,assigned_at,returned_at,assignment_status) VALUES (?,?,?,?,?,?)",(assignment_id,asset_id,employee_id,date.today().isoformat(),None,"ACTIVE"))
        _audit(c,"ASSET",asset_id,"ASSIGNED",actor,f"Assigned to {employee_id}; acknowledgement pending")
        return assignment_id

def acknowledge_asset(asset_id, employee_id, actor="EMPLOYEE", db_path="data/employee_lifecycle.db"):
    with get_connection(db_path) as c:
        row=c.execute("SELECT assignment_id FROM asset_assignments WHERE asset_id=? AND employee_id=? AND assignment_status='ACTIVE' ORDER BY assigned_at DESC LIMIT 1",(asset_id,employee_id)).fetchone()
        if not row: raise ValueError("No active asset assignment found for this employee")
        c.execute("UPDATE asset_assignments SET acknowledged_at=? WHERE assignment_id=?",(date.today().isoformat(),row["assignment_id"]))
        _audit(c,"ASSET",asset_id,"ACKNOWLEDGED",actor,f"Employee {employee_id} acknowledged receipt")

def start_offboarding(employee_id, reason, actor="HR", db_path="data/employee_lifecycle.db"):
    with get_connection(db_path) as c:
        emp=c.execute("SELECT employment_status FROM employees WHERE employee_id=?",(employee_id,)).fetchone()
        if not emp: raise ValueError("Employee not found")
        if emp["employment_status"]!="ACTIVE": raise ValueError("Only active employees can be offboarded")
        existing=c.execute("SELECT offboarding_case_id FROM offboarding_cases WHERE employee_id=?",(employee_id,)).fetchone()
        if existing: raise ValueError("An offboarding case already exists")
        count=c.execute("SELECT COUNT(*) FROM offboarding_cases").fetchone()[0]+1
        off=f"OFF-{date.today().year}-{count:06d}"; today=date.today().isoformat()
        c.execute("UPDATE employees SET employment_status='TERMINATED',end_date=? WHERE employee_id=?",(today,employee_id))
        c.execute("INSERT INTO offboarding_cases VALUES (?,?,?,?,?)",(off,employee_id,today,reason,"IN_PROGRESS"))
        defs=[("MANAGER_EXIT_APPROVAL","MANAGER"),("ACCESS_REVOCATION","IT"),("LAPTOP_RECOVERY","FACILITIES"),("BADGE_RETURN","FACILITIES")]
        for i,(kind,owner) in enumerate(defs,1):
            tid=f"TASK-{off}-{i:03d}"
            c.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",(tid,off,kind,owner,"PENDING",today,None,None,off))
            _audit(c,"TASK",tid,"CREATED","SYSTEM",f"Offboarding task {kind} created")
        _audit(c,"EMPLOYEE",employee_id,"TERMINATED",actor,f"Offboarding initiated: {reason}")
        return off

def revoke_employee_access(employee_id, actor="IT", db_path="data/employee_lifecycle.db"):
    with get_connection(db_path) as c:
        today=date.today().isoformat()
        rows=c.execute("SELECT grant_id FROM access_grants WHERE employee_id=? AND revoked_at IS NULL",(employee_id,)).fetchall()
        for row in rows:
            c.execute("UPDATE access_grants SET revoked_at=? WHERE grant_id=?",(today,row["grant_id"]))
            _audit(c,"ACCESS_GRANT",row["grant_id"],"REVOKED",actor,"Access revoked during offboarding")
        return len(rows)

def recover_employee_assets(employee_id, actor="FACILITIES", db_path="data/employee_lifecycle.db"):
    with get_connection(db_path) as c:
        today=date.today().isoformat()
        rows=c.execute("SELECT asset_id FROM assets WHERE assigned_employee_id=? AND asset_status='ASSIGNED'",(employee_id,)).fetchall()
        for row in rows:
            aid=row["asset_id"]
            c.execute("UPDATE assets SET asset_status='RECOVERED',assigned_employee_id=NULL,recovered_at=? WHERE asset_id=?",(today,aid))
            c.execute("UPDATE asset_assignments SET assignment_status='RETURNED',returned_at=? WHERE asset_id=? AND employee_id=? AND assignment_status='ACTIVE'",(today,aid,employee_id))
            _audit(c,"ASSET",aid,"RECOVERED",actor,f"Asset recovered from {employee_id}")
        return len(rows)
