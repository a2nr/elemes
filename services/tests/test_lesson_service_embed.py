import pytest
pytestmark = pytest.mark.unit
from services.lesson_service import _process_embed_embeds


def test_embed_canva_html():
    md = """```embed
<div style="position: relative; width: 100%; padding-top: 56.25%;">
  <iframe loading="lazy" src="https://www.canva.com/design/ABC/view?embed" allowfullscreen></iframe>
</div>
```"""
    out = _process_embed_embeds(md)
    assert 'canva.com' in out
    assert '<iframe' in out
    assert 'allowfullscreen' in out


def test_embed_strips_script():
    md = """```embed
<div><iframe src="https://youtube.com/embed/x"></iframe><script>alert(1)</script></div>
```"""
    out = _process_embed_embeds(md)
    # Script tags are stripped by bleach; inner text remains but is harmless
    assert '<script' not in out.lower()
    assert '</script>' not in out.lower()


def test_embed_strips_onclick():
    md = """```embed
<div onclick="alert(1)"><iframe src="https://youtube.com/embed/x"></iframe></div>
```"""
    out = _process_embed_embeds(md)
    assert 'onclick' not in out
    assert 'alert' not in out


def test_embed_blocked_domain():
    md = """```embed
<iframe src="https://169.254.169.254/meta"></iframe>
```"""
    out = _process_embed_embeds(md)
    assert 'embed-error' in out


def test_embed_non_https_iframe():
    md = """```embed
<iframe src="http://youtube.com/embed/x"></iframe>
```"""
    out = _process_embed_embeds(md)
    assert 'embed-error' in out


def test_embed_empty_rejected():
    md = """```embed

```"""
    out = _process_embed_embeds(md)
    assert 'embed-error' in out
    assert 'kosong' in out


def test_embed_no_embed_unchanged():
    md = "# Heading\n\nparagraf biasa"
    assert _process_embed_embeds(md) == md


def test_embed_youtube_html():
    md = """```embed
<iframe width="560" height="315" src="https://www.youtube.com/embed/dQw4w9WgXcQ" allowfullscreen></iframe>
```"""
    out = _process_embed_embeds(md)
    assert 'youtube.com' in out
    assert '<iframe' in out


def test_embed_strips_dangerous_style():
    md = """```embed
<div style="background: url('javascript:alert(1)')"><iframe src="https://youtube.com/embed/x"></iframe></div>
```"""
    out = _process_embed_embeds(md)
    assert 'javascript' not in out.lower()
