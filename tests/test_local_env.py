import os

from videos_llm.infrastructure.local_env import read_local_secret


def test_read_local_secret_uses_env_local_without_mutating_environment(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    (tmp_path / ".env.local").write_text(
        "# Local credentials\nGEMINI_API_KEY=local-secret\nIGNORED=value\n",
        encoding="utf-8",
    )

    assert read_local_secret(tmp_path, "GEMINI_API_KEY") == "local-secret"
    assert "IGNORED" not in os.environ


def test_read_local_secret_prefers_existing_environment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "environment-secret")
    (tmp_path / ".env.local").write_text(
        "GEMINI_API_KEY=file-secret\n",
        encoding="utf-8",
    )

    assert read_local_secret(tmp_path, "GEMINI_API_KEY") == "environment-secret"


def test_read_local_secret_returns_none_when_secret_is_unavailable(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert read_local_secret(tmp_path, "GEMINI_API_KEY") is None
