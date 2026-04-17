# 📦 Archived Documentation

**Purpose**: Reference only. These documents describe completed implementations from January 2026.

---

## 📋 Contents

### `old/` - Completed Features (23 files)

Implementations completed in January 2026. Reference for understanding the feature, but **not** for current development.

**Note**: Includes SQL migration scripts and implementation documentation.

#### Project Detail Implementation (7 files)
- AGATA_PROJECT_DETAIL_IMPLEMENTATION_PLAN.md
- AGATA_PROJECT_DETAIL_DB_ANALYSIS.md
- AGATA_PROJECT_DETAIL_IMPLEMENTATION_COMPLETE.md
- AGATA_PROJECT_DETAIL_QUICK_START.md
- AGATA_IMPLEMENTATION_SUMMARY.md
- AGATA_FRONTEND_IMPLEMENTATION_COMPLETE.md
- README_IMPLEMENTATION.md

**Status**: ✅ Feature complete. If you need to modify the Project Detail view, reference these for implementation details.

#### Feature Implementations (2 files)
- AGATA_CREATE_ASSOCIATION_FEATURE.md
- AGATA_CREATE_PROJECT_FEATURE.md

**Status**: ✅ Both features implemented. Reference if modifying create flows.

#### Gap Analysis (1 file)
- AAAAT_GAP_ANALYSIS.md

**Status**: ✅ Historical. Documents the gap between specification and Jan 2026 implementation.

#### Slack Integration (4 files)
- ASSOCIATIONS_SLACK_CHANNELS.md
- SLACK_INTEGRATION_IMPLEMENTATION.md
- SLACK_PRIVATE_CHANNELS_SETUP.md
- SLACK_WELCOME_MESSAGES.md
- SLACK_CLEANUP_INSTRUCTIONS.md

**Status**: ✅ Slack integration implemented. Reference if modifying channel logic or welcome messages.

#### Miscellaneous (1 file)
- Guida_logging_js.md - Logging best practices (still useful for JavaScript debugging)
- external_catalogs.md - External catalog integration (still active, but moved to general feature docs)

### `auth-old/` - OAuth Setup Iterations (5 files)

These document the OAuth 2.0 setup process and iterations before settling on Google OAuth.

- AUTHENTICATION_AZURE_ANALYSIS.md - Azure AD analysis (not chosen)
- AUTHENTICATION_PROPOSAL.md - OAuth proposal document (superseded)
- GOOGLE_OAUTH_SETUP.md - Basic Google OAuth setup (superseded by AGATA_AUTH_SETUP_GUIDE.md)
- START_AGATA_AUTH.md - Quick start (superseded)
- AGATA_AUTH_INSTALLATION_REPORT.md - Schema installation report (Jan 13, 2026)

**Status**: 🔴 OBSOLETE. Use [AGATA_AUTH_SETUP_GUIDE.md](../auth/AGATA_AUTH_SETUP_GUIDE.md) instead for current auth setup.

### `refactoring-proposals/` - Completed Refactors (1 file)

- REFACTORING_ROUTES_PROPOSAL.md

**Status**: ✅ COMPLETED. The proposal in this file was implemented and is described in [REFACTORING_SUMMARY.md](../refactoring/REFACTORING_SUMMARY.md). Reference this if understanding the refactoring rationale.

---

## 🎯 When to Use Archive

**Do NOT use archive files for**:
- Current setup/installation
- Understanding current implementation
- Making new feature decisions

**DO use archive files for**:
- Understanding historical context
- Seeing what was tried and why
- Reference when modifying completed features
- Gap analysis (what was specified vs. implemented)

---

## 🔗 Active Documentation Map

For current development, use these instead:

| Topic | Active Doc |
|-------|-----------|
| Authentication | [docs/auth/AGATA_AUTH_SETUP_GUIDE.md](../auth/AGATA_AUTH_SETUP_GUIDE.md) |
| Project Detail | [docs/DATABASE_SCHEMA.md](../DATABASE_SCHEMA.md) (projects table) + [docs/ARCHITECTURE.md](../ARCHITECTURE.md) |
| Slack Integration | (No active doc - feature stable) |
| Refactoring | [docs/refactoring/REFACTORING_SUMMARY.md](../refactoring/REFACTORING_SUMMARY.md) |

---

**Archive Date**: 2026-02-02
**Reason**: Documentation organization & cleanup
