# AI Assistant / TopSport Search Engine — Architecture Notes

## Core principle

Search decides → Business rules decide → LLM speaks.

LLM must not:
- build SQL
- choose products
- decide availability
- rank products
- make business decisions

LLM may only:
- explain results
- format natural language response
- clarify user intent

## Current architecture goal

Build a production-like conversational product search backend for a large product catalog.

The system must support:
- deterministic search logic
- conversational follow-up
- task lifecycle
- strategy-based retrieval
- analytics and observability
- future async DB layer
- future Alembic migrations
- future Redis/Docker/Postgres setup

## Current layers

### ChatUseCase

Role:
- entry orchestration
- receives user message
- resolves active conversation task
- calls search
- builds final response

Should not:
- contain DB persistence logic
- contain state mapping logic
- contain raw task lifecycle rules

### conversation_service.py

Role:
- conversation behavior
- transition logic
- continue/restart/duplicate decision
- merge active task with new user message

Still to improve:
- move transition engine later to task_transition_service.py
- move query merge logic later to conversation_merge_service.py

### task_state_service.py

Role:
- maps search result modes to task states

Examples:
- result_mode → current_step
- result_mode → pending_clarification
- result_mode → should_create_followup_task

This file is the single source of truth for task state mapping.

### task_flow_service.py

Role:
- manages task flow operations
- creates follow-up task
- updates session context
- uses task_state_service

This layer hides task orchestration details from ChatUseCase.

### conversation_lifecycle_service.py

Role:
- lifecycle expiration logic
- determines whether task is expired

Example:
- active task older than 15 minutes expires

### conversation_repository.py

Role:
- database persistence for conversation/session/task data

Already contains:
- get active session
- create session
- create search task record
- get latest active task
- update search task record

Repository should contain:
- db.query
- db.add
- db.commit
- db.refresh

Service should not directly manage SQLAlchemy persistence when avoidable.

## State contracts

Use enums instead of raw strings.

Current enums:
- TaskStatus
- TaskStep
- TaskTransition
- SearchResultMode
- PendingClarification

Reason:
- prevents typo bugs
- improves IDE support
- creates explicit state contracts
- makes refactoring safer
- keeps DB values stable through `.value`

## Current tested flows

### Follow-up size refinement

User:
- nike women 39
- 40

Expected:
- first query creates task
- second query is continue_task
- final query becomes nike women 40
- strategy remains brand_size

### Broad query refinement

User:
- nike
- running

Expected:
- first query creates broad/refinement task
- second message continues task
- system does not restart unnecessarily

### Restart task

User:
- nike women 39
- adidas running

Expected:
- second message is restart_task
- old context is not merged
- query becomes adidas running

## Important future cleanup tasks

### 1. Continue repository cleanup

Move remaining DB persistence from conversation_service.py to conversation_repository.py:

- complete_search_task
- expired task update logic, if we decide persistence belongs fully in repository
- session context update, if needed

Keep lifecycle decision itself in service.

### 2. Extract transition engine

Potential file:

```text
app/services/task_transition_service.py