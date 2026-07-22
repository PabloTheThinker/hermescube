"""Tests for learned embeddings."""

import math

from hermescube.embed import LearnedEmbedder
from hermescube import hrr


class TestLearnedEmbedder:
    def test_init(self):
        embedder = LearnedEmbedder(dim=256)
        assert embedder.dim == 256
        assert embedder.is_trained is False

    def test_tokenize(self):
        embedder = LearnedEmbedder()
        tokens = embedder._tokenize("User prefers dark mode")
        assert "user" in tokens
        assert "prefers" in tokens
        assert "dark" in tokens
        assert "mode" in tokens

    def test_tokenize_short_words(self):
        embedder = LearnedEmbedder()
        tokens = embedder._tokenize("I am a developer")
        # "I" and "a" are too short (1-2 chars)
        assert "i" not in tokens
        assert "a" not in tokens
        assert "developer" in tokens

    def test_train_basic(self):
        embedder = LearnedEmbedder(dim=64)
        descriptions = [
            "User prefers dark mode",
            "User likes Python programming",
            "User wants concise answers",
            "Agent should remember preferences",
            "Deployed hotfix for production crash",
        ]
        stats = embedder.train(descriptions)
        assert stats["status"] == "trained"
        assert stats["documents"] == 5
        assert embedder.is_trained is True

    def test_train_insufficient_data(self):
        embedder = LearnedEmbedder()
        stats = embedder.train(["Only one description"])
        assert stats["status"] == "insufficient_data"
        assert embedder.is_trained is False

    def test_embed_trained(self):
        embedder = LearnedEmbedder(dim=64)
        descriptions = [
            "User prefers dark mode",
            "User likes Python programming",
            "User wants concise answers",
            "Agent should remember preferences",
            "Deployed hotfix for production crash",
        ]
        embedder.train(descriptions)
        vec = embedder.embed("User prefers dark mode")
        assert len(vec) == 64
        assert hrr.norm(vec) > 0.9  # normalized

    def test_embed_untrained_fallback(self):
        embedder = LearnedEmbedder(dim=256)
        vec = embedder.embed("Any text")
        # Should fall back to hash embedding
        assert len(vec) == 256
        assert hrr.norm(vec) > 0.9

    def test_similarity_trained(self):
        embedder = LearnedEmbedder(dim=64)
        descriptions = [
            "User prefers dark mode",
            "User likes Python programming",
            "User wants concise answers",
            "Agent should remember preferences",
            "Deployed hotfix for production crash",
        ]
        embedder.train(descriptions)
        sim = embedder.similarity("User prefers dark mode", "User likes dark theme")
        assert -1.0 <= sim <= 1.0

    def test_get_vocab_info(self):
        embedder = LearnedEmbedder(dim=64)
        descriptions = [
            "User prefers dark mode",
            "User likes Python programming",
            "User wants concise answers",
            "Agent should remember preferences",
            "Deployed hotfix for production crash",
        ]
        embedder.train(descriptions)
        info = embedder.get_vocab_info()
        assert info["trained"] is True
        assert info["vocab_size"] > 0
        assert len(info["top_terms"]) > 0


class TestLearnedEmbedderPersistence:
    def test_save_and_load(self):
        import os
        import tempfile

        embedder = LearnedEmbedder(dim=64)
        descriptions = [
            "User prefers dark mode",
            "User likes Python programming",
            "User wants concise answers",
            "Agent should remember preferences",
            "Deployed hotfix for production crash",
        ]
        embedder.train(descriptions)

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "model.embedder")
            embedder.save(path)
            assert os.path.isfile(path)

            loaded = LearnedEmbedder.load(path)
            assert loaded.is_trained is True
            assert loaded.dim == 64
            assert len(loaded._vocab) == len(embedder._vocab)
            assert loaded._idf == embedder._idf
            assert loaded._doc_count == embedder._doc_count

            # Verify embeddings are identical
            vec_original = embedder.embed("User prefers dark mode")
            vec_loaded = loaded.embed("User prefers dark mode")
            assert len(vec_original) == len(vec_loaded)
            # Check all elements are close (within floating point tolerance)
            for a, b in zip(vec_original, vec_loaded):
                assert abs(a - b) < 1e-10

    def test_load_nonexistent(self):
        loaded = LearnedEmbedder.load("/nonexistent/path.embedder")
        assert loaded.is_trained is False

    def test_save_untrained(self):
        import os
        import tempfile

        embedder = LearnedEmbedder(dim=64)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "model.embedder")
            embedder.save(path)
            assert not os.path.isfile(path)

    def test_load_invalid_file(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "bad.embedder")
            with open(path, "wb") as f:
                f.write(b"garbage data")
            loaded = LearnedEmbedder.load(path)
            assert loaded.is_trained is False
