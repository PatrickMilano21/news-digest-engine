from src.normalize import dedupe_key, normalize_title, normalize_url


def test_normalize_url_strips_fragments():
    a = normalize_url("https://example.com/news?id=1#section")
    b = normalize_url("https://example.com/news?id=1#other")
    c = normalize_url("https://example.com/news?id=1")
    
    assert a == b == c 


def test_normalize_title_collapse_whitespace():
    assert normalize_title("  Hello   world \n") == "Hello world"


def test_dedupe_key_equal_for_equivalent_inputs():
    k1 = dedupe_key("https://example.com/news?id=1#section", " Hello   world ")
    k2 = dedupe_key("https://example.com/news?id=1", "Hello world")

    assert k1 == k2


def test_normalize_url_strips_tracking_params():
    clean = normalize_url("https://example.com/article?id=123")
    with_utm = normalize_url("https://example.com/article?id=123&utm_source=twitter")
    with_fbclid = normalize_url("https://example.com/article?id=123&fbclid=abc123")

    assert clean == with_utm == with_fbclid


def test_normalize_url_sorts_params():
    a = normalize_url("https://example.com/article?b=2&a=1")
    b = normalize_url("https://example.com/article?a=1&b=2")

    assert a == b
    assert a == "https://example.com/article?a=1&b=2"


def test_normalize_url_lowercases_scheme_and_host():
    a = normalize_url("HTTPS://EXAMPLE.COM/Article")
    b = normalize_url("https://example.com/Article")

    assert a == b
    assert a == "https://example.com/Article"  # Path case preserved


def test_dedupe_key_same_for_tracking_variants():
    k1 = dedupe_key("https://example.com/news?id=1&utm_source=twitter", "Hello")
    k2 = dedupe_key("https://example.com/news?id=1&fbclid=xyz", "Hello")
    k3 = dedupe_key("https://example.com/news?id=1", "Hello")

    assert k1 == k2 == k3
