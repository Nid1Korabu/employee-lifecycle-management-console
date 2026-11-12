"""Deterministic synthetic employee lifecycle data generator."""
import argparse, csv, json, random, hashlib
from pathlib import Path
from datetime import date, timedelta
from .database import get_connection, initialize_database

SEED=20261112
TODAY=date(2026,11,12)
DEPARTMENTS=[("DEP-001","Engineering"),("DEP-002","Human Resources"),("DEP-003","Operations"),("DEP-004","Finance"),("DEP-005","Customer Success")]
ACCESS=[("AR-001","Engineering Standard","Engineering tools"),("AR-002","HR Standard","HR systems"),("AR-003","IT Operations","IT administration"),("AR-004","Finance Standard","Finance systems"),("AR-005","CRM Standard","Customer systems")]
ROLES=[("ROL-001","Software Engineer","AR-001"),("ROL-002","HR Associate","AR-002"),("ROL-003","IT Support Analyst","AR-003"),("ROL-004","Finance Analyst","AR-004"),("ROL-005","Customer Success Associate","AR-005")]
FIRST=["Aarav","Diya","Ishaan","Meera","Kabir","Anaya","Rohan","Sara","Vivaan","Aisha","Reyansh","Maya"]
LAST=["Shah","Rao","Patel","Khan","Das","Iyer","Joshi","Nair","Kulkarni","Reddy"]

def _audit(conn, n, typ, eid, action, actor, details):
    audit_id = "AUD-" + hashlib.sha1(f"{typ}|{eid}|{action}".encode()).hexdigest()[:16]
    conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?,?)",(audit_id,typ,eid,action,actor,TODAY.isoformat(),details))

def _reset(conn):
    for t in ["audit_events","asset_assignments","dependencies","tasks","access_grants","assets","offboarding_cases","onboarding_cases","employee_role_history","employees","managers","roles","access_roles","departments"]:
        conn.execute(f"DELETE FROM {t}")

def generate(scale=1000, db_path=Path("data/employee_lifecycle.db"), seed=SEED, export_dir=Path("data/exports"), inject_anomalies=True):
    if scale < 10: raise ValueError("scale must be at least 10")
    rng=random.Random(seed); db_path=Path(db_path); export_dir=Path(export_dir)
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        _reset(conn)
        conn.executemany("INSERT INTO departments VALUES (?,?)",DEPARTMENTS)
        conn.executemany("INSERT INTO access_roles VALUES (?,?,?)",ACCESS)
        conn.executemany("INSERT INTO roles VALUES (?,?,?)",ROLES)
        for i,(did,_) in enumerate(DEPARTMENTS,1):
            conn.execute("INSERT INTO managers VALUES (?,?,?,?)",(f"MGR-{i:03d}",f"Manager {i}",f"manager{i}@example.test",did))
        # Parent/master data and valid employee lifecycle records.
        employees=[]; terminated_ids=[]; preboarding_ids=[]; active_ids=[]
        for i in range(1,scale+1):
            did,dept=DEPARTMENTS[(i-1)%len(DEPARTMENTS)]; rid,title,arid=ROLES[(i-1)%len(ROLES)]
            emp=f"EMP-{i:06d}"; start=TODAY+timedelta(days=rng.randint(-75,25))
            is_term=(i%37==0 or i==scale)
            future_candidate = scale-1 if (scale-1)%37 != 0 else scale-2
            if is_term:
                start=TODAY-timedelta(days=rng.randint(60,180)); end=TODAY-timedelta(days=rng.randint(1,30))
                if end < start: end=start+timedelta(days=1)
            elif i==future_candidate:
                start=TODAY+timedelta(days=rng.randint(5,25)); end=None
            else: end=None
            if is_term: status="TERMINATED"; terminated_ids.append(emp)
            elif start>TODAY: status="PREBOARDING"; preboarding_ids.append(emp)
            else: status="ACTIVE"; active_ids.append(emp)
            name=f"{rng.choice(FIRST)} {rng.choice(LAST)}"; etype="CONTRACTOR" if i%8==0 else "FULL_TIME"
            conn.execute("INSERT INTO employees VALUES (?,?,?,?,?,?,?,?,?,?)",(emp,name,f"employee{i}@example.test",etype,status,rid,did,f"MGR-{((i-1)%len(DEPARTMENTS))+1:03d}",start.isoformat(),end.isoformat() if end else None))
            employees.append((emp,rid,arid,start,status,end))
            onb=f"ONB-{TODAY.year}-{i:06d}"; onb_status="COMPLETED" if status=="ACTIVE" else ("ON_HOLD" if status=="TERMINATED" else "IN_PROGRESS")
            conn.execute("INSERT INTO onboarding_cases VALUES (?,?,?,?)",(onb,emp,onb_status,(start-timedelta(days=14)).isoformat()))
            _audit(conn,i,"EMPLOYEE",emp,"CREATED","HR","Synthetic employee master record created")
            # 8 onboarding tasks per employee, with sequential prerequisites.
            defs=[("HR_DOCUMENTS","HR"),("BACKGROUND_CHECK","HR"),("MANAGER_APPROVAL","MANAGER"),("ROLE_CONFIRMATION","MANAGER"),("ACCESS_PROVISIONING","IT"),("LAPTOP_PREPARATION","FACILITIES"),("EQUIPMENT_ACKNOWLEDGEMENT","FACILITIES"),("ONBOARDING_CONFIRMATION","HR")]
            task_ids=[]
            for j,(tt,owner) in enumerate(defs,1):
                tid=f"TASK-{onb}-{j:03d}"; task_ids.append(tid)
                done=(status=="ACTIVE" and j<=4) or (status=="TERMINATED" and j<=4)
                tstatus="COMPLETED" if done else ("BLOCKED" if status=="PREBOARDING" and j>=5 else "PENDING")
                completed=(start-timedelta(days=1)).isoformat() if done else None
                conn.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",(tid,onb,tt,owner,tstatus,(start-timedelta(days=2)).isoformat(),completed,onb,None))
                _audit(conn,i*10+j,"TASK",tid,"CREATED","SYSTEM",f"Created {tt} task")
            for j,(a,b) in enumerate(zip(task_ids,task_ids[1:]),1):
                conn.execute("INSERT INTO dependencies VALUES (?,?,?)",(f"DPN-{i:06d}-{j:03d}",a,b))
            if i%5==0:
                old=rid; new=ROLES[(i%len(ROLES))][0]
                conn.execute("INSERT INTO employee_role_history VALUES (?,?,?,?,?,?)",(f"RCH-{i:06d}",emp,old,new,(start+timedelta(days=10)).isoformat(),"HR"))
                _audit(conn,i*10+9,"EMPLOYEE",emp,"ROLE_CHANGE","HR",f"Role change scheduled from {old} to {new}")
            if is_term:
                off=f"OFF-{TODAY.year}-{len(terminated_ids):06d}"
                conn.execute("INSERT INTO offboarding_cases VALUES (?,?,?,?,?)",(off,emp,end.isoformat(),"Urgent business separation" if i%74==0 else "Contract/end of employment","IN_PROGRESS"))
                offdefs=[("MANAGER_EXIT_APPROVAL","MANAGER"),("ACCESS_REVOCATION","IT"),("LAPTOP_RECOVERY","FACILITIES"),("BADGE_RETURN","FACILITIES")]
                for j,(tt,owner) in enumerate(offdefs,1):
                    tid=f"TASK-{off}-{j:03d}"; conn.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",(tid,off,tt,owner,"PENDING",end.isoformat(),None,None,off))
                    _audit(conn,scale*20+i*10+j,"TASK",tid,"CREATED","SYSTEM",f"Created offboarding {tt} task")
        # Exactly 1,498 valid access grants, then two deliberate grant anomalies when possible.
        valid_grants=1498 if inject_anomalies else 1500
        eligible=[x for x in employees if x[4]=="ACTIVE"]
        if not eligible: raise ValueError("Scale/date range produced no active employees")
        for g in range(valid_grants):
            emp,rid,arid,start,status,end=eligible[g%len(eligible)]
            granted=max(start,TODAY-timedelta(days=rng.randint(0,45)))
            if granted>TODAY: granted=TODAY
            conn.execute("INSERT INTO access_grants VALUES (?,?,?,?,?,?,?)",(f"GRANT-{emp}-{g//len(eligible)+1:03d}",emp,arid,granted.isoformat(),"MGR-APPROVED","APPROVED",None))
        # 1,200 assets: baseline assignment pool plus available stock.
        for i in range(1,1201):
            aid=f"AST-{i:06d}"; assigned_emp=active_ids[(i-1)%len(active_ids)] if i<=min(850,len(active_ids)) else None
            status="ASSIGNED" if assigned_emp else ("RECOVERED" if i%13==0 else "AVAILABLE")
            assigned_at=(TODAY-timedelta(days=10)).isoformat() if assigned_emp else None
            recovered=(TODAY-timedelta(days=2)).isoformat() if status=="RECOVERED" else None
            conn.execute("INSERT INTO assets VALUES (?,?,?,?,?,?,?)",(aid,"LAPTOP" if i%3 else "MOBILE","SERIAL-{0:06d}".format(i),status,assigned_emp,assigned_at,recovered))
            if assigned_emp:
                conn.execute("INSERT INTO asset_assignments (assignment_id,asset_id,employee_id,assigned_at,returned_at,assignment_status) VALUES (?,?,?,?,?,?)",(f"AAS-{i:06d}-001",aid,assigned_emp,assigned_at,None,"ACTIVE"))
        # Five deliberate anomalies, tagged only in separate ground_truth file.
        truth=[]
        if inject_anomalies:
            # 1: access grant exists before start and lacks approval.
            emp=preboarding_ids[0] if preboarding_ids else employees[-1][0]
            row=next(x for x in employees if x[0]==emp)
            conn.execute("INSERT INTO access_grants VALUES (?,?,?,?,?,?,?)",(f"GRANT-{emp}-999",emp,"AR-001",(row[3]-timedelta(days=3)).isoformat(),None,"PENDING",None))
            truth.append(("ANOM-001","ACCESS_BEFORE_START_OR_APPROVAL","ACCESS_GRANT",f"GRANT-{emp}-999","Grant date precedes start date and approval is pending"))
            # 2: one asset has two simultaneously active assignment records.
            aid="AST-000001"; emp2=active_ids[-1]
            conn.execute("INSERT INTO asset_assignments (assignment_id,asset_id,employee_id,assigned_at,returned_at,assignment_status) VALUES (?,?,?,?,?,?)",("AAS-ANOM-002",aid,emp2,TODAY.isoformat(),None,"ACTIVE"))
            truth.append(("ANOM-002","DUPLICATE_ASSET_ASSIGNMENT","ASSET",aid,"Asset has more than one active assignment"))
            # 3: terminated employee retains a live grant.
            if terminated_ids:
                te=terminated_ids[0]
                conn.execute("INSERT INTO access_grants VALUES (?,?,?,?,?,?,?)",(f"GRANT-{te}-999",te,"AR-001",TODAY.isoformat(),"MGR-APPROVED","APPROVED",None))
                truth.append(("ANOM-003","TERMINATED_EMPLOYEE_ACTIVE_GRANT","ACCESS_GRANT",f"GRANT-{te}-999","Terminated employee still has a non-revoked grant"))
            else:
                truth.append(("ANOM-003","TERMINATED_EMPLOYEE_ACTIVE_GRANT","ACCESS_GRANT","NONE","Not injected: no terminated employee at selected scale"))
            # 4: introduce a back-edge in first employee's onboarding dependency chain.
            onb="ONB-{0}-{1:06d}".format(TODAY.year,1)
            first=f"TASK-{onb}-001"; last=f"TASK-{onb}-008"
            conn.execute("INSERT INTO dependencies VALUES (?,?,?)",("DPN-ANOM-004",last,first))
            truth.append(("ANOM-004","TASK_DEPENDENCY_CYCLE","DEPENDENCY","DPN-ANOM-004","Back-edge creates a cycle in the onboarding task graph"))
            # 5: recovered asset still has an employee assignment.
            aid5="AST-000013"; emp5=active_ids[0]
            conn.execute("UPDATE assets SET asset_status='RECOVERED',assigned_employee_id=?,assigned_at=?,recovered_at=? WHERE asset_id=?",(emp5,TODAY.isoformat(),TODAY.isoformat(),aid5))
            conn.execute("UPDATE asset_assignments SET assignment_status='RETURNED', returned_at=? WHERE asset_id=?",(TODAY.isoformat(),aid5))
            truth.append(("ANOM-005","RECOVERED_ASSET_STILL_ASSIGNED","ASSET",aid5,"Recovered asset still references an active employee assignment"))
            for k,(issue,kind,entity,eid,desc) in enumerate(truth,1): _audit(conn,scale*100+k,entity,eid,"ANOMALY_INJECTED","SYSTEM",f"{issue} {kind}: {desc}")
        conn.commit()
    export_tables(db_path,export_dir)
    export_dir.mkdir(parents=True,exist_ok=True)
    from .validation import run_checks, detect_findings
    with get_connection(db_path) as c:
        row_counts={name:c.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]}
    validation=[{"check":name,"passed":bool(ok),"details":details} for name,ok,details in run_checks(db_path)]
    (export_dir/"validation_summary.json").write_text(json.dumps({"passed":sum(x["passed"] for x in validation),"total":len(validation),"checks":validation,"detected_exception_records":len(detect_findings(db_path))},indent=2),encoding="utf-8")
    manifest={"seed":seed,"scale_employees":scale,"generated_on":TODAY.isoformat(),"database":str(db_path),"row_counts":row_counts,"synthetic_only":True,"provenance":"Synthetic records generated locally; no external datasets or personal data used.","external_sources":[],"anomaly_labels_separate":True}
    (export_dir/"source_manifest.json").write_text(json.dumps(manifest,indent=2))
    if inject_anomalies:
        with (export_dir/"ground_truth.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.writer(f); w.writerow(["issue_id","issue_type","entity_type","entity_id","description"]); w.writerows(truth)
    return {"employees":scale,"seed":seed,"database":str(db_path),"exports":str(export_dir)}

def export_tables(db_path,export_dir):
    import pandas as pd
    export_dir=Path(export_dir); export_dir.mkdir(parents=True,exist_ok=True)
    with get_connection(db_path) as conn:
        names=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        for name in names:
            df=pd.read_sql_query(f'SELECT * FROM "{name}"',conn)
            df.to_csv(export_dir/f"{name}.csv",index=False)
            (export_dir/f"{name}.json").write_text(df.to_json(orient="records",indent=2),encoding="utf-8")
        (export_dir/"database_seed.sql").write_text("\n".join(conn.iterdump()),encoding="utf-8")

def checksum_tree(folder):
    result={}
    for pattern in ("*.csv","*.json","*.sql"):
        for p in sorted(Path(folder).glob(pattern)):
            if p.name=="source_manifest.json": continue
            result[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result

def verify_reproducibility(scale=1000, seed=SEED):
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        base=Path(temp)
        a_db=base/"a.db"; b_db=base/"b.db"
        a_exp=base/"a"; b_exp=base/"b"
        generate(scale,a_db,seed,a_exp,True)
        generate(scale,b_db,seed,b_exp,True)
        a=checksum_tree(a_exp); b=checksum_tree(b_exp)
        return {"reproducible":a==b,"files_compared":len(a),"mismatched_files":sorted(k for k in set(a)|set(b) if a.get(k)!=b.get(k))}

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--scale",type=int,default=1000); p.add_argument("--seed",type=int,default=SEED); p.add_argument("--db",default="data/employee_lifecycle.db"); p.add_argument("--export-dir",default="data/exports"); p.add_argument("--no-anomalies",action="store_true"); p.add_argument("--verify-reproducibility",action="store_true"); a=p.parse_args()
    if a.verify_reproducibility: print(verify_reproducibility(a.scale,a.seed))
    else: print(generate(a.scale,Path(a.db),a.seed,Path(a.export_dir),not a.no_anomalies))
