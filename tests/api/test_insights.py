import json

from modules import ai_insights


def test_preview_returns_payload_and_available_flag(client, people):
    r = client.get("/api/insights/preview", params={"person_id": people[0]["id"]})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["payload"], str)
    assert isinstance(body["available"], bool)
    # payload is the exact anonymized JSON that would be sent — must parse.
    json.loads(body["payload"])


def test_preview_joint_is_household(client):
    # No person_id => Joint => household: one summary per person + shared-goals household.
    r = client.get("/api/insights/preview")
    assert r.status_code == 200
    summaries = json.loads(r.json()["payload"])
    labels = [s["who"] for s in summaries]
    assert "Person A" in labels and "Person B" in labels
    assert any("Household" in lbl for lbl in labels)
    # Anonymized: no real seeded names ("Ido"/"Aviv") leak into the payload.
    assert "Ido" not in labels and "Aviv" not in labels


def test_generate_returns_text(client, people, monkeypatch):
    # Mock the CLI: pretend claude is installed and returns insight text.
    monkeypatch.setattr(ai_insights.shutil, "which", lambda _name: "/usr/bin/claude")

    class FakeCompleted:
        returncode = 0
        stdout = "You saved 24% this month. Great work!"
        stderr = ""

    monkeypatch.setattr(ai_insights.subprocess, "run", lambda *a, **k: FakeCompleted())

    r = client.post("/api/insights/generate", json={"person_id": people[0]["id"]})
    assert r.status_code == 200
    assert r.json()["text"] == "You saved 24% this month. Great work!"


def test_generate_personalizes_labels_with_real_names(client, people, monkeypatch):
    # Real names never go to the model; the platform swaps the generic labels
    # back into the model's output before returning it.
    monkeypatch.setattr(ai_insights.shutil, "which", lambda _name: "/usr/bin/claude")

    class FakeCompleted:
        returncode = 0
        stdout = "## Person A — Snapshot\n\nPerson A is on track."
        stderr = ""

    monkeypatch.setattr(ai_insights.subprocess, "run", lambda *a, **k: FakeCompleted())

    r = client.post("/api/insights/generate", json={"person_id": people[0]["id"]})
    assert r.status_code == 200
    text = r.json()["text"]
    assert people[0]["name"] in text
    assert "Person A" not in text


def test_apply_names_swaps_labels():
    names = {"Person A": "Ido", "Person B": "Aviv"}
    assert ai_insights.apply_names("Person A paid Person B.", names) == "Ido paid Aviv."
    assert ai_insights.apply_names("", names) == ""
    assert ai_insights.apply_names("untouched", {}) == "untouched"


def test_get_insights_decodes_cli_output_as_utf8(monkeypatch):
    # Guards the Windows mojibake fix: the CLI emits UTF-8, so subprocess must be
    # told to decode as UTF-8 (not the platform's ANSI codepage).
    monkeypatch.setattr(ai_insights.shutil, "which", lambda _name: "/usr/bin/claude")
    captured = {}

    class FakeCompleted:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(cmd, *a, **k):
        captured.update(k)
        return FakeCompleted()

    monkeypatch.setattr(ai_insights.subprocess, "run", fake_run)
    ai_insights.get_insights([{"who": "Person A"}])
    assert captured.get("encoding") == "utf-8"


def test_ai_available_reflects_shutil_which(monkeypatch):
    monkeypatch.setattr(ai_insights.shutil, "which", lambda _name: "/usr/bin/claude")
    assert ai_insights.ai_available() is True
    monkeypatch.setattr(ai_insights.shutil, "which", lambda _name: None)
    assert ai_insights.ai_available() is False


def test_get_insights_prompt_contains_aggregates_and_returns_stdout(monkeypatch):
    monkeypatch.setattr(ai_insights.shutil, "which", lambda _name: "/usr/bin/claude")

    captured = {}

    class FakeCompleted:
        returncode = 0
        stdout = "  Here are your insights.  "
        stderr = ""

    def fake_run(cmd, *a, **k):
        captured["cmd"] = cmd
        return FakeCompleted()

    monkeypatch.setattr(ai_insights.subprocess, "run", fake_run)

    summaries = [{"who": "Person A", "spending_by_category": {"Food": 123.45}}]
    out = ai_insights.get_insights(summaries)

    # Returns stdout stripped.
    assert out == "Here are your insights."
    # The prompt (last positional CLI arg before flags) carries the anonymized aggregates.
    prompt = captured["cmd"][2]
    assert "Person A" in prompt
    assert "123.45" in prompt
    # Coaching instructions are prepended into the single prompt.
    assert "personal-finance coach" in prompt


def test_get_insights_cli_not_installed(monkeypatch):
    monkeypatch.setattr(ai_insights.shutil, "which", lambda _name: None)
    out = ai_insights.get_insights([{"who": "Person A"}])
    assert "Claude Code" in out


def test_get_insights_nonzero_exit_returns_friendly_error(monkeypatch):
    monkeypatch.setattr(ai_insights.shutil, "which", lambda _name: "/usr/bin/claude")

    class FakeCompleted:
        returncode = 1
        stdout = ""
        stderr = "boom: something broke"

    monkeypatch.setattr(ai_insights.subprocess, "run", lambda *a, **k: FakeCompleted())
    out = ai_insights.get_insights([{"who": "Person A"}])
    assert "boom: something broke" in out


def test_get_insights_file_not_found(monkeypatch):
    # which() resolves but run() raises FileNotFoundError (race / removed binary).
    monkeypatch.setattr(ai_insights.shutil, "which", lambda _name: "/usr/bin/claude")

    def fake_run(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(ai_insights.subprocess, "run", fake_run)
    out = ai_insights.get_insights([{"who": "Person A"}])
    assert "Claude Code" in out
