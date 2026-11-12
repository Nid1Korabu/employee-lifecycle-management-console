import streamlit as st
import pandas as pd
from pathlib import Path
from src.database import get_connection, initialize_database
from src.generator import generate, checksum_tree
from src.validation import run_checks, detect_findings
from src.workflows import complete_task, provision_access, assign_asset, acknowledge_asset, start_offboarding, revoke_employee_access, recover_employee_assets

st.set_page_config(page_title="Employee Lifecycle Console",page_icon="🏢",layout="wide")
st.title("🏢 Employee Lifecycle Management Console")
st.caption("Pre-boarding • approvals • access provisioning • equipment • offboarding • audit")
DB=Path("data/employee_lifecycle.db")
initialize_database(DB)
with st.sidebar:
    st.header("Data controls")
    scale=st.number_input("Employee count",min_value=25,max_value=1000,value=1000,step=25)
    seed=st.number_input("Fixed random seed",min_value=1,value=20261112,step=1)
    if st.button("Generate / regenerate dataset",type="primary",width="stretch"):
        with st.spinner("Generating master data, workflows, events and exports..."):
            result=generate(int(scale),DB,int(seed))
        st.success(f"Generated {result['employees']} employees. Exports: {result['exports']}")
    st.caption("Regeneration replaces the local synthetic demo database.")

with get_connection(DB) as c:
    tables={name:pd.read_sql_query(f'SELECT * FROM "{name}"',c) for name in [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]}
employees=tables.get("employees",pd.DataFrame()); tasks=tables.get("tasks",pd.DataFrame()); grants=tables.get("access_grants",pd.DataFrame()); assets=tables.get("assets",pd.DataFrame()); off=tables.get("offboarding_cases",pd.DataFrame()); audit=tables.get("audit_events",pd.DataFrame())
if employees.empty:
    st.info("Use the sidebar to generate the 1,000-employee synthetic dataset.")
else:
    active=int((employees.employment_status=="ACTIVE").sum()); pre=int((employees.employment_status=="PREBOARDING").sum()); term=int((employees.employment_status=="TERMINATED").sum())
    cols=st.columns(5); cols[0].metric("Employees",len(employees)); cols[1].metric("Active",active); cols[2].metric("Pre-boarding",pre); cols[3].metric("Terminated",term); cols[4].metric("Tasks",len(tasks))
    cols=st.columns(4); cols[0].metric("Access grants",len(grants)); cols[1].metric("Assets",len(assets)); cols[2].metric("Offboarding cases",len(off)); cols[3].metric("Audit events",len(audit))
    tabs=st.tabs(["Overview","Employees & Cases","Tasks & Dependencies","Access & Assets","Actions","Exceptions","Validation & Audit","Exports"])
    with tabs[0]:
        st.subheader("Employee lifecycle overview")
        st.bar_chart(employees.employment_status.value_counts())
        st.write("**Task status distribution**")
        st.bar_chart(tasks.task_status.value_counts())
        st.write("**Ownership across teams**")
        st.bar_chart(tasks.owner_team.value_counts())
    with tabs[1]:
        st.subheader("Employee directory")
        st.dataframe(employees,width="stretch",hide_index=True)
        st.subheader("Onboarding / offboarding cases")
        for name in ["onboarding_cases","offboarding_cases"]:
            st.markdown(f"**{name.replace('_',' ').title()}**"); st.dataframe(tables.get(name,pd.DataFrame()),width="stretch",hide_index=True)
        st.subheader("Role change history"); st.dataframe(tables.get("employee_role_history",pd.DataFrame()),width="stretch",hide_index=True)
    with tabs[2]:
        st.subheader("Workflow tasks")
        if not tasks.empty:
            status=st.multiselect("Filter task status",sorted(tasks.task_status.unique()),default=sorted(tasks.task_status.unique()))
            st.dataframe(tasks[tasks.task_status.isin(status)],width="stretch",hide_index=True)
        st.subheader("Prerequisite edges"); st.dataframe(tables.get("dependencies",pd.DataFrame()),width="stretch",hide_index=True)
    with tabs[3]:
        left,right=st.columns(2)
        with left: st.subheader("Access grants"); st.dataframe(grants,width="stretch",hide_index=True)
        with right: st.subheader("Asset inventory"); st.dataframe(assets,width="stretch",hide_index=True)
        st.subheader("Asset assignment history"); st.dataframe(tables.get("asset_assignments",pd.DataFrame()),width="stretch",hide_index=True)
    with tabs[4]:
        st.subheader("Execute workflow actions")
        active_options=employees[employees.employment_status=="ACTIVE"].employee_id.tolist()
        available_assets=assets[assets.asset_status=="AVAILABLE"].asset_id.tolist()
        pending_tasks=tasks[tasks.task_status!="COMPLETED"].task_id.tolist()
        action_tabs=st.tabs(["Complete task","Provision access","Assign / acknowledge equipment","Start offboarding","Exit controls"])
        with action_tabs[0]:
            if pending_tasks:
                selected_task=st.selectbox("Task",pending_tasks,key="complete_task_id")
                if st.button("Mark task completed",key="complete_task_btn"):
                    try: complete_task(selected_task); st.success("Task completed; audit event recorded."); st.rerun()
                    except ValueError as exc: st.error(str(exc))
        with action_tabs[1]:
            if active_options:
                emp=st.selectbox("Active employee",active_options,key="grant_emp")
                roles_df=tables.get("access_roles",pd.DataFrame())
                role_map=dict(zip(roles_df.access_role_id,roles_df.role_name)) if not roles_df.empty else {}
                if role_map:
                    ar=st.selectbox("Access role",list(role_map),format_func=lambda x: f"{x} — {role_map[x]}",key="grant_role")
                    approved=st.checkbox("Manager approval obtained",key="manager_approved")
                    if st.button("Provision access",key="provision_btn"):
                        try: gid=provision_access(emp,ar,approved); st.success(f"Created {gid}"); st.rerun()
                        except ValueError as exc: st.error(str(exc))
        with action_tabs[2]:
            if active_options and available_assets:
                emp=st.selectbox("Employee",active_options,key="asset_emp")
                aid=st.selectbox("Available asset",available_assets,key="asset_id")
                if st.button("Assign equipment",key="assign_asset_btn"):
                    try: assignment=assign_asset(emp,aid); st.success(f"Created assignment {assignment}"); st.rerun()
                    except ValueError as exc: st.error(str(exc))
            active_assign=tables.get("asset_assignments",pd.DataFrame())
            if not active_assign.empty:
                active_assign=active_assign[active_assign.assignment_status=="ACTIVE"]
                if not active_assign.empty:
                    st.markdown("**Employee acknowledgement**")
                    ack_row=st.selectbox("Active assignment",active_assign.assignment_id.tolist(),key="ack_assignment")
                    chosen=active_assign[active_assign.assignment_id==ack_row].iloc[0]
                    if st.button("Record acknowledgement",key="ack_btn"):
                        try: acknowledge_asset(chosen.asset_id,chosen.employee_id); st.success("Acknowledgement recorded."); st.rerun()
                        except ValueError as exc: st.error(str(exc))
        with action_tabs[3]:
            if active_options:
                emp=st.selectbox("Employee to offboard",active_options,key="off_emp")
                reason=st.text_input("Reason",value="Voluntary separation",key="off_reason")
                if st.button("Start offboarding",key="offboard_btn"):
                    try: case=start_offboarding(emp,reason); st.success(f"Created {case} and exit tasks."); st.rerun()
                    except ValueError as exc: st.error(str(exc))
        with action_tabs[4]:
            terminated=employees[employees.employment_status=="TERMINATED"].employee_id.tolist()
            if terminated:
                emp=st.selectbox("Terminated employee",terminated,key="exit_emp")
                if st.button("Revoke all active access",key="revoke_btn"):
                    count=revoke_employee_access(emp); st.success(f"Revoked {count} access grant(s)."); st.rerun()
                if st.button("Recover assigned equipment",key="recover_btn"):
                    count=recover_employee_assets(emp); st.success(f"Recovered {count} asset(s)."); st.rerun()
    with tabs[5]:
        st.subheader("Rule-based exception detection")
        findings=detect_findings()
        st.metric("Detected exception records",len(findings))
        if findings: st.dataframe(pd.DataFrame(findings),width="stretch",hide_index=True)
        else: st.success("No exceptions detected.")
        st.caption("Detectors query operational records only. Ground-truth labels are stored separately in data/exports/ground_truth.csv and are not detector inputs.")
    with tabs[6]:
        checks=run_checks(); st.metric("Structural checks passed",f"{sum(x[1] for x in checks)}/{len(checks)}")
        st.dataframe(pd.DataFrame(checks,columns=["Check","Passed","Details"]),width="stretch",hide_index=True)
        st.subheader("Audit trail"); st.dataframe(audit.sort_values("event_time",ascending=False),width="stretch",hide_index=True)
    with tabs[7]:
        st.write("CSV and JSON exports are written to `data/exports/` on generation.")
        export=Path("data/exports")
        if export.exists():
            files=sorted(p for p in export.iterdir() if p.is_file())
            st.write(f"{len(files)} export / manifest files")
            for p in files:
                if p.suffix==".csv": st.download_button(f"Download {p.name}",p.read_bytes(),file_name=p.name,mime="text/csv")
                elif p.suffix==".json": st.download_button(f"Download {p.name}",p.read_bytes(),file_name=p.name,mime="application/json")
st.divider(); st.caption("Synthetic demonstration data only. No real employee personal data is used.")
