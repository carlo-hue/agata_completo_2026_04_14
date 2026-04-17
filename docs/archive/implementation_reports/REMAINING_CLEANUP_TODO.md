# 📋 Remaining Cleanup Tasks (2026-02-20)

**Status**: INCOMPLETE - More files to move
**Priority**: Complete before committing major reorganization

---

## ⏰ To-Do List

### Root-Level Files Still Present (NOT YET HANDLED)
```
/var/www/astrogen/
├── TESTING_QUICK_START.md ← Keep in root (testing reference)
├── test*.* (multiple test-related files) ← MOVE TO: test/
├── [Other root files not in above list?]
```

### Actions Needed

#### 1. 🔍 Identify All Remaining Root Files to Move

**Command to see current state:**
```bash
ls -1 /var/www/astrogen/*.md /var/www/astrogen/test* 2>/dev/null | sort
```

#### 2. 📁 Create Proper Test Directory

```bash
mkdir -p /var/www/astrogen/test
```

#### 3. 📚 Move test-related files

```bash
# Move all test-related files to test/
mv /var/www/astrogen/test*.* /var/www/astrogen/test/
mv /var/www/astrogen/*test*.md /var/www/astrogen/test/
```

#### 4. 🗂️ Organize Test Directory

```bash
# Create subdirectories if needed
mkdir -p /var/www/astrogen/test/gaia
mkdir -p /var/www/astrogen/test/vast
mkdir -p /var/www/astrogen/test/tess
# ... etc
```

#### 5. ✏️ Update Navigation

- Update `INDEX.md` to reference `test/` directory
- Update `CLAUDE.md` to reference test subdirectories
- Create `test/INDEX.md` if multiple test categories

#### 6. ✅ Final Verification

```bash
# Verify root is clean
ls -1 /var/www/astrogen/*.md

# Verify test/ is complete
ls -R /var/www/astrogen/test/
```

#### 7. 📝 Commit

Then commit with message about test directory organization.

---

## 📊 Current Status Summary

| Phase | Status | Files |
|-------|--------|-------|
| Archive setup | ✅ COMPLETE | 52 → docs/archive/ |
| Root cleanup | ✅ PARTIAL | 10 core + 3 nav files |
| Test directory | ❌ TODO | test*.* → test/ |
| Navigation | ✅ PARTIAL | INDEX.md created, but may need test/ ref |
| CLAUDE.md | ✅ UPDATED | Reflects 10 core files |
| Final commit | ❌ BLOCKED | Waiting for test directory |

---

## 🎯 Final Result Target

After all steps:
```
/var/www/astrogen/
├── CLAUDE.md (project context, auto-loaded)
├── INDEX.md (navigation)
├── CLEANUP_SUMMARY.md (documentation of this process)
├── COMMIT_SUMMARY.md (last commit)
├── [10 core implementation .md files]
├── docs/ (main documentation)
│   ├── archive/ (92 historical docs)
│   └── ... (other doc directories)
├── test/ (all test-related files)
│   ├── test-files
│   ├── gaia/ (if needed)
│   ├── vast/ (if needed)
│   └── ... (organized by feature)
└── ... (other project directories)
```

---

## 📌 Notes

- **TESTING_QUICK_START.md** - Keep this in root (it's a reference guide)
- **Test directory** - Should have clear organization matching project features
- **Documentation** - Update INDEX.md and CLAUDE.md after moving test files
- **Git** - Commit only after all files are in final locations

---

**Created**: 2026-02-20
**Reason**: Ensure complete cleanup before final commit
**Next Step**: You handle test directory organization
