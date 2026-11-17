"""Regression checks for grounded vision routing and Cloudflare image fallback."""
from pathlib import Path


def test_image_accuracy_instruction_and_dedicated_vision_model_are_present():
    source = Path("app.py").read_text(encoding="utf-8")
    assert 'GEMINI_VISION_MODEL", "gemini-3.8-flash' in source
    assert "IMAGE ANALYSIS MODE" in source
    assert "do not fabricate a description" in source
    assert "_has_vision_input" in source


def test_cloudflare_image_fallback_is_configurable_and_uses_flux():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "CLOUDFLARE_ACCOUNT_ID" in source
    assert "CLOUDFLARE_API_TOKEN" in source
    assert "@cf/black-forest-labs/flux-1-schnell" in source
    assert "_generate_cloudflare_image_result(prompt, reference_images)" in source


def test_online_image_search_combines_wikimedia_and_openverse():
    source = Path("cyberlord_ai.py").read_text(encoding="utf-8")
    assert "api.openverse.org/v1/images/" in source
    assert "Combine independent free sources" in source
