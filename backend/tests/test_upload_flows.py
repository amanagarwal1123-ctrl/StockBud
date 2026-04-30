"""Tests for upload flows: transaction uploads, non-physical upload flows, upload queue."""
import pytest
import httpx
import openpyxl
import io

API_URL = "https://profit-planner-16.preview.emergentagent.com/api"

@pytest.fixture(scope="module")
def admin_token():
    r = httpx.post(f"{API_URL}/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    return r.json()["access_token"]

@pytest.fixture()
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}

def _make_excel(headers, rows):
    """Create an in-memory Excel file from headers + rows."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class TestTransactionUpload:
    """Test purchase/sale transaction upload endpoints."""

    def test_purchase_upload_endpoint_exists(self, auth):
        """Verify purchase upload endpoint returns proper response."""
        excel = _make_excel(
            ["Date", "Type", "Party Name", "Item Name", "Gr.Wt.", "Net.Wt.", "Tunch", "Total"],
            [["2026-01-15", "P", "Test Party", "Test Item ABC", 1.0, 0.8, 90, 5000]]
        )
        r = httpx.post(
            f"{API_URL}/transactions/upload/purchase?start_date=2026-01-15&end_date=2026-01-15",
            files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth,
            timeout=30,
        )
        # Should succeed or return validation error - endpoint exists
        assert r.status_code in [200, 400], f"Unexpected status: {r.status_code}, {r.text}"

    def test_sale_upload_endpoint_exists(self, auth):
        """Verify sale upload endpoint returns proper response."""
        excel = _make_excel(
            ["Date", "Type", "Party Name", "Item Name", "Gr.Wt.", "Gold Std.", "Tunch", "Total"],
            [["2026-01-15", "S", "Test Customer", "Test Sale Item", 1.0, 0.8, 92, 5500]]
        )
        r = httpx.post(
            f"{API_URL}/transactions/upload/sale?start_date=2026-01-15&end_date=2026-01-15",
            files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth,
            timeout=30,
        )
        assert r.status_code in [200, 400], f"Unexpected status: {r.status_code}, {r.text}"


class TestChunkedUpload:
    """Test chunked upload init endpoint for all supported types."""

    def test_chunked_init_purchase(self, auth):
        """Init a chunked upload for purchase type."""
        r = httpx.post(
            f"{API_URL}/upload/init",
            json={"file_type": "purchase", "total_chunks": 1, "start_date": "2026-01-01", "end_date": "2026-01-31"},
            headers=auth, timeout=30,
        )
        assert r.status_code == 200
        assert "upload_id" in r.json()

    def test_chunked_init_sale(self, auth):
        """Init a chunked upload for sale type."""
        r = httpx.post(
            f"{API_URL}/upload/init",
            json={"file_type": "sale", "total_chunks": 1, "start_date": "2026-01-01", "end_date": "2026-01-31"},
            headers=auth, timeout=30,
        )
        assert r.status_code == 200
        assert "upload_id" in r.json()

    def test_chunked_init_branch_transfer(self, auth):
        """Init a chunked upload for branch_transfer type."""
        r = httpx.post(
            f"{API_URL}/upload/init",
            json={"file_type": "branch_transfer", "total_chunks": 1, "start_date": "2026-01-01", "end_date": "2026-01-31"},
            headers=auth, timeout=30,
        )
        assert r.status_code == 200
        assert "upload_id" in r.json()

    def test_chunked_init_opening_stock(self, auth):
        """Init a chunked upload for opening_stock type."""
        r = httpx.post(
            f"{API_URL}/upload/init",
            json={"file_type": "opening_stock", "total_chunks": 1},
            headers=auth, timeout=30,
        )
        assert r.status_code == 200
        assert "upload_id" in r.json()

    def test_chunked_init_master_stock(self, auth):
        """Init a chunked upload for master_stock type."""
        r = httpx.post(
            f"{API_URL}/upload/init",
            json={"file_type": "master_stock", "total_chunks": 1},
            headers=auth, timeout=30,
        )
        assert r.status_code == 200
        assert "upload_id" in r.json()

    def test_chunked_init_invalid_type(self, auth):
        """Invalid file_type should return 400."""
        r = httpx.post(
            f"{API_URL}/upload/init",
            json={"file_type": "invalid_type", "total_chunks": 1},
            headers=auth, timeout=30,
        )
        assert r.status_code == 400


class TestOpeningStockUpload:
    """Test opening stock upload endpoint."""

    def test_opening_stock_upload_endpoint(self, auth):
        """Verify opening stock upload endpoint works."""
        excel = _make_excel(
            ["Item Name", "Stamp", "Pc", "Gr.Wt.", "Net.Wt.", "Fine", "Rate", "Total"],
            [["Test Opening Item", "TEST", 1, 1.0, 0.8, 0.75, 75000, 60000]]
        )
        r = httpx.post(
            f"{API_URL}/opening-stock/upload",
            files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth,
            timeout=30,
        )
        # This will replace all opening stock
        assert r.status_code == 200, f"Failed: {r.text}"
        assert r.json()["success"] is True


class TestMasterStockUpload:
    """Test master stock upload endpoint."""

    def test_master_stock_upload_endpoint(self, auth):
        """Verify master stock upload endpoint works."""
        excel = _make_excel(
            ["Item Name", "Stamp", "Gr.Wt.", "Net.Wt."],
            [["Test Master Item", "STAMP1", 1.0, 0.8]]
        )
        r = httpx.post(
            f"{API_URL}/master-stock/upload",
            files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth,
            timeout=30,
        )
        # This will replace all master/opening stock
        assert r.status_code == 200, f"Failed: {r.text}"
        assert r.json()["success"] is True


class TestPhysicalStockFullUpload:
    """Test physical stock full replacement endpoint."""

    def test_physical_stock_full_replacement(self, auth):
        """Verify physical stock full upload replaces all data."""
        excel = _make_excel(
            ["Item Name", "Stamp", "Gross Weight", "Net Weight"],
            [
                ["FULL REPLACE ITEM A", "STAMP 1", 10.0, 8.0],
                ["FULL REPLACE ITEM B", "STAMP 2", 20.0, 15.0],
            ]
        )
        r = httpx.post(
            f"{API_URL}/physical-stock/upload?verification_date=2026-01-20",
            files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth,
            timeout=30,
        )
        assert r.status_code == 200, f"Failed: {r.text}"
        data = r.json()
        assert data["success"] is True
        assert data["count"] == 2
        assert data["verification_date"] == "2026-01-20"


class TestUploadAuthRequired:
    """Verify upload endpoints require authentication."""

    def test_physical_stock_upload_requires_auth(self):
        """Physical stock upload without auth should fail."""
        excel = _make_excel(["Item Name", "Gross Weight"], [["Test", 10.0]])
        r = httpx.post(
            f"{API_URL}/physical-stock/upload",
            files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            timeout=30,
        )
        assert r.status_code in [401, 403]

    def test_physical_stock_preview_requires_auth(self):
        """Physical stock preview without auth should fail."""
        excel = _make_excel(["Item Name", "Gross Weight"], [["Test", 10.0]])
        r = httpx.post(
            f"{API_URL}/physical-stock/upload-preview",
            files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            timeout=30,
        )
        assert r.status_code in [401, 403]

    def test_physical_stock_apply_requires_auth(self):
        """Physical stock apply without auth should fail."""
        r = httpx.post(
            f"{API_URL}/physical-stock/apply-updates",
            json={"items": [], "verification_date": "2026-01-01"},
            timeout=30,
        )
        assert r.status_code in [401, 403]

    def test_upload_init_requires_auth(self):
        """Upload init without auth should fail."""
        r = httpx.post(
            f"{API_URL}/upload/init",
            json={"file_type": "purchase", "total_chunks": 1},
            timeout=30,
        )
        assert r.status_code in [401, 403]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
