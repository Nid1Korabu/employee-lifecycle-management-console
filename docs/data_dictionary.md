# Data dictionary, relationships and validation rules

All IDs are immutable text primary keys. Dates use ISO `YYYY-MM-DD`; timestamps in this synthetic prototype also use ISO date strings. `example.test` emails and serial numbers are synthetic. Required means `NOT NULL`; optional means nullable.

## Core entities and field dictionary

### Department (`departments`)
| Field | Type | Required? | Allowed values / unit | Unique? | Validation |
|---|---|---:|---|---:|---|
| department_id | TEXT | Yes | `DEP-NNN` | PK | Must reference an existing department |
| name | TEXT | Yes | Organization department name | Yes | Non-empty |

### Role (`roles`)
| Field | Type | Required? | Allowed values / unit | Unique? | Validation |
|---|---|---:|---|---:|---|
| role_id | TEXT | Yes | `ROL-NNN` | PK | Immutable |
| title | TEXT | Yes | Role title | No | Non-empty |
| access_role_id | TEXT | Yes | Access role ID | No | FK to `access_roles` |

### Manager (`managers`)
| Field | Type | Required? | Allowed values / unit | Unique? | Validation |
|---|---|---:|---|---:|---|
| manager_id | TEXT | Yes | `MGR-NNN` | PK | Immutable |
| full_name | TEXT | Yes | Synthetic name | No | Non-empty |
| email | TEXT | Yes | `@example.test` | Yes | Synthetic email format |
| department_id | TEXT | Yes | Department ID | No | FK to `departments` |

### Employee (`employees`)
| Field | Type | Required? | Allowed values / unit | Unique? | Validation |
|---|---|---:|---|---:|---|
| employee_id | TEXT | Yes | `EMP-NNNNNN` | PK | Immutable, zero-padded |
| full_name | TEXT | Yes | Synthetic name | No | Non-empty |
| email | TEXT | Yes | `@example.test` | Yes | Unique synthetic email |
| employment_type | TEXT | Yes | `FULL_TIME`, `CONTRACTOR` | No | SQLite CHECK |
| employment_status | TEXT | Yes | `PREBOARDING`, `ACTIVE`, `TERMINATED` | No | SQLite CHECK; reconciled with dates and grants |
| role_id | TEXT | Yes | Role ID | No | FK to `roles` |
| department_id | TEXT | Yes | Department ID | No | FK to `departments` |
| manager_id | TEXT | No | Manager ID | No | Optional FK to `managers` |
| start_date | TEXT | Yes | ISO date | No | Must be valid date |
| end_date | TEXT | No | ISO date | No | If present, must be on/after start date |

### OnboardingCase (`onboarding_cases`)
| Field | Type | Required? | Allowed values / unit | Unique? | Validation |
|---|---|---:|---|---:|---|
| onboarding_case_id | TEXT | Yes | `ONB-YYYY-NNNNNN` | PK | Deterministic ID |
| employee_id | TEXT | Yes | Employee ID | Yes | FK to `employees`; one onboarding case per employee |
| case_status | TEXT | Yes | `NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`, `ON_HOLD` | No | SQLite CHECK |
| created_at | TEXT | Yes | ISO date | No | Valid date |

### Task (`tasks`)
| Field | Type | Required? | Allowed values / unit | Unique? | Validation |
|---|---|---:|---|---:|---|
| task_id | TEXT | Yes | `TASK-<case-id>-NNN` | PK | Deterministic ID |
| case_id | TEXT | Yes | Parent case ID | No | Display/reference key |
| task_type | TEXT | Yes | Named workflow step | No | Non-empty |
| owner_team | TEXT | Yes | `HR`, `MANAGER`, `IT`, `FACILITIES`, `SYSTEM` | No | SQLite CHECK |
| task_status | TEXT | Yes | `PENDING`, `IN_PROGRESS`, `COMPLETED`, `BLOCKED` | No | SQLite CHECK; completion requires prerequisites |
| due_date | TEXT | No | ISO date | No | Valid date when present |
| completed_at | TEXT | No | ISO date | No | Set when completed |
| onboarding_case_id | TEXT | No | Onboarding case ID | No | Optional FK to onboarding case |
| offboarding_case_id | TEXT | No | Offboarding case ID | No | Optional FK to offboarding case; one case FK required |

### Dependency (`dependencies`)
| Field | Type | Required? | Allowed values / unit | Unique? | Validation |
|---|---|---:|---|---:|---|
| dependency_id | TEXT | Yes | `DPN-NNNNNN-NNN` | PK | Immutable |
| predecessor_task_id | TEXT | Yes | Task ID | Composite unique with successor | FK to `tasks`; not equal to successor |
| successor_task_id | TEXT | Yes | Task ID | Composite unique with predecessor | FK to `tasks`; graph cycle detector checks DAG rule |

### AccessRole (`access_roles`)
| Field | Type | Required? | Allowed values / unit | Unique? | Validation |
|---|---|---:|---|---:|---|
| access_role_id | TEXT | Yes | `AR-NNN` | PK | Immutable |
| role_name | TEXT | Yes | Named access bundle | Yes | Non-empty |
| description | TEXT | No | Text | No | Optional explanation |

### AccessGrant (`access_grants`)
| Field | Type | Required? | Allowed values / unit | Unique? | Validation |
|---|---|---:|---|---:|---|
| grant_id | TEXT | Yes | `GRANT-<employee-id>-NNN` | PK | Immutable |
| employee_id | TEXT | Yes | Employee ID | No | FK to `employees` |
| access_role_id | TEXT | Yes | Access role ID | No | FK to `access_roles` |
| granted_at | TEXT | Yes | ISO date | No | Must not precede start date |
| approved_by | TEXT | No | Actor / manager identifier | No | Required by provisioning action |
| approval_status | TEXT | Yes | `PENDING`, `APPROVED`, `REJECTED` | No | SQLite CHECK; provisioning requires approved manager flag |
| revoked_at | TEXT | No | ISO date | No | Active grants have null revoked_at |

### Asset (`assets`)
| Field | Type | Required? | Allowed values / unit | Unique? | Validation |
|---|---|---:|---|---:|---|
| asset_id | TEXT | Yes | `AST-NNNNNN` | PK | Immutable |
| asset_type | TEXT | Yes | `LAPTOP`, `MOBILE` | No | Non-empty category |
| serial_number | TEXT | Yes | Synthetic serial | Yes | Unique inventory serial |
| asset_status | TEXT | Yes | `AVAILABLE`, `ASSIGNED`, `RECOVERED` | No | SQLite CHECK; reconcile current assignment |
| assigned_employee_id | TEXT | No | Employee ID | No | Optional FK to `employees` |
| assigned_at | TEXT | No | ISO date | No | Set on assignment |
| recovered_at | TEXT | No | ISO date | No | Set on recovery |

### OffboardingCase (`offboarding_cases`)
| Field | Type | Required? | Allowed values / unit | Unique? | Validation |
|---|---|---:|---|---:|---|
| offboarding_case_id | TEXT | Yes | `OFF-YYYY-NNNNNN` | PK | Deterministic ID |
| employee_id | TEXT | Yes | Employee ID | Yes | FK to `employees`; one case per employee |
| termination_date | TEXT | Yes | ISO date | No | Valid date |
| reason | TEXT | No | Free text | No | Optional business reason |
| case_status | TEXT | Yes | `OPEN`, `IN_PROGRESS`, `COMPLETED` | No | SQLite CHECK |

### AuditEvent (`audit_events`)
| Field | Type | Required? | Allowed values / unit | Unique? | Validation |
|---|---|---:|---|---:|---|
| audit_event_id | TEXT | Yes | `AUD-<stable-hash>` | PK | Deterministic event key |
| entity_type | TEXT | Yes | Entity/table name | No | Non-empty |
| entity_id | TEXT | Yes | Related entity ID | No | Polymorphic reference; entity is recorded in details |
| action | TEXT | Yes | `CREATED`, `COMPLETED`, `PROVISIONED`, `REVOKED`, `ASSIGNED`, `ACKNOWLEDGED`, `RECOVERED`, `TERMINATED`, etc. | No | Non-empty |
| actor | TEXT | Yes | `HR`, `IT`, `FACILITIES`, `MANAGER`, `SYSTEM`, `EMPLOYEE` | No | Non-empty |
| event_time | TEXT | Yes | ISO date | No | Valid date |
| details | TEXT | No | Human-readable explanation | No | Optional context |

## Supporting bridge/history tables

- `employee_role_history(history_id PK, employee_id FK, old_role_id FK nullable, new_role_id FK, effective_date, changed_by)` preserves role-change history.
- `asset_assignments(assignment_id PK, asset_id FK, employee_id FK, assigned_at, returned_at nullable, assignment_status, acknowledged_at nullable)` is the N:M assignment/history bridge between employees and assets. At most one ACTIVE assignment per asset is allowed.

## Cardinality and lifecycle

- Department 1:N Manager and Employee; Role 1:N Employee; AccessRole 1:N Role and AccessGrant.
- Manager 1:N Employee; Employee 1:1 OnboardingCase and optional 1:1 OffboardingCase.
- OnboardingCase / OffboardingCase 1:N Task. Task prerequisites are N:M through Dependency.
- Employee N:M Asset over time through AssetAssignment; the assignment history stores returned and acknowledged states.
- Employee 1:N AccessGrant and AuditEvent records. AuditEvent is append-oriented history; the entity reference is polymorphic.
- Access provisioning requires manager approval, active employment and a start date that has arrived. Non-revoked grants must reconcile to active employment.
- A task cannot be completed until all predecessor tasks are complete. The dependency graph must be acyclic.
- An asset must have at most one active assignment. A recovered asset must not retain a current employee assignment.
- Offboarding creates manager approval, access revocation, equipment recovery and badge-return tasks. Revocation and recovery actions append audit events.

## Synthetic data and labels

No external dataset is used. All people, emails and serial numbers are synthetic. `ground_truth.csv` is an evaluation-only export; it is never stored in the operational SQLite database and is never read by the anomaly detectors.
