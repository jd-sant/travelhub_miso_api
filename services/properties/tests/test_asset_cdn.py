def test_rewrite_asset_url_returns_original_when_cdn_disabled(monkeypatch):
    monkeypatch.delenv("ASSET_CDN_BASE_URL", raising=False)
    from core import config
    config.get_settings.cache_clear()
    from adapters.repositories import property_repository
    property_repository.settings = config.get_settings()

    original = "https://images.unsplash.com/photo-123?w=800&q=80"
    assert property_repository._rewrite_asset_url(original) == original


def test_rewrite_asset_url_swaps_host_to_cdn(monkeypatch):
    monkeypatch.setenv("ASSET_CDN_BASE_URL", "https://d111111abcdef8.cloudfront.net")
    from core import config
    config.get_settings.cache_clear()
    from adapters.repositories import property_repository
    property_repository.settings = config.get_settings()

    original = "https://images.unsplash.com/photo-123?w=800&q=80"
    rewritten = property_repository._rewrite_asset_url(original)

    assert rewritten == "https://d111111abcdef8.cloudfront.net/photo-123?w=800&q=80"
