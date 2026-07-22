"""Tests for HRR primitives."""

from unittest.mock import patch

from hermescube import hrr


class TestEmbed:
    def test_embed_outputs_unit_vector(self):
        v = hrr.embed_text("hello world")
        assert abs(hrr.norm(v) - 1.0) < 1e-10

    def test_embed_is_deterministic(self):
        v1 = hrr.embed_text("test query")
        v2 = hrr.embed_text("test query")
        assert abs(hrr.cosine_sim(v1, v2) - 1.0) < 1e-10

    def test_embed_different_texts_differ(self):
        v1 = hrr.embed_text("hello")
        v2 = hrr.embed_text("world")
        assert hrr.cosine_sim(v1, v2) < 0.9

    def test_embed_empty_string(self):
        v = hrr.embed_text("")
        assert abs(hrr.norm(v) - 1.0) < 1e-10

    def test_embed_dim_respected(self):
        v = hrr.embed_text("test", dim=128)
        assert len(v) == 128

    def test_embed_none_text(self):
        v = hrr.embed_text(None)  # type: ignore
        assert abs(hrr.norm(v) - 1.0) < 1e-10


class TestOps:
    def test_dot_product(self):
        a = hrr.embed_text("vector a")
        b = hrr.embed_text("vector b")
        d = hrr.dot(a, b)
        assert isinstance(d, float)

    def test_self_similarity(self):
        a = hrr.embed_text("self")
        assert abs(hrr.cosine_sim(a, a) - 1.0) < 1e-10

    def test_zero_norm(self):
        z = hrr.zero_vector()
        assert hrr.norm(z) < 1e-10

    def test_normalize_zero(self):
        z = hrr.zero_vector()
        nz = hrr.normalize(z)
        assert hrr.norm(nz) < 1e-10

    def test_cosine_with_zero(self):
        a = hrr.embed_text("something")
        z = hrr.zero_vector()
        assert hrr.cosine_sim(a, z) == 0.0
        assert hrr.cosine_sim(z, a) == 0.0


class TestHRR:
    def test_bind_reduces_similarity(self):
        a = hrr.embed_text("concept a")
        b = hrr.embed_text("concept b")
        c = hrr.bind(a, b)
        sim_a_c = hrr.cosine_sim(a, c)
        assert sim_a_c < 0.5  # bound vector should differ from inputs

    def test_bind_unbind_roundtrip(self):
        a = hrr.embed_text("original concept")
        b = hrr.embed_text("binding key")
        c = hrr.bind(a, b)
        a_recovered = hrr.unbind(c, b)
        sim = hrr.cosine_sim(a, a_recovered)
        # HRR approximate inverse, expect reasonable but not perfect reconstruction
        assert sim > 0.4

    def test_bind_unbind_different_key_fails(self):
        a = hrr.embed_text("original")
        b1 = hrr.embed_text("key one")
        b2 = hrr.embed_text("key two")
        c = hrr.bind(a, b1)
        wrong = hrr.unbind(c, b2)
        sim_correct = hrr.cosine_sim(a, hrr.unbind(c, b1))
        sim_wrong = hrr.cosine_sim(a, wrong)
        assert sim_correct > sim_wrong

    def test_superpose_preserves_norm(self):
        a = hrr.embed_text("item 1")
        b = hrr.embed_text("item 2")
        s = hrr.superpose([a, b])
        assert abs(hrr.norm(s) - 1.0) < 1e-10

    def test_superpose_with_self(self):
        a = hrr.embed_text("item")
        s = hrr.superpose([a, a])
        # Superposing same vector should produce same direction
        assert hrr.cosine_sim(s, a) > 0.99

    def test_superpose_empty(self):
        s = hrr.superpose([])
        assert hrr.norm(s) < 1e-10


class TestBackend:
    def test_has_numpy_bool(self):
        assert isinstance(hrr.has_numpy(), bool)

    def test_consistent_across_ops(self):
        """Verify both backends produce similar results (when numpy available)."""
        if not hrr.has_numpy():
            return
        import numpy as np

        a = hrr.embed_text("consistency test")
        b = hrr.embed_text("another vector")

        d1 = hrr.dot(a, b)
        d2 = float(np.dot(np.asarray(a, dtype=np.float64),
                          np.asarray(b, dtype=np.float64)))
        assert abs(d1 - d2) < 1e-10


class TestPurePythonBackend:
    """Force the pure-Python path to verify all ops work without numpy.

    Patches hrr._HAS_NUMPY to False so every public function dispatches
    to the _pure_* implementations. This covers the code paths that
    CI's test-no-numpy job runs but cannot verify (GH Actions runners
    have numpy pre-installed).
    """

    @patch.object(hrr, "_HAS_NUMPY", False)
    def test_embed_and_norm_pure(self):
        """embed_text + norm + normalize in pure Python."""
        v = hrr.embed_text("hello world")
        assert abs(hrr.norm(v) - 1.0) < 1e-10
        w = hrr.normalize([1.0, 2.0, 3.0])
        assert abs(hrr.norm(w) - 1.0) < 1e-10

    @patch.object(hrr, "_HAS_NUMPY", False)
    def test_dot_and_cosine_pure(self):
        """dot + cosine_sim in pure Python."""
        a = hrr.embed_text("first vector")
        b = hrr.embed_text("second vector")
        d = hrr.dot(a, b)
        assert isinstance(d, float)
        s = hrr.cosine_sim(a, b)
        assert -1.0 <= s <= 1.0

    @patch.object(hrr, "_HAS_NUMPY", False)
    def test_bind_unbind_pure(self):
        """bind + unbind round-trip in pure Python."""
        a = hrr.embed_text("key concept")
        b = hrr.embed_text("value concept")
        bound = hrr.bind(a, b)
        recovered = hrr.unbind(bound, a)
        sim = hrr.cosine_sim(b, recovered)
        assert sim > 0.1  # approximate recovery

    @patch.object(hrr, "_HAS_NUMPY", False)
    def test_superpose_pure(self):
        """superpose in pure Python."""
        a = hrr.embed_text("idea one")
        b = hrr.embed_text("idea two")
        c = hrr.embed_text("idea three")
        merged = hrr.superpose([a, b, c])
        assert abs(hrr.norm(merged) - 1.0) < 1e-10

    @patch.object(hrr, "_HAS_NUMPY", False)
    def test_zero_vector_pure(self):
        """zero_vector in pure Python."""
        z = hrr.zero_vector(128)
        assert len(z) == 128
        assert hrr.norm(z) < 1e-10

    @patch.object(hrr, "_HAS_NUMPY", False)
    def test_normalize_zero_pure(self):
        """normalize of near-zero vector returns same vector."""
        z = hrr.normalize([0.0] * 256)
        assert abs(hrr.norm(z)) < 1e-10

    @patch.object(hrr, "_HAS_NUMPY", False)
    def test_has_numpy_false(self):
        """has_numpy reports False when patched."""
        assert hrr.has_numpy() is False
