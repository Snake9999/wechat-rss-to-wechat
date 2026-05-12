from app.transform.html_cleaner import clean_html


def test_clean_html_removes_script_and_style():
    raw_html = "<div><script>alert(1)</script><style>body{}</style><p>Hello</p></div>"
    cleaned = clean_html(raw_html)
    assert "<script" not in cleaned
    assert "<style" not in cleaned
    assert "Hello" in cleaned


def test_clean_html_drops_images_by_default():
    raw_html = '<div><p>Hello</p><img src="https://example.com/a.jpg" alt="a"/></div>'
    cleaned = clean_html(raw_html)
    assert "<img" not in cleaned
