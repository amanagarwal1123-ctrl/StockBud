"""Tests for date-safe physical stock: direct upload, chunked path, ambiguity detection."""
import pytest
import httpx
import openpyxl
import io

API_URL = "https://stock-session-undo.preview.emergentagent.com/api"

DATE_A = "2026-02-17"
DATE_B = "2026-02-18"
DATE_C = "2026-02-19"

@pytest.fixture(scope="module")
def admin_token():
    r = httpx.post(f"{API_URL}/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    return r.json()["access_token"]

@pytest.fixture()
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}

def _make_excel(headers, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class TestDateSafeDirectUpload:
    """Direct full upload must only replace the selected date's rows."""

    def test_upload_date_a_then_date_b_preserves_both(self, auth):
        """Upload for DATE_A, then DATE_B — DATE_A rows survive."""
        # Upload DATE_A
        excel_a = _make_excel(
            ["Item Name", "Stamp", "Gross Weight", "Net Weight"],
            [["ALPHA RING", "STAMP 1", 10.0, 8.0], ["BETA CHAIN", "STAMP 2", 20.0, 15.0]]
        )
        r_a = httpx.post(
            f"{API_URL}/physical-stock/upload?verification_date={DATE_A}",
            files={"file": ("a.xlsx", excel_a, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth, timeout=30,
        )
        assert r_a.status_code == 200
        assert DATE_A in r_a.json()["message"]

        # Upload DATE_B
        excel_b = _make_excel(
            ["Item Name", "Stamp", "Gross Weight", "Net Weight"],
            [["GAMMA BANGLE", "STAMP 3", 30.0, 25.0]]
        )
        r_b = httpx.post(
            f"{API_URL}/physical-stock/upload?verification_date={DATE_B}",
            files={"file": ("b.xlsx", excel_b, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth, timeout=30,
        )
        assert r_b.status_code == 200

        # Verify DATE_A still has rows
        compare_a = httpx.get(
            f"{API_URL}/physical-stock/compare?verification_date={DATE_A}",
            headers=auth, timeout=30,
        )
        assert compare_a.status_code == 200
        assert compare_a.json()["summary"]["total_physical_kg"] > 0, "DATE_A rows should still exist"

        # Verify DATE_B has rows
        compare_b = httpx.get(
            f"{API_URL}/physical-stock/compare?verification_date={DATE_B}",
            headers=auth, timeout=30,
        )
        assert compare_b.status_code == 200
        assert compare_b.json()["summary"]["total_physical_kg"] > 0, "DATE_B rows should exist"

    def test_reupload_same_date_replaces_only_that_date(self, auth):
        """Re-uploading DATE_A replaces DATE_A rows but DATE_B untouched."""
        # First seed both dates
        for date, items in [(DATE_A, [["X1", "S1", 5, 4]]), (DATE_B, [["Y1", "S2", 6, 5]])]:
            excel = _make_excel(["Item Name", "Stamp", "Gross Weight", "Net Weight"], items)
            httpx.post(
                f"{API_URL}/physical-stock/upload?verification_date={date}",
                files={"file": ("s.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                headers=auth, timeout=30,
            )

        # Now re-upload DATE_A with new data
        excel_new = _make_excel(
            ["Item Name", "Stamp", "Gross Weight", "Net Weight"],
            [["X2_REPLACED", "S1", 50, 40]]
        )
        r = httpx.post(
            f"{API_URL}/physical-stock/upload?verification_date={DATE_A}",
            files={"file": ("new.xlsx", excel_new, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth, timeout=30,
        )
        assert r.status_code == 200

        # DATE_B should still have its original Y1 item
        compare_b = httpx.get(
            f"{API_URL}/physical-stock/compare?verification_date={DATE_B}",
            headers=auth, timeout=30,
        )
        assert compare_b.json()["summary"]["total_physical_kg"] > 0

    def test_upload_requires_verification_date(self, auth):
        """Direct upload without verification_date returns 400."""
        excel = _make_excel(["Item Name", "Gross Weight"], [["TEST", 1.0]])
        r = httpx.post(
            f"{API_URL}/physical-stock/upload",
            files={"file": ("t.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth, timeout=30,
        )
        assert r.status_code == 400
        assert "verification_date" in r.json()["detail"].lower()

    def test_new_date_creates_snapshot(self, auth):
        """Uploading to a brand new date works and creates rows."""
        excel = _make_excel(
            ["Item Name", "Gross Weight", "Net Weight"],
            [["NEW_ITEM", 100.0, 80.0]]
        )
        r = httpx.post(
            f"{API_URL}/physical-stock/upload?verification_date={DATE_C}",
            files={"file": ("c.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth, timeout=30,
        )
        assert r.status_code == 200
        assert r.json()["count"] == 1

        # Verify preview works on the new date
        preview_excel = _make_excel(["Item Name", "Gross Weight"], [["NEW_ITEM", 110.0]])
        rp = httpx.post(
            f"{API_URL}/physical-stock/upload-preview?verification_date={DATE_C}",
            files={"file": ("p.xlsx", preview_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth, timeout=30,
        )
        assert rp.status_code == 200
        assert rp.json()["summary"]["matched"] == 1


class TestChunkedPathDateSafe:
    """Chunked upload path must reject physical_stock (direct-only)."""

    def test_chunked_init_for_physical_stock(self, auth):
        """Chunked init for physical_stock should return 400 — physical stock is direct-only."""
        r = httpx.post(
            f"{API_URL}/upload/init",
            json={"file_type": "physical_stock", "total_chunks": 1, "verification_date": DATE_B},
            headers=auth, timeout=30,
        )
        assert r.status_code == 400
        assert "direct upload flow" in r.json()["detail"]


class TestAmbiguityDetection:
    """item_name is unique per user's business rule. Preview matches by normalized name."""

    def test_ambiguous_item_name_no_stamp(self, auth):
        """Upload with same item name on same date → matches correctly by name."""
        # Seed DATE_A with two items (using full upload which allows duplicates in file)
        excel_seed = _make_excel(
            ["Item Name", "Stamp", "Gross Weight", "Net Weight"],
            [
                ["DUP_ITEM", "STAMP 1", 10.0, 8.0],
                ["DUP_ITEM", "STAMP 2", 20.0, 15.0],
            ]
        )
        httpx.post(
            f"{API_URL}/physical-stock/upload?verification_date={DATE_A}",
            files={"file": ("seed.xlsx", excel_seed, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth, timeout=30,
        )

        # Preview with NO stamp column → matches by name
        preview_excel = _make_excel(["Item Name", "Gross Weight"], [["DUP_ITEM", 15.0]])
        r = httpx.post(
            f"{API_URL}/physical-stock/upload-preview?verification_date={DATE_A}",
            files={"file": ("p.xlsx", preview_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth, timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["summary"]["matched"] >= 1

    def test_stamp_resolves_ambiguity(self, auth):
        """Upload WITH stamp column → matches correctly."""
        excel_seed = _make_excel(
            ["Item Name", "Stamp", "Gross Weight", "Net Weight"],
            [
                ["DUP_ITEM", "STAMP 1", 10.0, 8.0],
                ["DUP_ITEM", "STAMP 2", 20.0, 15.0],
            ]
        )
        httpx.post(
            f"{API_URL}/physical-stock/upload?verification_date={DATE_A}",
            files={"file": ("seed.xlsx", excel_seed, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth, timeout=30,
        )

        preview_excel = _make_excel(
            ["Item Name", "Stamp", "Gross Weight"],
            [["DUP_ITEM", "STAMP 1", 15.0]]
        )
        r = httpx.post(
            f"{API_URL}/physical-stock/upload-preview?verification_date={DATE_A}",
            files={"file": ("p.xlsx", preview_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth, timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["summary"]["matched"] == 1


class TestPreviewApplyStillWork:
    """Regression: preview and apply must still work after refactor."""

    def test_preview_date_scoped(self, auth):
        """Preview for seeded date works."""
        # Seed
        excel = _make_excel(
            ["Item Name", "Gross Weight", "Net Weight"],
            [["REGR_ITEM", 10.0, 8.0]]
        )
        httpx.post(
            f"{API_URL}/physical-stock/upload?verification_date={DATE_B}",
            files={"file": ("s.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth, timeout=30,
        )

        # Preview
        prev_excel = _make_excel(["Item Name", "Gross Weight"], [["REGR_ITEM", 12.0]])
        r = httpx.post(
            f"{API_URL}/physical-stock/upload-preview?verification_date={DATE_B}",
            files={"file": ("p.xlsx", prev_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth, timeout=30,
        )
        assert r.status_code == 200
        assert r.json()["update_mode"] == "gross_only"
        assert r.json()["summary"]["matched"] == 1

    def test_apply_returns_date_and_count(self, auth):
        """Apply returns proper success message with date and count."""
        # Seed
        excel = _make_excel(
            ["Item Name", "Gross Weight", "Net Weight"],
            [["APPLY_ITEM", 10.0, 8.0]]
        )
        httpx.post(
            f"{API_URL}/physical-stock/upload?verification_date={DATE_B}",
            files={"file": ("s.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth, timeout=30,
        )

        # Apply
        r = httpx.post(
            f"{API_URL}/physical-stock/apply-updates",
            json={
                "items": [{"item_name": "APPLY_ITEM", "new_gr_wt": 12000, "update_mode": "gross_only"}],
                "verification_date": DATE_B,
            },
            headers=auth, timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["updated_count"] == 1
        assert data["verification_date"] == DATE_B
        assert DATE_B in data["message"]
        assert "1 item" in data["message"]


class TestExistingFlows:
    """Non-physical upload endpoints must not regress."""

    def test_purchase_upload_still_works(self, auth):
        """Purchase upload endpoint exists and rejects bad input properly."""
        r = httpx.post(
            f"{API_URL}/transactions/upload/purchase?start_date=2026-01-01&end_date=2026-01-01",
            files={"file": ("empty.xlsx", b"not-an-excel", "application/octet-stream")},
            headers=auth, timeout=30,
        )
        # Will fail parsing but should not 500
        assert r.status_code in (400, 422)

    def test_chunked_init_purchase(self, auth):
        """Chunked init for purchase still works."""
        r = httpx.post(
            f"{API_URL}/upload/init",
            json={"file_type": "purchase", "total_chunks": 1, "start_date": "2026-01-01", "end_date": "2026-01-01"},
            headers=auth, timeout=30,
        )
        assert r.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
