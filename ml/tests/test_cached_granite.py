"""Tests for the deterministic Granite cache used by the panel demo."""

import pytest

from app.services.granite import GraniteClient


@pytest.mark.asyncio
async def test_unknown_upload_uses_the_committed_demo_fallback() -> None:
    result = await GraniteClient().parse_esg_pdf("", "panel-upload.pdf")

    assert result["cached"] is True
    assert result["claims"]
    assert result["claims"][0]["company_name"] == "Demo Energy Corp"
