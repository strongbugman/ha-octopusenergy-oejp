from __future__ import annotations

from octopusenergy_oejp_demo.env import load_dotenv


def test_load_dotenv_does_not_override_existing_values(tmp_path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "OCTOPUS_EMAIL=file@example.com\n"
        "OCTOPUS_PASSWORD='file password'\n"
        "OCTOPUS_BASE_URL=https://api.example.test # comment\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OCTOPUS_EMAIL", "env@example.com")

    values = load_dotenv(dotenv)

    assert values["OCTOPUS_EMAIL"] == "file@example.com"
    assert values["OCTOPUS_PASSWORD"] == "file password"
    assert values["OCTOPUS_BASE_URL"] == "https://api.example.test"
    assert "OCTOPUS_PASSWORD" in values
