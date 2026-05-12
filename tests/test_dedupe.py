from app.state.dedupe import ProcessedArticleStore


def test_mark_and_check_processed(tmp_path):
    store = ProcessedArticleStore(tmp_path / "processed.json")
    assert store.has_processed("src", "item-1") is False
    store.mark("src", "item-1", "Title", "https://example.com", "draft_uploaded")
    assert store.has_processed("src", "item-1") is True
