# 🔐 Authentication & Authorization Documentation

**Current Implementation**: OAuth 2.0 with Google

---

## 📚 Active Documentation

Use these files for **current authentication work**:

### Setup & Installation
- **[AGATA_AUTH_SETUP_GUIDE.md](AGATA_AUTH_SETUP_GUIDE.md)** (531 lines)
  - Complete OAuth 2.0 setup walkthrough
  - Google Cloud Console configuration
  - Environment variables
  - Testing procedures
  - Troubleshooting

### Implementation Details
- **[AGATA_AUTH_IMPLEMENTATION_SUMMARY.md](AGATA_AUTH_IMPLEMENTATION_SUMMARY.md)** (369 lines)
  - Database schema (9 tables)
  - SQLAlchemy models
  - API endpoints
  - Session management
  - RBAC roles & permissions
  - Use this when modifying auth logic

### Testing & Verification
- **[TEST_LOGIN_GOOGLE.md](TEST_LOGIN_GOOGLE.md)** (290 lines)
  - Login flow verification
  - Browser testing procedures
  - Success/failure scenarios
  - Debugging common issues

---

## 🗂️ Archived Documentation

These files describe **previous auth iterations** that were **evaluated but not chosen** or **superseded by current implementation**.

See [../archive/auth-old/README.md](../archive/auth-old/README.md) for details.

### Why Archived?

1. **AUTHENTICATION_AZURE_ANALYSIS.md** - Analyzed Azure AD, but chose Google OAuth
2. **AUTHENTICATION_PROPOSAL.md** - Initial OAuth proposal (now implemented)
3. **GOOGLE_OAUTH_SETUP.md** - Basic Google setup (superseded by AGATA_AUTH_SETUP_GUIDE.md)
4. **START_AGATA_AUTH.md** - Quick start (superseded by more detailed guides)
5. **AGATA_AUTH_INSTALLATION_REPORT.md** - Schema installation report from Jan 13, 2026 (historical)

### When to Use Archives

- Understanding why certain technologies were chosen/rejected
- Historical context on OAuth decision-making
- Gap analysis (what was proposed vs. what was implemented)
- **NOT for**: Current setup, implementation, or troubleshooting

---

## 🎯 Quick Reference

### I Need to...

| Task | File | Section |
|------|------|---------|
| **Set up OAuth for the first time** | AGATA_AUTH_SETUP_GUIDE.md | Complete guide |
| **Test if login works** | TEST_LOGIN_GOOGLE.md | All sections |
| **Fix a login issue** | AGATA_AUTH_SETUP_GUIDE.md | Troubleshooting |
| **Understand how roles work** | AGATA_AUTH_IMPLEMENTATION_SUMMARY.md | RBAC section |
| **Modify auth endpoints** | AGATA_AUTH_IMPLEMENTATION_SUMMARY.md | API Endpoints section |
| **Debug a database auth issue** | AGATA_AUTH_IMPLEMENTATION_SUMMARY.md | Database Schema section |
| **Add a new role** | AGATA_AUTH_IMPLEMENTATION_SUMMARY.md | RBAC section |
| **Understand session management** | AGATA_AUTH_IMPLEMENTATION_SUMMARY.md | Session Management section |

---

## 🔑 Key Concepts

### Authentication Method
- **OAuth 2.0** with Google Identity
- Users log in with their Google account
- No local password storage needed

### Authorization Levels
- **superuser**: Full access to all associations and functions
- **admin**: Can manage a specific association
- **reviewer**: Can review data, limited modifications
- **analyst**: Can view and analyze data, no modifications

### Multi-Tenant Architecture
- All user data scoped to `association_id`
- Users can belong to multiple associations
- Role is per-association (same user might be admin in one association, analyst in another)

### Session Management
- Database-backed sessions
- Auto-expiry after inactivity
- Stored in PostgreSQL `sessions` table

---

## 📋 Database Schema (Auth)

See [../DATABASE_SCHEMA.md](../DATABASE_SCHEMA.md) for complete schema.

### Key Tables
- **users** - Google OAuth user profiles
- **sessions** - Active user sessions
- **user_associations** - User-to-association mappings with roles
- **associations** - Organizations/groups
- Plus 5 more support tables for audit & tracking

---

## 🚀 Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Google OAuth | ✅ COMPLETE | Working in production |
| Database schema | ✅ COMPLETE | 9 tables, tested |
| SQLAlchemy models | ✅ COMPLETE | All models implemented |
| API endpoints | ✅ COMPLETE | Login, logout, role check |
| Session management | ✅ COMPLETE | Auto-expiry, cleanup |
| RBAC enforcement | ✅ COMPLETE | All endpoints check roles |
| Multi-tenant scoping | ✅ COMPLETE | All queries filtered by association_id |
| Testing | ✅ COMPLETE | Manual testing procedures documented |

---

## 🔗 Related Documentation

- **Project Architecture**: [../ARCHITECTURE.md](../ARCHITECTURE.md)
- **Database Schema**: [../DATABASE_SCHEMA.md](../DATABASE_SCHEMA.md)
- **Architecture Mapping**: [../ARCHITECTURE_MAP.md](../ARCHITECTURE_MAP.md)
- **Full Documentation Index**: [../INDEX.md](../INDEX.md)

---

## 📞 When You're Stuck

1. **Can't get Google OAuth key?** → AGATA_AUTH_SETUP_GUIDE.md, "Google Cloud Console Setup"
2. **Login not working?** → TEST_LOGIN_GOOGLE.md, "Verify System Readiness"
3. **Role checks failing?** → AGATA_AUTH_IMPLEMENTATION_SUMMARY.md, "RBAC" section
4. **Database error?** → AGATA_AUTH_IMPLEMENTATION_SUMMARY.md, "Database Schema"
5. **Not sure which role to use?** → This file, "Authorization Levels" section

---

**Last Updated**: 2026-02-02
**Status**: All active documentation current as of 2026-02-02
