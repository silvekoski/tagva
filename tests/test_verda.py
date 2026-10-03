import json
from types import SimpleNamespace

import pytest
import yaml

from train import train, verda

BASE = verda.BASE_URL
PUB = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyBody user@host"


class Resp:
    def __init__(self, status, body=None):
        self.status_code = status
        if body is None:
            self.content, self.text = b"", ""
        elif isinstance(body, str):
            self.content, self.text = body.encode(), body
        else:
            self.text = json.dumps(body)
            self.content = self.text.encode()

    def json(self):
        return json.loads(self.text)


class FakeHttp:
    def __init__(self, routes):
        self.routes = {k: list(v) if isinstance(v, list) else v for k, v in routes.items()}
        self.calls = []

    def request(self, method, url, json=None, params=None, headers=None, timeout=None):
        path = url.removeprefix(BASE)
        self.calls.append(SimpleNamespace(method=method, path=path, json=json, params=params, headers=headers))
        route = self.routes[(method, path)]
        if isinstance(route, list):
            return route.pop(0) if len(route) > 1 else route[0]
        return route(json) if callable(route) else route

    def find(self, method, path):
        return [c for c in self.calls if c.method == method and c.path == path]


TOKEN = Resp(200, {"access_token": "tok", "token_type": "Bearer", "expires_in": 3600, "refresh_token": "r", "scope": "x"})
TYPES = Resp(200, [
    {"instance_type": "1A100.22V", "model": "A100 80GB", "gpu": {"description": "1x A100 SXM4 80GB"},
     "price_per_hour": "1.571", "spot_price": "0.7853", "currency": "eur"},
    {"instance_type": "1H100.80S.30V", "model": "H100", "gpu": {"description": "1x H100"},
     "price_per_hour": "2.5", "spot_price": "1.2", "currency": "eur"},
])
AVAIL = Resp(200, [{"location_code": "FIN-01", "availabilities": ["1H100.80S.30V"]},
                   {"location_code": "FIN-03", "availabilities": ["1A100.22V"]}])
IMAGES = Resp(200, [
    {"id": "i1", "image_type": "ubuntu-24.04", "name": "Ubuntu 24.04"},
    {"id": "i2", "image_type": verda.DEFAULT_IMAGE, "name": "Ubuntu 24.04 + CUDA 13.0"},
    {"id": "i3", "image_type": "ubuntu-22.04-cuda-13.0-open", "name": "Ubuntu 22.04 + CUDA 13.0"},
])
INSTANCE = {"id": "inst-1", "status": "running", "ip": "203.0.113.5", "instance_type": "1A100.22V",
            "os_volume_id": "vol-os", "volume_ids": ["vol-os", "vol-data"], "price_per_hour": 1.571,
            "location": "FIN-03", "hostname": "rex615-train"}


@pytest.fixture
def paths(tmp_path, monkeypatch):
    key = tmp_path / "verda_ed25519"
    key.write_text("private")
    (tmp_path / "verda_ed25519.pub").write_text(PUB + "\n")
    monkeypatch.setattr(verda, "STATE_FILE", tmp_path / ".state.json")
    monkeypatch.setattr(verda, "KNOWN_HOSTS", tmp_path / ".known-hosts")
    monkeypatch.setattr(verda, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(verda, "SSH_KEY", key)
    monkeypatch.delenv("VERDA_CLIENT_ID", raising=False)
    monkeypatch.delenv("VERDA_CLIENT_SECRET", raising=False)
    return tmp_path


def client(routes):
    http = FakeHttp({("POST", "/oauth2/token"): TOKEN, **routes})
    return verda.Client("cid", "secret", http=http), http


def test_missing_env_file_gives_clear_error(paths):
    with pytest.raises(verda.VerdaError, match="(?s)does not exist.*VERDA_CLIENT_ID"):
        verda.credentials(paths / ".env")


def test_env_file_is_parsed(paths):
    (paths / ".env").write_text("# c\nexport VERDA_CLIENT_ID='abc'\nVERDA_CLIENT_SECRET=\"s3\"\n")
    assert verda.credentials(paths / ".env") == ("abc", "s3")


def test_env_file_without_keys(paths):
    (paths / ".env").write_text("OTHER=1\n")
    with pytest.raises(verda.VerdaError, match="has no VERDA_CLIENT_ID"):
        verda.credentials(paths / ".env")


def test_token_and_bearer_header():
    c, http = client({("GET", "/instances"): Resp(200, [])})
    assert c.instances() == []
    token = http.find("POST", "/oauth2/token")[0]
    assert token.json == {"grant_type": "client_credentials", "client_id": "cid", "client_secret": "secret"}
    assert "Authorization" not in token.headers
    assert http.find("GET", "/instances")[0].headers["Authorization"] == "Bearer tok"


def test_401_reauthenticates_once():
    c, http = client({("GET", "/instances"): [Resp(401, {"code": "unauthorized_request", "message": "x"}), Resp(200, [])]})
    assert c.instances() == []
    assert len(http.find("POST", "/oauth2/token")) == 2


def test_error_has_code_message_and_status():
    c, _ = client({("GET", "/balance"): Resp(400, {"code": "insufficient_funds", "message": "no money"})})
    with pytest.raises(verda.VerdaError, match="HTTP 400 .insufficient_funds: no money") as e:
        c.balance()
    assert e.value.status == 400


def test_instance_types_are_public():
    c, http = client({("GET", "/instance-types"): TYPES})
    c.instance_types("eur")
    assert not http.find("POST", "/oauth2/token")
    assert http.find("GET", "/instance-types")[0].params == {"currency": "eur"}


def test_response_id_accepts_text_and_json():
    assert verda.response_id("abc-123") == "abc-123"
    assert verda.response_id('"abc-123"') == "abc-123"
    assert verda.response_id({"id": "abc"}) == "abc"
    with pytest.raises(verda.VerdaError):
        verda.response_id(None)


def test_ssh_key_found_by_public_key(paths):
    c, http = client({("GET", "/ssh-keys"): Resp(200, [
        {"id": "k1", "name": "other", "key": "ssh-ed25519 OTHER x"},
        {"id": "k2", "name": "mine", "key": PUB.rsplit(" ", 1)[0] + " other-comment"},
    ])})
    assert verda.ensure_ssh_key(c) == "k2"
    assert not http.find("POST", "/ssh-keys")


def test_ssh_key_added_when_missing(paths):
    c, http = client({("GET", "/ssh-keys"): Resp(200, []), ("POST", "/ssh-keys"): Resp(201, "new-key")})
    assert verda.ensure_ssh_key(c) == "new-key"
    assert http.find("POST", "/ssh-keys")[0].json["key"] == PUB


def up_args(**kw):
    return verda.parser().parse_args(["up", *[x for k, v in kw.items() for x in (f"--{k}", v)]])


def test_up_creates_a100_and_saves_state(paths, monkeypatch, capsys):
    monkeypatch.setattr(verda, "wait_ssh", lambda ip: None)
    c, http = client({
        ("GET", "/images"): IMAGES,
        ("GET", "/instance-types"): TYPES,
        ("GET", "/instance-availability"): AVAIL,
        ("GET", "/ssh-keys"): Resp(200, [{"id": "k2", "name": "mine", "key": PUB}]),
        ("POST", "/instances"): Resp(202, "inst-1"),
        ("GET", "/instances/inst-1"): [Resp(200, {**INSTANCE, "status": "provisioning", "ip": None}), Resp(200, INSTANCE)],
    })
    monkeypatch.setattr(verda, "POLL_SECONDS", 0)
    verda.cmd_up(c, up_args())
    body = http.find("POST", "/instances")[0].json
    assert body["instance_type"] == "1A100.22V"
    assert body["location_code"] == "FIN-03"
    assert body["ssh_key_ids"] == ["k2"]
    assert body["image"] == verda.DEFAULT_IMAGE and "cuda" in body["image"]
    assert body["is_spot"] is False
    state = json.loads((paths / ".state.json").read_text())
    assert state["instance_id"] == "inst-1" and state["ip"] == "203.0.113.5" and state["price_per_hour"] == 1.571
    assert "1.571 eur per hour" in capsys.readouterr().out


def test_up_refuses_second_instance(paths):
    (paths / ".state.json").write_text(json.dumps({"instance_id": "old"}))
    c, http = client({})
    with pytest.raises(verda.VerdaError, match="already"):
        verda.cmd_up(c, up_args())
    assert not http.calls


def test_up_with_unknown_image_creates_nothing(paths):
    c, http = client({("GET", "/images"): IMAGES})
    with pytest.raises(verda.VerdaError, match="(?s)does not exist.*ubuntu-22.04-cuda-13.0-open") as e:
        verda.cmd_up(c, up_args(image="ubuntu-99.04-cuda-13.0-open"))
    assert "ubuntu-24.04," not in str(e.value)
    assert not http.find("POST", "/instances")
    assert not (paths / ".state.json").exists()


def test_up_without_capacity_creates_nothing(paths):
    c, http = client({
        ("GET", "/images"): IMAGES,
        ("GET", "/instance-types"): TYPES,
        ("GET", "/instance-availability"): Resp(200, [{"location_code": "FIN-01", "availabilities": []}]),
    })
    with pytest.raises(verda.VerdaError, match="not available"):
        verda.cmd_up(c, up_args())
    assert not http.find("POST", "/instances")
    assert not (paths / ".state.json").exists()


def test_wait_running_stops_on_failed_status():
    c, _ = client({("GET", "/instances/inst-1"): Resp(200, {**INSTANCE, "status": "no_capacity", "ip": None})})
    with pytest.raises(verda.VerdaError, match="no_capacity"):
        verda.wait_running(c, "inst-1", sleep=lambda s: None)


def test_failure_prints_warning_with_instance_id(paths, capsys):
    (paths / ".state.json").write_text(json.dumps({"instance_id": "inst-1", "price_per_hour": 1.571, "currency": "eur"}))
    c, _ = client({("GET", "/instances"): Resp(500, {"code": "server_error", "message": "boom"})})
    assert verda.main(["status"], client=c) == 1
    err = capsys.readouterr().err
    assert "WARNING: instance inst-1" in err and "down" in err


def test_missing_credentials_fail_with_warning(paths, capsys):
    (paths / ".state.json").write_text(json.dumps({"instance_id": "inst-1"}))
    c = verda.Client(http=FakeHttp({}))
    assert verda.main(["status"], client=c) == 1
    err = capsys.readouterr().err
    assert "does not exist" in err and "inst-1" in err


def test_down_deletes_instance_and_volumes(paths):
    (paths / ".state.json").write_text(json.dumps({"instance_id": "inst-1", "ip": "203.0.113.5"}))
    (paths / ".known-hosts").write_text("x")
    c, http = client({
        ("GET", "/instances/inst-1"): Resp(200, INSTANCE),
        ("PUT", "/instances"): Resp(202, [{"instanceId": "inst-1", "action": "delete", "status": "success"}]),
    })
    assert verda.cmd_down(c, verda.parser().parse_args(["down", "--yes"])) == 0
    body = http.find("PUT", "/instances")[0].json
    assert body == {"action": "delete", "id": "inst-1", "volume_ids": ["vol-data", "vol-os"], "delete_permanently": True}
    assert not (paths / ".state.json").exists() and not (paths / ".known-hosts").exists()


def test_down_asks_for_confirmation(paths):
    (paths / ".state.json").write_text(json.dumps({"instance_id": "inst-1"}))
    c, http = client({("GET", "/instances/inst-1"): Resp(200, INSTANCE)})
    assert verda.cmd_down(c, verda.parser().parse_args(["down"]), ask=lambda prompt: "no") == 1
    assert not http.find("PUT", "/instances")
    assert (paths / ".state.json").exists()


def test_down_reports_delete_error(paths):
    (paths / ".state.json").write_text(json.dumps({"instance_id": "inst-1"}))
    c, _ = client({
        ("GET", "/instances/inst-1"): Resp(200, INSTANCE),
        ("PUT", "/instances"): Resp(207, [{"instanceId": "inst-1", "action": "delete", "status": "error", "error": "stuck"}]),
    })
    with pytest.raises(verda.VerdaError, match="stuck"):
        verda.cmd_down(c, verda.parser().parse_args(["down", "--yes"]))
    assert (paths / ".state.json").exists()


def test_down_clears_state_when_instance_is_gone(paths):
    (paths / ".state.json").write_text(json.dumps({"instance_id": "inst-1"}))
    c, _ = client({("GET", "/instances/inst-1"): Resp(404, {"code": "not_found", "message": "gone"})})
    assert verda.cmd_down(c, verda.parser().parse_args(["down", "--yes"])) == 0
    assert not (paths / ".state.json").exists()


def test_types_lists_a100_without_credentials(paths, capsys):
    c = verda.Client(http=FakeHttp({("GET", "/instance-types"): TYPES}))
    assert verda.main(["types"], client=c) == 0
    out = capsys.readouterr().out
    assert "1A100.22V" in out and "1.571" in out and "H100" not in out and "availability unknown" in out


def test_render_script_splits_count_and_seeds():
    script = verda.render_script("base", "base", 10, 7, 3)
    assert verda.split_count(10, 3) == [4, 3, 3]
    assert "--profile synth/profiles/base.json --count 4 --seed 7000 --out data/synth/base/part-00" in script
    assert "--profile synth/profiles/dark.json" in verda.render_script("d", "synth/profiles/dark.json", 1, 0, 1)
    assert "--count 3 --seed 7002 --out data/synth/base/part-02" in script
    assert script.count("wait $pid") == 3 and script.endswith("exit $status")


def test_render_seeds_of_nearby_runs_do_not_overlap():
    def seeds(seed):
        words = verda.render_script("x", "base", 60, seed, 8).split()
        return {words[i + 1] for i, w in enumerate(words) if w == "--seed"}
    assert len(seeds(0)) == 8 and not seeds(0) & seeds(1)


def test_fetch_install_copies_weights(paths, monkeypatch):
    monkeypatch.setattr(verda, "ROOT", paths / "repo")
    monkeypatch.setattr(verda, "WEIGHTS", paths / "rex615.pt")
    (paths / ".state.json").write_text(json.dumps({"instance_id": "inst-1", "ip": "203.0.113.5"}))

    def fake_run(cmd, check=True, **kw):
        for name in ("best.pt", "results.csv", "args.yaml"):
            (paths / "repo/models/runs/run-a" / name).write_text(name)

    monkeypatch.setattr(verda, "run", fake_run)
    verda.cmd_fetch(None, verda.parser().parse_args(["fetch", "--name", "run-a"]))
    assert not (paths / "rex615.pt").exists()
    verda.cmd_fetch(None, verda.parser().parse_args(["fetch", "--name", "run-a", "--install"]))
    assert (paths / "rex615.pt").read_text() == "best.pt"


def test_train_script():
    s = verda.train_script("base", "yolo26m.pt", 30, 16, "run-a")
    assert s == ".venv/bin/python train/train.py --data data/synth/base --model yolo26m.pt --epochs 30 --batch 16 --name run-a --project runs"


def test_sync_never_sends_scan_data(paths, monkeypatch):
    root = paths / "repo"
    for d in ("pipeline", "synth", "train", "data/scan", "data/real-test"):
        (root / d).mkdir(parents=True)
    (root / "cloud_0.e57").write_text("x")
    (root / "9PAA00000215617_master.jpg").write_text("x")
    monkeypatch.setattr(verda, "ROOT", root)
    (paths / ".state.json").write_text(json.dumps({"instance_id": "inst-1", "ip": "203.0.113.5"}))
    cmds = []
    monkeypatch.setattr(verda, "run", lambda cmd, check=True, **kw: cmds.append(list(map(str, cmd))))
    verda.cmd_sync(None, None)
    rsync = next(c for c in cmds if c[0] == "rsync")
    sources = [x for x in rsync[rsync.index("-e") + 2:-1] if not x.startswith("--")]
    assert sources == ["pipeline", "synth", "train", "9PAA00000215617_master.jpg"]
    assert "--exclude=*.e57" in rsync and rsync[-1] == "root@203.0.113.5:rex/"


def make_part(root, name, train_dir="images/train"):
    part = root / name
    for d in ("images/train", "images/val"):
        (part / d).mkdir(parents=True)
    (part / "data.yaml").write_text(yaml.safe_dump({"path": ".", "train": train_dir, "val": "images/val", "names": {0: "rex615"}}))
    return part


def test_resolve_data_merges_parts_added_later(tmp_path):
    make_part(tmp_path, "part-00")
    first = yaml.safe_load(train.resolve_data(tmp_path).read_text())
    make_part(tmp_path, "part-01")
    out = train.resolve_data(tmp_path)
    data = yaml.safe_load(out.read_text())
    assert out.name == "data-resolved.yaml" and not (tmp_path / "data.yaml").exists()
    assert len(first["train"]) == 1 and len(data["train"]) == 2 and len(data["val"]) == 2
    assert data["names"] == {0: "rex615"}


def test_resolve_data_single_data_yaml(tmp_path):
    part = make_part(tmp_path, "ds")
    data = yaml.safe_load(train.resolve_data(part).read_text())
    assert data["train"] == [str((part / "images/train").resolve())]


@pytest.mark.parametrize("split", ["train", "val"])
def test_resolve_data_refuses_real_test(tmp_path, split):
    real = tmp_path / "real-test" / "images"
    real.mkdir(parents=True)
    part = make_part(tmp_path, "part-00")
    data = yaml.safe_load((part / "data.yaml").read_text())
    data[split] = [data[split], str(real)]
    (part / "data.yaml").write_text(yaml.safe_dump(data))
    with pytest.raises(SystemExit, match="real test"):
        train.resolve_data(tmp_path)


def test_up_body_has_only_schema_fields(paths, monkeypatch):
    monkeypatch.setattr(verda, "wait_ssh", lambda ip: None)
    monkeypatch.setattr(verda, "POLL_SECONDS", 0)
    c, http = client({
        ("GET", "/images"): IMAGES,
        ("GET", "/instance-types"): TYPES,
        ("GET", "/instance-availability"): AVAIL,
        ("GET", "/ssh-keys"): Resp(200, [{"id": "k2", "name": "mine", "key": PUB}]),
        ("POST", "/instances"): Resp(202, "inst-1"),
        ("GET", "/instances/inst-1"): Resp(200, INSTANCE),
    })
    verda.cmd_up(c, up_args())
    allowed = {"instance_type", "image", "ssh_key_ids", "startup_script_id", "hostname", "description", "tags",
               "location_code", "os_volume", "is_spot", "coupon", "volumes", "existing_volumes", "contract", "pricing"}
    assert set(http.find("POST", "/instances")[0].json) <= allowed


def test_up_create_error_tells_to_check_status(paths):
    c, _ = client({
        ("GET", "/images"): IMAGES,
        ("GET", "/instance-types"): TYPES,
        ("GET", "/instance-availability"): AVAIL,
        ("GET", "/ssh-keys"): Resp(200, [{"id": "k2", "name": "mine", "key": PUB}]),
        ("POST", "/instances"): Resp(503, {"code": "service_unavailable", "message": "later"}),
    })
    with pytest.raises(verda.VerdaError, match="check with 'status'"):
        verda.cmd_up(c, up_args())
    assert not (paths / ".state.json").exists()


def test_up_interrupt_during_create_tells_to_check_status(paths, capsys):
    def interrupt(body):
        raise KeyboardInterrupt
    c, _ = client({
        ("GET", "/images"): IMAGES,
        ("GET", "/instance-types"): TYPES,
        ("GET", "/instance-availability"): AVAIL,
        ("GET", "/ssh-keys"): Resp(200, [{"id": "k2", "name": "mine", "key": PUB}]),
        ("POST", "/instances"): interrupt,
    })
    assert verda.main(["up"], client=c) == 1
    assert "check with 'status'" in capsys.readouterr().err


def fake_ssh(results):
    calls = []

    def run(cmd, check=True, **kw):
        calls.append(cmd[-1])
        code, out = results.pop(0)
        return SimpleNamespace(returncode=code, stdout=out)
    return run, calls


@pytest.mark.parametrize("probe", [(0, "running\n"), (255, "")])
def test_remote_job_lost_stream_is_not_a_failure(monkeypatch, probe):
    run, calls = fake_ssh([(0, "4242\n"), (255, ""), probe])
    monkeypatch.setattr(verda, "run", run)
    with pytest.raises(verda.VerdaError, match="stopped following remote job train-a .pid 4242.; it can still run"):
        verda.remote_job("203.0.113.5", "train-a", "true")
    assert "kill -0 4242" in calls[-1]


@pytest.mark.parametrize("probe,match", [((0, "0\n"), None), ((0, "2\n"), "failed .exit 2"), ((1, ""), "failed .exit unknown")])
def test_remote_job_exit_codes(monkeypatch, probe, match):
    run, _ = fake_ssh([(0, "4242\n"), (0, ""), probe])
    monkeypatch.setattr(verda, "run", run)
    if match is None:
        assert verda.remote_job("203.0.113.5", "train-a", "true") == 0
    else:
        with pytest.raises(verda.VerdaError, match=match):
            verda.remote_job("203.0.113.5", "train-a", "true")


def test_time_cap_stops_before_budget(monkeypatch):
    trainer = SimpleNamespace(train_time_start=0.0, start_epoch=0, epoch=0, stop=False)
    check = train.time_cap(1.0)
    for epoch, now, stop in [(0, 600.0, False), (4, 2900.0, False), (5, 3100.0, True)]:
        trainer.epoch, trainer.stop = epoch, False
        monkeypatch.setattr(train.time, "time", lambda now=now: now)
        check(trainer)
        assert trainer.stop is stop
