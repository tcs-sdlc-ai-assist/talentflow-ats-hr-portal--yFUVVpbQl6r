# Changelog

All notable changes to the TalentFlow ATS project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-01

### Added

#### Authentication & Session Management
- Cookie-based session authentication using signed tokens with configurable expiration
- Secure login and logout endpoints with CSRF protection
- Password hashing using bcrypt for secure credential storage
- Session persistence across browser restarts with remember-me support

#### Role-Based Access Control (RBAC)
- Four distinct user roles with hierarchical permissions:
  - **Admin**: Full system access including user management, all job requisitions, and audit log visibility
  - **Hiring Manager**: Create and manage job requisitions, review candidates, provide interview feedback, and manage application pipeline
  - **Recruiter**: Source and manage candidates, advance applications through pipeline stages, and schedule interviews
  - **Interviewer**: View assigned interviews, submit structured interview feedback, and access candidate profiles for scheduled interviews

#### Job Requisition Management
- Create, edit, and close job requisitions with detailed descriptions
- Track requisition status through lifecycle stages: Draft, Open, On Hold, Closed, Cancelled
- Assign hiring managers and recruiters to requisitions
- Filter and search requisitions by status, department, and location
- Support for requisition metadata including salary range, employment type, and experience level

#### Candidate Management
- Comprehensive candidate profiles with contact information, resume, and work history
- Skill tagging system with many-to-many relationship for flexible candidate-skill associations
- Search and filter candidates by skills, experience, and availability
- Candidate source tracking for recruitment channel analytics
- Bulk candidate import support via structured data entry

#### Application Pipeline
- Multi-stage application pipeline: Applied, Screening, Interview, Offer, Hired, Rejected, Withdrawn
- Kanban board view for visual pipeline management per job requisition
- Drag-and-drop stage transitions with automatic timestamp logging
- Application status history tracking with full audit trail
- Rejection reason capture and candidate communication tracking

#### Interview Scheduling & Feedback
- Schedule interviews with date, time, location, and interviewer assignment
- Support for multiple interview types: Phone Screen, Technical, Behavioral, Panel, Final
- Structured interview feedback forms with rating scales
- Multi-interviewer feedback aggregation per candidate per interview round
- Interview calendar view with conflict detection

#### Role-Specific Dashboards
- **Admin Dashboard**: System-wide metrics, user activity summary, and audit log overview
- **Hiring Manager Dashboard**: Open requisitions, pipeline summary per role, and pending feedback items
- **Recruiter Dashboard**: Active candidates, upcoming interviews, and pipeline stage distribution
- **Interviewer Dashboard**: Assigned upcoming interviews and pending feedback submissions

#### Audit Logging
- Comprehensive audit trail for all state-changing operations
- Logged events include: user authentication, requisition changes, application stage transitions, interview scheduling, and feedback submissions
- Audit entries capture actor, action, target entity, timestamp, and contextual metadata
- Admin-accessible audit log viewer with filtering by date range, actor, and action type