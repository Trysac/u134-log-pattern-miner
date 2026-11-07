"""Comprehensive tests for log_pattern_miner exercising all acceptance criteria."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from log_pattern_miner import (
    Miner,
    MinerConfig,
    MinerError,
    __version__,
    new_templates,
)
from log_pattern_miner.cli import main


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_acceptance_1() -> None:
    """Adding 'Connected to 10.0.0.1 in 35 ms' then 'Connected to 10.0.0.2 in 7 ms'
    returns Matches with the same cluster_id 1, is_new True then False, and
    template 'Connected to <*> in <*> ms' with count 2.
    """
    m = Miner()
    match1 = m.add("Connected to 10.0.0.1 in 35 ms")
    assert match1.cluster_id == 1
    assert match1.is_new is True
    assert match1.changed is False
    assert match1.template == "Connected to <*> in <*> ms"

    match2 = m.add("Connected to 10.0.0.2 in 7 ms")
    assert match2.cluster_id == 1
    assert match2.is_new is False
    assert match2.changed is False
    assert match2.template == "Connected to <*> in <*> ms"

    clusters = m.clusters()
    assert len(clusters) == 1
    assert clusters[0].id == 1
    assert clusters[0].template == "Connected to <*> in <*> ms"
    assert clusters[0].count == 2


def test_acceptance_2() -> None:
    """'session opened for alice' then 'session opened for bob' with sim_threshold 0.4
    give template 'session opened for <*>' and the second Match has changed == True;
    'disk full' and 'cache miss' become separate clusters with ids 1 and 2, and
    'user alice quit' and 'user bob quit' also stay separate because the second token
    routes the tree.
    """
    # Part 1
    m1 = Miner(MinerConfig(sim_threshold=0.4))
    res1 = m1.add("session opened for alice")
    assert res1.template == "session opened for alice"
    assert res1.is_new is True
    assert res1.changed is False

    res2 = m1.add("session opened for bob")
    assert res2.cluster_id == res1.cluster_id
    assert res2.is_new is False
    assert res2.changed is True
    assert res2.template == "session opened for <*>"

    # Part 2
    m2 = Miner()
    r_disk = m2.add("disk full")
    r_cache = m2.add("cache miss")
    assert r_disk.cluster_id == 1
    assert r_cache.cluster_id == 2

    # Part 3: depth=4 has root -> token count -> token 0 -> token 1 -> leaf
    # 'user alice quit' has tokens ['user', 'alice', 'quit']
    # Second token routes the tree ('alice' vs 'bob'), so they stay separate.
    m3 = Miner(MinerConfig(depth=4, sim_threshold=0.4))
    r_alice = m3.add("user alice quit")
    r_bob = m3.add("user bob quit")
    assert r_alice.cluster_id != r_bob.cluster_id
    assert len(m3.clusters()) == 2


def test_acceptance_3() -> None:
    """Lines with different token counts never share a cluster:
    'job done' and 'job done twice' produce two clusters.
    """
    m = Miner()
    m.add("job done")
    m.add("job done twice")
    clusters = m.clusters()
    assert len(clusters) == 2
    assert clusters[0].id == 1
    assert clusters[0].template == "job done"
    assert clusters[1].id == 2
    assert clusters[1].template == "job done twice"


def test_acceptance_4(tmp_path: Path) -> None:
    """Miner.from_json(m.to_json()).clusters() == m.clusters() after 100 lines,
    and adding the same next line to both yields equal Matches;
    a state string over max_state_chars=50_000_000 raises MinerError with code 'input_too_large'
    and invalid JSON raises code 'invalid_state'.
    """
    m = Miner()
    for i in range(100):
        m.add(f"Request {i} processed in {i * 10} ms status {200 if i % 2 == 0 else 500}")

    json_state = m.to_json()
    m_loaded = Miner.from_json(json_state)
    assert m_loaded.clusters() == m.clusters()

    next_line = "Request 999 processed in 1234 ms status 404"
    match_orig = m.add(next_line)
    match_loaded = m_loaded.add(next_line)
    assert match_orig == match_loaded

    # input_too_large test
    with pytest.raises(MinerError) as exc_info:
        Miner.from_json("x" * 100, max_state_chars=50)
    assert exc_info.value.code == "input_too_large"

    # invalid JSON test
    with pytest.raises(MinerError) as exc_invalid:
        Miner.from_json("{not valid json}")
    assert exc_invalid.value.code == "invalid_state"

    # invalid json payload structure
    with pytest.raises(MinerError) as exc_not_dict:
        Miner.from_json("[]")
    assert exc_not_dict.value.code == "invalid_state"

    with pytest.raises(MinerError) as exc_bad_cfg:
        Miner.from_json(json.dumps({"config": "not_a_dict"}))
    assert exc_bad_cfg.value.code == "invalid_state"

    with pytest.raises(MinerError) as exc_bad_clusters:
        Miner.from_json(
            json.dumps(
                {
                    "config": {
                        "depth": 4,
                        "sim_threshold": 0.4,
                        "max_children": 10,
                        "max_clusters": 10,
                        "max_line_chars": 100,
                    },
                    "next_id": 1,
                    "clusters": "not_a_list",
                }
            )
        )
    assert exc_bad_clusters.value.code == "invalid_state"


def test_acceptance_5() -> None:
    """With max_clusters=2, a third distinct cluster evicts the least recently matched one,
    stats.evicted == 1 and clusters() holds the 2 most recent; cluster ids are never reused
    (the third cluster has id 3).
    """
    m = Miner(MinerConfig(max_clusters=2))
    m.add("first distinct message")
    m.add("second distinct message")
    assert len(m.clusters()) == 2
    assert m.stats.evicted == 0

    # Match first cluster again to make it recently used
    m.add("first distinct message")

    # Add a third distinct cluster
    m.add("third distinct message")

    assert m.stats.evicted == 1
    active_clusters = m.clusters()
    assert len(active_clusters) == 2
    # Evicted was cluster 2 (second message), remaining are 1 and 3
    ids = [c.id for c in active_clusters]
    assert ids == [1, 3]
    assert active_clusters[1].id == 3
    assert active_clusters[1].template == "third distinct message"


def test_acceptance_6() -> None:
    """A line of 10_001 characters is truncated to max_line_chars=10_000
    before tokenising and stats.truncated == 1.
    """
    m = Miner(MinerConfig(max_line_chars=10_000))
    long_line = "a " * 5000 + "xyz"
    assert len(long_line) > 10_000
    m.add(long_line)
    assert m.stats.truncated == 1
    assert m.stats.lines == 1


def test_acceptance_7(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """main(['mine', 'app.log', '--baseline', 'base.json']) prints one line
    'NEW 3 disk <*> on <*>' per template whose text is not in the baseline and returns 1;
    with no new template it prints nothing and returns 0;
    main(['mine', 'app.log', '--save', 's.json']) prints '<count> <id> <template>' lines
    sorted by count descending then id and returns 0.
    """
    app_log = tmp_path / "app.log"
    base_json = tmp_path / "base.json"
    save_json = tmp_path / "s.json"

    # Setup baseline miner with some templates
    # Baseline has:
    # 1: 'user logged in'
    # 2: 'service started'
    base_m = Miner()
    base_m.add("user logged in")
    base_m.add("service started")
    base_json.write_text(base_m.to_json(), encoding="utf-8")

    # Setup app.log: has 'user logged in' (present in base), 'service started' (present in base),
    # plus 'disk 12 on 99' and 'disk 34 on 56', which both match cluster 3 'disk <*> on <*>'
    app_log.write_text(
        "user logged in\nservice started\ndisk 12 on 99\ndisk 34 on 56\n",
        encoding="utf-8",
    )

    # Run baseline comparison: prints 'NEW 3 disk <*> on <*>'
    capsys.readouterr()
    code = main(["mine", str(app_log), "--baseline", str(base_json)])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == "NEW 3 disk <*> on <*>\n"

    # Baseline with no new templates
    no_new_log = tmp_path / "no_new.log"
    no_new_log.write_text("user logged in\nservice started\n", encoding="utf-8")
    capsys.readouterr()
    code_zero = main(["mine", str(no_new_log), "--baseline", str(base_json)])
    captured_zero = capsys.readouterr()
    assert code_zero == 0
    assert captured_zero.out == ""

    # Run with --save
    capsys.readouterr()
    code_save = main(["mine", str(app_log), "--save", str(save_json)])
    captured_save = capsys.readouterr()
    assert code_save == 0
    assert save_json.exists()
    # Validate output format: '<count> <id> <template>' sorted by count descending then id
    lines = [ln.strip() for ln in captured_save.out.splitlines() if ln.strip()]
    assert len(lines) == 3
    # 'disk <*> on <*>' appeared 2 times (id 3), 'user logged in' 1 time (id 1), 'service started' 1 time (id 2)
    assert lines[0] == "2 3 disk <*> on <*>"
    assert lines[1] == "1 1 user logged in"
    assert lines[2] == "1 2 service started"


def test_miner_config_validation() -> None:
    """MinerConfig validation: depth 3-10, sim_threshold in [0, 1], max_children and max_clusters >= 1."""
    with pytest.raises(MinerError) as exc:
        Miner(MinerConfig(depth=2))
    assert exc.value.code == "invalid_config"

    with pytest.raises(MinerError) as exc:
        Miner(MinerConfig(depth=11))
    assert exc.value.code == "invalid_config"

    with pytest.raises(MinerError) as exc:
        Miner(MinerConfig(sim_threshold=-0.1))
    assert exc.value.code == "invalid_config"

    with pytest.raises(MinerError) as exc:
        Miner(MinerConfig(sim_threshold=1.1))
    assert exc.value.code == "invalid_config"

    with pytest.raises(MinerError) as exc:
        Miner(MinerConfig(max_children=0))
    assert exc.value.code == "invalid_config"

    with pytest.raises(MinerError) as exc:
        Miner(MinerConfig(max_clusters=0))
    assert exc.value.code == "invalid_config"

    with pytest.raises(MinerError) as exc:
        Miner(MinerConfig(max_line_chars=0))
    assert exc.value.code == "invalid_config"


def test_preprocessing_masks() -> None:
    """Test UUID, IPv4 with optional port, hex, and number masks."""
    m = Miner()
    # UUID
    res_uuid = m.add("Event c39c9480-1a1a-4f51-879e-4c5ef38f16b2 occurred")
    assert res_uuid.template == "Event <*> occurred"

    # IPv4 without port
    res_ip = m.add("Host 192.168.1.1 is active")
    assert res_ip.template == "Host <*> is active"

    # IPv4 with port
    res_ipport = m.add("Host 10.0.0.1:8080 connected")
    assert res_ipport.template == "Host <*> connected"

    # Hex
    res_hex = m.add("Address 0xdeadbeef parsed")
    assert res_hex.template == "Address <*> parsed"

    # Number: negative, positive with sign, float, integer
    res_num1 = m.add("Offset -42 detected")
    assert res_num1.template == "Offset <*> detected"
    res_num2 = m.add("Temperature +23.5 measured")
    assert res_num2.template == "Temperature <*> measured"


def test_edge_cases() -> None:
    """Empty lines, lines that are only masked tokens, unicode, CRLF line endings."""
    m = Miner()
    # Empty line
    res_empty = m.add("")
    assert res_empty.template == ""
    assert res_empty.cluster_id == 1

    # Line with only whitespace
    res_spaces = m.add("   \t  ")
    assert res_spaces.template == ""
    assert res_spaces.cluster_id == 1
    assert res_spaces.is_new is False

    # CRLF line ending
    res_crlf = m.add("server start\r\n")
    assert res_crlf.template == "server start"

    # Only masked tokens
    res_masked = m.add("192.168.0.1 0x12 45")
    assert res_masked.template == "<*> <*> <*>"

    # Unicode characters
    res_uni = m.add("ユーザー 123 ログイン")
    assert res_uni.template == "ユーザー <*> ログイン"


def test_max_children_overflow() -> None:
    """When children exceed max_children, route to <*>."""
    m = Miner(MinerConfig(depth=3, max_children=2))
    # depth 3 has 1 prefix token step
    m.add("alpha log")
    m.add("beta log")
    # Now node has 2 children: 'alpha' and 'beta'
    # Third distinct token routes to '<*>'
    r_gamma = m.add("gamma log")
    assert r_gamma.cluster_id == 3

    # Another distinct token routes to '<*>' and can match cluster 3
    r_delta = m.add("delta log")
    assert r_delta.cluster_id == 3
    assert r_delta.template == "<*> log"


def test_new_templates_helper() -> None:
    """Verify new_templates diffing."""
    base = Miner()
    base.add("msg A")
    base.add("msg B")

    curr = Miner()
    curr.add("msg A")
    curr.add("msg C")
    curr.add("msg D")

    diff = new_templates(curr, base)
    templates = [c.template for c in diff]
    assert templates == ["msg C", "msg D"]


def test_cli_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI error scenarios and exit codes."""
    # Invalid subcommand
    assert main([]) == 2
    assert main(["invalid_cmd"]) == 2

    # Invalid miner configuration flag
    assert main(["mine", "nonexistent.log", "--depth", "20"]) == 2

    # Nonexistent logfile
    assert main(["mine", str(tmp_path / "not_there.log")]) == 2

    # Nonexistent baseline file
    real_log = tmp_path / "file.log"
    real_log.write_text("line 1\n", encoding="utf-8")
    assert main(["mine", str(real_log), "--baseline", str(tmp_path / "no_base.json")]) == 2

    # Corrupted baseline file
    bad_base = tmp_path / "bad_base.json"
    bad_base.write_text("{broken json", encoding="utf-8")
    assert main(["mine", str(real_log), "--baseline", str(bad_base)]) == 2
