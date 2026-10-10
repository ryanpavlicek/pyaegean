"""Offline cache references and optional neural activation stay distinguishable.

Synthetic rows and model doubles exercise mechanical contracts, not linguistic gold.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from conftest import _cached_neural_backend


FOLD_PATHS = [
    ("papygreek_path", (), "papygreek-test.conllu"),
    ("papygreek_orig_path", (), "papygreek-test-orig.conllu"),
    ("papygreek_dev_path", ("tagging",), "papygreek-dev-tagging.conllu"),
    ("papygreek_dev_path", ("parse",), "papygreek-dev-parse.conllu"),
]
MECHANICAL_CONLLU = "# sent_id = mechanical\n1\tα\t_\tX\t---------\t_\t0\troot\t_\t_\n\n"


@pytest.fixture
def offline_cache(tmp_path, monkeypatch):
    from aegean import data

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))

    def no_fetch(*args, **kwargs):
        pytest.fail("an offline path lookup attempted to fetch an asset")

    monkeypatch.setattr(data, "fetch", no_fetch)
    return data.cache_dir()


@pytest.mark.parametrize("resolver,args,filename", FOLD_PATHS)
@pytest.mark.parametrize("state", ["missing", "present", "corrupt"])
def test_offline_fold_path_does_not_promise_readability(offline_cache, resolver, args, filename, state):
    from aegean.greek import papygreek
    from aegean.greek.ud import load_conllu

    expected = offline_cache / "papygreek-grc" / filename
    if state != "missing":
        expected.parent.mkdir(parents=True)
        expected.write_bytes(MECHANICAL_CONLLU.encode() if state == "present" else b"\xff")
    path = getattr(papygreek, resolver)(*args, download=False)
    assert path == expected
    if state == "missing":
        assert not path.exists()
        with pytest.raises(FileNotFoundError):
            load_conllu(path)
    elif state == "corrupt":
        with pytest.raises(UnicodeDecodeError):
            load_conllu(path)
        assert path.read_bytes() == b"\xff"
    else:
        sentences = load_conllu(path, strict=True)
        assert len(sentences) == 1
        assert [(t.form, t.upos, t.head, t.deprel) for t in sentences[0].tokens] == [
            ("α", "X", 0, "root"),
        ]
        assert path.read_text(encoding="utf-8") == MECHANICAL_CONLLU


@pytest.fixture
def neural_cache(tmp_path, monkeypatch):
    import conftest
    from aegean import data
    from aegean.greek import joint

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    real_find_spec = conftest.importlib.util.find_spec
    monkeypatch.setattr(
        conftest.importlib.util, "find_spec",
        lambda name: object() if name in ("numpy", "onnxruntime", "tokenizers") else real_find_spec(name),
    )
    selected = joint._resolve_neural_variant("default")
    return data.cache_dir() / selected.dataset


def test_missing_optional_neural_cache_skips_before_activation(neural_cache, monkeypatch):
    from aegean import greek

    def forbidden_activation(**kwargs):
        pytest.fail("absent optional model should not be activated")

    monkeypatch.setattr(greek, "use_neural_pipeline", forbidden_activation)
    with pytest.raises(pytest.skip.Exception, match="model not cached"):
        with _cached_neural_backend():
            pytest.fail("absent cache produced a backend")
    assert not neural_cache.exists()


@pytest.mark.parametrize("suffix", [".part", ".part.info", ".extract", ".old", ".sha256"])
def test_partial_neural_cache_fails_before_activation(neural_cache, monkeypatch, suffix):
    from aegean import greek

    remnant = neural_cache.with_name(neural_cache.name + suffix)
    if suffix in (".extract", ".old"):
        remnant.mkdir()
    else:
        remnant.write_bytes(b"incomplete")

    def forbidden_activation(**kwargs):
        pytest.fail("incomplete cache should fail before activation")

    monkeypatch.setattr(greek, "use_neural_pipeline", forbidden_activation)
    with pytest.raises(AssertionError, match="incomplete neural cache"):
        with _cached_neural_backend():
            pytest.fail("partial cache produced a backend")
    assert remnant.exists()


def test_lock_file_alone_is_an_absent_optional_cache(neural_cache, monkeypatch):
    from aegean import greek

    neural_cache.with_name(neural_cache.name + ".lock").touch()

    def forbidden_activation(**kwargs):
        pytest.fail("a persistent lock file is not a model artifact")

    monkeypatch.setattr(greek, "use_neural_pipeline", forbidden_activation)
    with pytest.raises(pytest.skip.Exception, match="model not cached"):
        with _cached_neural_backend():
            pytest.fail("lock file produced a backend")


def test_present_neural_cache_activates_and_restores_state(neural_cache, monkeypatch):
    from aegean import greek
    from aegean.greek import joint, runtime

    neural_cache.mkdir()
    previous_pipeline = runtime.default_pipeline()
    previous_active = joint._ACTIVE
    model = SimpleNamespace()
    calls = []

    def activate(**kwargs):
        calls.append(kwargs)
        runtime._set_default_pipeline(runtime.GreekPipeline())
        joint._ACTIVE = model

    monkeypatch.setattr(greek, "use_neural_pipeline", activate)
    with _cached_neural_backend() as activated:
        assert activated is model
        assert joint.active() is model
    assert calls == [{"variant": "default"}]
    assert runtime.default_pipeline() is previous_pipeline
    assert joint._ACTIVE is previous_active


@pytest.mark.parametrize("error", [ValueError("corrupt model metadata"), RuntimeError("activation failed")])
def test_present_neural_cache_activation_errors_fail(neural_cache, monkeypatch, error):
    from aegean import greek
    from aegean.greek import joint, runtime

    neural_cache.mkdir()
    previous_pipeline = runtime.default_pipeline()
    previous_active = joint._ACTIVE

    def activate(**kwargs):
        runtime._set_default_pipeline(runtime.GreekPipeline())
        joint._ACTIVE = None
        raise error

    monkeypatch.setattr(greek, "use_neural_pipeline", activate)
    with pytest.raises(type(error), match=str(error)):
        with _cached_neural_backend():
            pytest.fail("activation failure produced a backend")
    assert runtime.default_pipeline() is previous_pipeline
    assert joint._ACTIVE is previous_active


def test_stale_neural_cache_cannot_download(neural_cache, monkeypatch):
    from aegean import data, greek

    neural_cache.mkdir()

    def activate(**kwargs):
        data._download("https://example.invalid/model", neural_cache / "model.part", "grc-joint")

    monkeypatch.setattr(greek, "use_neural_pipeline", activate)
    with pytest.raises(pytest.fail.Exception, match="attempted a download"):
        with _cached_neural_backend():
            pytest.fail("stale cache produced a backend")
    assert list(neural_cache.iterdir()) == []


def test_activation_without_backend_fails(neural_cache, monkeypatch):
    from aegean import greek
    from aegean.greek import joint

    neural_cache.mkdir()
    monkeypatch.setattr(greek, "use_neural_pipeline", lambda **kwargs: None)
    monkeypatch.setattr(joint, "active", lambda: None)
    with pytest.raises(AssertionError, match="did not install a backend"):
        with _cached_neural_backend():
            pytest.fail("missing backend was accepted")
