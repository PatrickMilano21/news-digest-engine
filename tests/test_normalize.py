from src.schemas import dedupe_key, normalize_title, normalize_url


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
