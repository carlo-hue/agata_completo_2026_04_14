# 📚 Astrogen Documentation Index

**Active Documentation** - Use these files for current development.

**Last Updated**: 2026-02-02

---

## 📋 Changelog & Storico

| File | Purpose |
|------|---------|
| [CHANGELOG.md](CHANGELOG.md) | Storico completo versioni dalla nascita del progetto (Apr 2025 → oggi) |

---

## 🏗️ Architecture & Core Design

Start here to understand the project structure and design principles.

| File | Purpose | Key Topics |
|------|---------|-----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Normative architecture document | Boundaries, responsibilities, module organization, RBAC, multi-tenant design |
| [ARCHITECTURE_MAP.md](ARCHITECTURE_MAP.md) | Maps architecture to repository structure | Directory layout, blueprint organization, service patterns |
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | Complete PostgreSQL schema (authoritative) | 50+ tables, relationships, FK constraints, triggers, stored procedures, views |

**When to use**: Before adding features, modifying DB, or understanding project structure.

---

## 🔐 Authentication & Authorization

OAuth 2.0 integration with role-based access control.

| File | Purpose | Key Topics |
|------|---------|-----------|
| [auth/AGATA_AUTH_SETUP_GUIDE.md](auth/AGATA_AUTH_SETUP_GUIDE.md) | Complete OAuth 2.0 setup guide | Google OAuth config, environment variables, testing, troubleshooting |
| [auth/AGATA_AUTH_IMPLEMENTATION_SUMMARY.md](auth/AGATA_AUTH_IMPLEMENTATION_SUMMARY.md) | Implementation details | Database schema, SQLAlchemy models, endpoints, session management, RBAC roles |
| [auth/TEST_LOGIN_GOOGLE.md](auth/TEST_LOGIN_GOOGLE.md) | Testing guide | Verification steps, browser testing, login flow validation |

**When to use**: Setting up auth, debugging login issues, understanding RBAC, modifying auth logic.

---

## 🤖 AI & Knowledge Base

Knowledge Base with semantic search + AI Advisor for intelligent recommendations.

### Knowledge Base Setup

| File | Purpose | Key Topics |
|------|---------|-----------|
| [KNOWLEDGE_BASE_SETUP.md](KNOWLEDGE_BASE_SETUP.md) | KB architecture & setup | MBOX parsing, embeddings, search backend, provider configuration |
| [../INIZIA_QUI.md](../INIZIA_QUI.md) | Quick start: Voyage AI setup | 5-step setup with Voyage AI (Anthropic's embedding service) |
| [../INIZIA_QUI_SENTENCE_TRANSFORMERS.md](../INIZIA_QUI_SENTENCE_TRANSFORMERS.md) | Quick start: Free local embeddings | 3-command setup with Sentence Transformers (100% free, local) |
| [../KB_README.md](../KB_README.md) | KB overview | Features, usage, performance, architecture |
| [../KNOWLEDGE_BASE_NO_OPENAI.md](../KNOWLEDGE_BASE_NO_OPENAI.md) | Embedding provider comparison | Voyage AI vs Sentence Transformers vs Cerebras (pro/con analysis) |
| [../VOYAGE_AI_SETUP.md](../VOYAGE_AI_SETUP.md) | Voyage AI detailed setup | API keys, free tier (100M tokens/month), configuration |

**When to use**: Setting up KB, choosing embedding provider, implementing semantic search, understanding KB architecture.

### AI Advisor

| File | Purpose | Key Topics |
|------|---------|-----------|
| [ai/AI_ADVISOR_IMPLEMENTATION.md](ai/AI_ADVISOR_IMPLEMENTATION.md) | Complete AI Advisor implementation | Backend endpoints, frontend UI, Claude API integration, testing |
| [ai/QUICK_START_AI.md](ai/QUICK_START_AI.md) | 5-minute quick start | Cerebras setup (free), environment variables, testing |
| [ai/CEREBRAS_SETUP.md](ai/CEREBRAS_SETUP.md) | Cerebras API setup | API keys, free tier (unlimited), Llama 3.3 70B model, OpenAI-compatible API |
| [ai/TEST_AI_ADVISOR.md](ai/TEST_AI_ADVISOR.md) | Testing procedures | Cerebras (free) vs Claude (paid), test endpoints, validation |

**When to use**: Setting up AI Advisor, choosing model provider, implementing AI features, testing AI responses.

---

## 🌟 Variable Stars Analysis

Light curve analysis, phase analysis, stellar classification.

| File | Purpose | Key Topics |
|------|---------|-----------|
| [../VARIABILITY_ANALYSIS_README.md](../VARIABILITY_ANALYSIS_README.md) | API documentation for variability analysis | Multi-catalog queries, phase analysis, χ² fitting, caching |
| [../VARIABILITY_COMPARISON_USER_GUIDE.md](../VARIABILITY_COMPARISON_USER_GUIDE.md) | End-user guide | "Analisi Comparativa" tab, finding similar stars, comparing light curves |
| [../INSTALLATION_VARIABILITY_ANALYSIS.md](../INSTALLATION_VARIABILITY_ANALYSIS.md) | Setup & installation | Prerequisites, dependencies, configuration |
| [../agata/admin/README.md](../agata/admin/README.md) | Admin module docs | RBAC, audit trail, multi-association management |

**When to use**: Implementing variability features, setting up analysis tools, understanding the admin module.

---

## 🔧 Performance & Optimization

Caching, memory management, and optimization strategies.

| File | Purpose | Key Topics |
|------|---------|-----------|
| [../MEMORY_OPTIMIZATION.md](../MEMORY_OPTIMIZATION.md) | Memory optimization strategies | EmbeddingService singleton, lazy loading, model caching |
| [../REDIS_CACHING_GUIDE.md](../REDIS_CACHING_GUIDE.md) | Redis caching implementation | VSX analog caching, TTL policies, performance benefits |
| [SLOW_QUERY_LOG_SETUP.md](SLOW_QUERY_LOG_SETUP.md) | Database slow query analysis | MariaDB slow log, analysis tools, optimization priorities |

**When to use**: Improving performance, debugging memory issues, implementing caching, optimizing queries.

---

## 🌐 External Data Integration

Integration with astronomical catalogs and data sources.

| File | Purpose | Key Topics |
|------|---------|-----------|
| [../COORDINATE_AUTO_FETCH_UPDATE.md](../COORDINATE_AUTO_FETCH_UPDATE.md) | Automatic coordinate fetching | Gaia DR3 integration, resolve_gaia_coordinates(), missing coordinate handling |
| [../CHANGES_ASSOCIATION_ID_OWNER.md](../CHANGES_ASSOCIATION_ID_OWNER.md) | Multi-tenant catalog visibility | Association-level data scoping, external catalog ownership |

**When to use**: Adding catalog integrations, understanding data fetching, implementing multi-tenant data access.

---

## 📖 Code Guidelines

Prompt templates and best practices.

| File | Purpose | Key Topics |
|------|---------|-----------|
| [../docs/AGATA_LOW_COST_PROMPT_TEMPLATE_COMPACT.md](../docs/AGATA_LOW_COST_PROMPT_TEMPLATE_COMPACT.md) | Compact prompt guidelines | Token efficiency, required headers, working with Claude AI |
| [../docs/AGATA_LOW_COST_PROMPT_TEMPLATE.md](../docs/AGATA_LOW_COST_PROMPT_TEMPLATE.md) | Full prompt guidelines | Detailed token-saving strategies, consistency rules |

**When to use**: Writing AI prompts, modifying Claude instructions, understanding project conventions.

---

## 🔄 Refactoring & Architectural Changes

Documentation of major refactoring efforts.

| File | Purpose | Key Topics |
|------|---------|-----------|
| [refactoring/REFACTORING_SUMMARY.md](refactoring/REFACTORING_SUMMARY.md) | Summary of completed refactoring | Variable stars module refactoring (2210 lines → 9 modular files) |

**When to use**: Understanding refactoring rationale, maintaining modularity, improving code organization.

---

## 📂 Module-Specific Documentation

Deep dives into specific modules.

| File | Path | Purpose |
|------|------|---------|
| [../agata/variable_stars/STRUCTURE.md](../agata/variable_stars/STRUCTURE.md) | agata/variable_stars/ | Module structure after refactoring |
| [../agata/variable_stars/AI_ADVISOR_README.md](../agata/variable_stars/AI_ADVISOR_README.md) | agata/variable_stars/ | AI Advisor setup & configuration |
| [../agata/exoplanets/workflow_exoclock.md](../agata/exoplanets/workflow_exoclock.md) | agata/exoplanets/ | ESO ExoClock workflow integration |
| [../agata/static/js/variable_stars/REFACTORING-PHASE.md](../agata/static/js/variable_stars/REFACTORING-PHASE.md) | agata/static/js/variable_stars/ | JavaScript phase analysis module refactoring |

**When to use**: Working on specific modules, understanding module structure, improving modular code.

---

## 📦 Archived Documentation

Historical reference (completed features from January 2026).

See [archive/README.md](archive/README.md) for details.

**When to use**: Understanding historical implementation, gap analysis, learning from completed work.

**Do NOT use for**: Current setup, new features, implementation decisions.

---

## 🎯 Common Workflows

### Setting Up a Fresh Development Environment
1. [ARCHITECTURE.md](ARCHITECTURE.md) - Understand the project
2. [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - Understand the data model
3. [auth/AGATA_AUTH_SETUP_GUIDE.md](auth/AGATA_AUTH_SETUP_GUIDE.md) - Set up authentication
4. [KNOWLEDGE_BASE_SETUP.md](KNOWLEDGE_BASE_SETUP.md) (optional) - Set up Knowledge Base
5. [ai/AI_ADVISOR_IMPLEMENTATION.md](ai/AI_ADVISOR_IMPLEMENTATION.md) (optional) - Set up AI Advisor

### Adding a New Feature
1. [ARCHITECTURE.md](ARCHITECTURE.md) - Check boundaries & patterns
2. [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - Design DB schema if needed
3. [../docs/AGATA_LOW_COST_PROMPT_TEMPLATE_COMPACT.md](../docs/AGATA_LOW_COST_PROMPT_TEMPLATE_COMPACT.md) - Follow prompt guidelines
4. Module-specific docs (e.g., [../VARIABILITY_ANALYSIS_README.md](../VARIABILITY_ANALYSIS_README.md))

### Debugging Authentication Issues
1. [auth/AGATA_AUTH_SETUP_GUIDE.md](auth/AGATA_AUTH_SETUP_GUIDE.md) - Verify setup
2. [auth/TEST_LOGIN_GOOGLE.md](auth/TEST_LOGIN_GOOGLE.md) - Test login flow
3. [auth/AGATA_AUTH_IMPLEMENTATION_SUMMARY.md](auth/AGATA_AUTH_IMPLEMENTATION_SUMMARY.md) - Understand implementation

### Performance Issues
1. [SLOW_QUERY_LOG_SETUP.md](SLOW_QUERY_LOG_SETUP.md) - Analyze slow queries (MySQL)
2. [../MEMORY_OPTIMIZATION.md](../MEMORY_OPTIMIZATION.md) - Check memory usage
3. [../REDIS_CACHING_GUIDE.md](../REDIS_CACHING_GUIDE.md) - Implement/verify caching
4. [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - Check query performance & indexes

### Working with AI Features
1. [ai/AI_ADVISOR_IMPLEMENTATION.md](ai/AI_ADVISOR_IMPLEMENTATION.md) - Implementation details
2. [ai/TEST_AI_ADVISOR.md](ai/TEST_AI_ADVISOR.md) - Testing procedures
3. [../docs/AGATA_LOW_COST_PROMPT_TEMPLATE_COMPACT.md](../docs/AGATA_LOW_COST_PROMPT_TEMPLATE_COMPACT.md) - Prompt guidelines

---

## 📊 Documentation Stats

- **Active docs**: 28 files
- **Archived docs**: 20 files (reference only)
- **Total pages**: ~2,000 pages of documentation
- **Last updated**: 2026-02-18 (slow query log added)

---

## 🔗 Quick Links

- **Project Root**: [README.md](../README.md)
- **Claude Context**: [CLAUDE.md](../CLAUDE.md) (auto-loaded by Claude Code)
- **Database Schema**: [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md) + [ARCHITECTURE_MAP.md](ARCHITECTURE_MAP.md)

---

**Note**: This index is maintained in parallel with [CLAUDE.md](../CLAUDE.md). CLAUDE.md is auto-loaded by Claude Code CLI and contains the same essential information in a more concise format.
