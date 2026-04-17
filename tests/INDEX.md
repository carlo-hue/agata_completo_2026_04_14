# 🧪 Tests Directory Index

**Last Updated**: 2026-02-20
**Purpose**: Local test scripts for development and debugging
**Status**: ✅ Organized by feature category

---

## Directory Structure

```
tests/
├── gaia/          (19 files) - Gaia catalog cross-matching tests
├── vast/          (0 files) - VAST automation tests [placeholder]
├── tess/          (0 files) - TESS QLP import tests [placeholder]
├── auth/          (0 files) - Authentication tests [placeholder]
├── kb/            (0 files) - Knowledge Base tests [placeholder]
├── catalog/       (0 files) - Catalog integration tests [placeholder]
└── other/         (3 files) - Miscellaneous tests
```

---

## Test Categories

### 🔹 Gaia Cross-Matching Tests (19 files)

These test the Gaia catalog matching algorithm and related functionality:

**Algorithm Testing**:
- `test_gaia_two_stage.py` - Full two-stage matching algorithm
- `test_gaia_manual_search.py` - Manual Gaia match search
- `test_gaia_magnitude_filtering.py` - Gmag < 18 filtering

**Bug Fixes & Debugging**:
- `test_gaia_fix.py` - Initial fix verification
- `test_gaia_fix_30arcsec.py` - 30" radius optimization
- `test_gaia_distance_debug.py` - Distance calculation debugging

**Integration Tests**:
- `test_gaia_vizier.py` - Vizier wrapper integration
- `test_batch_gaia_upload.py` - TAP upload batch processing
- `test_gaia_all_results.py` - Comprehensive result handling
- `test_gaia_lookup.py` - Basic lookup functionality
- `test_single_star_gaia.py` - Single star matching

**Worker & Parallel Tests**:
- `test_gaia_worker.py` - Worker function validation
- `test_worker_only.py` - Isolated worker testing
- `test_worker_out27251.py` - Specific field test (out27251)

**Ambiguity & Manual Correction**:
- `test_ambiguity_detection.py` - Ambiguous match detection
- `test_manual_gaia_endpoint.py` - Manual correction UI backend

**Utilities**:
- `test_distances.py` - Distance calculation validation
- `test_vizier_gaia_wrapper.py` - Vizier client wrapper

---

### 🔹 Other Tests (3 files)

**Bulk Delete Performance**:
- `test_bulk_delete_fix.sh` - Bulk delete shell script
- `test_bulk_delete_performance.py` - Performance measurement

**Debugging**:
- `test_out31321_debug.py` - Debug script for specific field

---

## Placeholder Categories (Ready for Use)

These directories are created but currently empty. Add tests here as needed:

- **vast/** - VAST automation pipeline tests
- **tess/** - TESS QLP import and download tests
- **auth/** - Authentication and OAuth tests
- **kb/** - Knowledge Base and embeddings tests
- **catalog/** - Catalog integration tests

---

## Running Tests

### Run All Gaia Tests
```bash
python tests/gaia/test_gaia_two_stage.py
python tests/gaia/test_vizier_gaia_wrapper.py
```

### Run Specific Test
```bash
python tests/gaia/test_gaia_magnitude_filtering.py
```

### Run All Tests (if using pytest)
```bash
pytest tests/
```

---

## Test Dependencies

Most tests require:
- `astroquery` - For Gaia/Vizier queries
- `astropy` - For astronomical calculations
- Project Flask app running (for endpoint tests)

Check individual test files for specific imports.

---

## Organization Notes

- Tests are organized by **feature/module** not by test framework
- Each test is **self-contained** and can run independently
- Test names follow pattern: `test_<feature>_<description>.py`
- Debugging scripts prefixed with `test_debug_` or `test_out_<fieldname>_`

---

**Created**: 2026-02-20 (final root cleanup)
**Last Updated**: 2026-02-20
**Maintainer**: Development Team
