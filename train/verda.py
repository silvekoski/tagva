import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = "https://api.verda.com/v1"
ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
STATE_FILE = ROOT / "train" / ".state.json"
KNOWN_HOSTS = ROOT / "train" / ".known-hosts"
SSH_KEY = Path("~/.ssh/verda_ed25519").expanduser()
SSH_USER = "root"
REMOTE_DIR = "rex"
SYNC_DIRS = ("pipeline", "synth", "train")
REFERENCE_PHOTOS = "9PAA*_master.jpg"
SYNC_EXCLUDES = ("__pycache__", ".DS_Store", ".state.json", ".known-hosts", "*.e57", "*.pt", ".venv*", "real-test/")
FETCH_FILES = ("weights/best.pt", "results.csv", "args.yaml")
DEFAULT_TYPE = "1A100.22V"
DEFAULT_IMAGE = "ubuntu-24.04-cuda-13.0-open"
DEFAULT_HOSTNAME = "rex615-train"
OS_VOLUME_GB = 100
FAILED_STATES = {"error", "no_capacity", "installation_failed", "discontinued", "notfound"}
POLL_SECONDS = 10
UP_TIMEOUT = 1800
SEED_STRIDE = 1000
WEIGHTS = ROOT / "models" / "rex615.pt"
USER_AGENT = "rex615-train/0.1"


class VerdaError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def read_env(path):
    values = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip().removeprefix("export ").strip()] = value.strip().strip("'\"")
    return values


def credentials(path=None):
    path = path or ENV_FILE
    env = read_env(path)
    cid = os.environ.get("VERDA_CLIENT_ID") or env.get("VERDA_CLIENT_ID")
    secret = os.environ.get("VERDA_CLIENT_SECRET") or env.get("VERDA_CLIENT_SECRET")
    if not cid or not secret:
        where = f"{path} has no VERDA_CLIENT_ID or VERDA_CLIENT_SECRET" if path.is_file() else f"{path} does not exist"
        raise VerdaError(
            f"Verda credentials are missing: {where}. Create the file with the lines\n"
            "  VERDA_CLIENT_ID=...\n  VERDA_CLIENT_SECRET=...\n"
            "Get the values in https://console.verda.com under Keys, Cloud API credentials."
        )
    return cid, secret


class Client:
    def __init__(self, client_id=None, client_secret=None, http=None, base_url=BASE_URL):
        self.client_id, self.client_secret = client_id, client_secret
        self.http = http or requests.Session()
        self.base_url = base_url
        self.token, self.token_expires = None, 0.0

    def authenticate(self):
        if not self.client_id or not self.client_secret:
            self.client_id, self.client_secret = credentials()
        body = {"grant_type": "client_credentials", "client_id": self.client_id, "client_secret": self.client_secret}
        data = self.request("POST", "/oauth2/token", json=body, auth=False)
        self.token = data["access_token"]
        self.token_expires = time.time() + float(data["expires_in"]) - 60

    def request(self, method, path, json=None, params=None, auth=True, retry=True):
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if auth:
            if not self.token or time.time() >= self.token_expires:
                self.authenticate()
            headers["Authorization"] = f"Bearer {self.token}"
        r = self.http.request(method, self.base_url + path, json=json, params=params, headers=headers, timeout=60)
        if r.status_code == 401 and auth and retry:
            self.token = None
            return self.request(method, path, json=json, params=params, auth=auth, retry=False)
        if r.status_code >= 400:
            try:
                err = r.json()
                detail = f"{err.get('code', '')}: {err.get('message', '')}"
            except ValueError:
                detail = r.text[:300]
            raise VerdaError(f"{method} {path} failed with HTTP {r.status_code} ({detail})", r.status_code)
        if not r.content:
            return None
        try:
            return r.json()
        except ValueError:
            return r.text.strip()

    def instance_types(self, currency="eur"):
        return self.request("GET", "/instance-types", params={"currency": currency}, auth=False)

    def availability(self):
        return self.request("GET", "/instance-availability")

    def images(self):
        return self.request("GET", "/images")

    def ssh_keys(self):
        return self.request("GET", "/ssh-keys")

    def add_ssh_key(self, name, key):
        return response_id(self.request("POST", "/ssh-keys", json={"name": name, "key": key}))

    def create_instance(self, body):
        return response_id(self.request("POST", "/instances", json=body))

    def instance(self, instance_id):
        return self.request("GET", f"/instances/{instance_id}")

    def instances(self):
        return self.request("GET", "/instances")

    def delete_instance(self, instance_id, volume_ids):
        body = {"action": "delete", "id": instance_id, "volume_ids": volume_ids, "delete_permanently": True}
        return self.request("PUT", "/instances", json=body)

    def balance(self):
        return self.request("GET", "/balance")


def response_id(data):
    if isinstance(data, dict):
        data = data.get("id")
    if not isinstance(data, str) or not data.strip('"'):
        raise VerdaError(f"unexpected create response: {data!r}")
    return data.strip('"')


def load_state():
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.is_file() else {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def clear_state():
    STATE_FILE.unlink(missing_ok=True)
    KNOWN_HOSTS.unlink(missing_ok=True)


def a100_types(types):
    return [t for t in types if "A100" in t.get("model", "") + t.get("instance_type", "")]


def locations_for(availability, instance_type):
    return [a["location_code"] for a in availability if instance_type in a.get("availabilities", [])]


def public_key_body(text):
    return " ".join(text.split()[:2])


def ensure_ssh_key(client, key_path=None):
    key_path = key_path or SSH_KEY
    pub = key_path.with_name(key_path.name + ".pub")
    if not pub.is_file():
        raise VerdaError(f"public key {pub} does not exist")
    body = public_key_body(pub.read_text())
    for k in client.ssh_keys():
        if public_key_body(k.get("key", "")) == body:
            return k["id"]
    key_id = client.add_ssh_key(f"{key_path.name}-{DEFAULT_HOSTNAME}", pub.read_text().strip())
    print(f"added SSH key {key_path.name} to Verda: {key_id}")
    return key_id


def price_of(client, instance_type, currency):
    for t in client.instance_types(currency):
        if t["instance_type"] == instance_type:
            return float(t["price_per_hour"]), t.get("currency", currency)
    raise VerdaError(f"unknown instance type {instance_type}")


def wait_running(client, instance_id, timeout=UP_TIMEOUT, poll=None, sleep=time.sleep):
    start, last = time.time(), None
    while True:
        inst = client.instance(instance_id)
        status = inst.get("status")
        if status != last:
            print(f"status: {status}", flush=True)
            last = status
        if status == "running" and inst.get("ip"):
            return inst
        if status in FAILED_STATES:
            raise VerdaError(f"instance {instance_id} reached status {status}")
        if time.time() - start > timeout:
            raise VerdaError(f"instance {instance_id} is not running after {timeout} s (status {status})")
        sleep(POLL_SECONDS if poll is None else poll)


def ssh_base(ip):
    return [
        "ssh", "-i", str(SSH_KEY), "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"UserKnownHostsFile={KNOWN_HOSTS}", "-o", "ServerAliveInterval=30", "-o", "ConnectTimeout=15",
        f"{SSH_USER}@{ip}",
    ]


def run(cmd, check=True, **kw):
    print("+ " + shlex.join(map(str, cmd)), flush=True)
    r = subprocess.run(list(map(str, cmd)), **kw)
    if check and r.returncode != 0:
        raise VerdaError(f"command failed with exit code {r.returncode}")
    return r


def ssh(ip, command, check=True, **kw):
    return run(ssh_base(ip) + [command], check=check, **kw)


def wait_ssh(ip, timeout=600, sleep=time.sleep):
    start = time.time()
    while subprocess.run(ssh_base(ip) + ["true"], capture_output=True).returncode != 0:
        if time.time() - start > timeout:
            raise VerdaError(f"SSH to {ip} does not answer after {timeout} s")
        sleep(POLL_SECONDS)


def current(state=None):
    state = load_state() if state is None else state
    if not state.get("instance_id"):
        raise VerdaError("no instance in train/.state.json, run 'up' first")
    if not state.get("ip"):
        raise VerdaError(f"instance {state['instance_id']} has no IP in train/.state.json, run 'status'")
    return state


def split_count(count, workers):
    return [count // workers + (k < count % workers) for k in range(workers)]


def profile_path(profile):
    return profile if profile.endswith(".json") else f"synth/profiles/{profile}.json"


def render_script(name, profile, count, seed, workers, extra=""):
    out = f"data/synth/{name}"
    lines = [f"mkdir -p {out} logs", "status=0"]
    parts = [(k, n) for k, n in enumerate(split_count(count, workers)) if n > 0]
    for k, n in parts:
        args = ["--profile", profile_path(profile), "--count", n, "--seed", seed * SEED_STRIDE + k, "--out", f"{out}/part-{k:02d}"]
        cmd = ".venv-bpy/bin/python synth/render.py " + shlex.join(map(str, args)) + (f" {extra}" if extra else "")
        lines.append(f"{cmd} > logs/{name}-part-{k:02d}.log 2>&1 & pid{k}=$!")
    for k, _ in parts:
        log = f"logs/{name}-part-{k:02d}.log"
        lines.append(f"if wait $pid{k}; then echo part-{k:02d} done; else echo part-{k:02d} failed; tail -n 30 {log}; status=1; fi")
    lines.append("exit $status")
    return "\n".join(lines)


def train_script(data, model, epochs, batch, name, extra=""):
    args = ["--data", f"data/synth/{data}", "--model", model, "--epochs", epochs, "--batch", batch, "--name", name, "--project", "runs"]
    return ".venv/bin/python train/train.py " + shlex.join(map(str, args)) + (f" {extra}" if extra else "")


def remote_job(ip, name, script, follow=True, extra_logs=()):
    inner = f"( {script}\n); echo $? > logs/{name}.exit"
    start = (
        f"cd ~/{REMOTE_DIR} || exit 1; mkdir -p logs; rm -f logs/{name}.exit; "
        f"nohup bash -c {shlex.quote(inner)} > logs/{name}.log 2>&1 < /dev/null & echo $!"
    )
    pid = ssh(ip, start, capture_output=True, text=True).stdout.strip().splitlines()[-1]
    print(f"remote job {name} started, pid {pid}, log ~/{REMOTE_DIR}/logs/{name}.log")
    if not follow:
        return None
    logs = " ".join([f"logs/{name}.log"] + list(extra_logs))
    try:
        ssh(ip, f"cd ~/{REMOTE_DIR} && tail -n +1 --pid={pid} -F {logs} 2>/dev/null", check=False)
    except KeyboardInterrupt:
        print(f"\nstopped following; job {name} still runs on the instance (pid {pid})")
        raise
    probe = f"cat ~/{REMOTE_DIR}/logs/{name}.exit 2>/dev/null || (kill -0 {pid} 2>/dev/null && echo running)"
    r = ssh(ip, probe, check=False, capture_output=True, text=True)
    code = r.stdout.strip()
    if code == "running" or r.returncode == 255:
        raise VerdaError(f"stopped following remote job {name} (pid {pid}); it can still run, see ~/{REMOTE_DIR}/logs/{name}.log")
    if code != "0":
        raise VerdaError(f"remote job {name} failed (exit {code or 'unknown'}), see ~/{REMOTE_DIR}/logs/{name}.log")
    print(f"remote job {name} done")
    return 0


def cmd_types(client, a):
    types = a100_types(client.instance_types(a.currency))
    try:
        avail = client.availability()
    except VerdaError as e:
        print(f"availability unknown: {e}")
        avail = None
    for t in types:
        locs = "?" if avail is None else (", ".join(locations_for(avail, t["instance_type"])) or "none")
        print(f"{t['instance_type']:<18} {(t.get('gpu') or {}).get('description', t.get('model', '')):<22} {float(t['price_per_hour']):>7.3f} {t['currency']}/h  "
              f"spot {float(t['spot_price']):.3f}  available: {locs}")


def cmd_images(client, a):
    for i in client.images():
        print(f"{i['image_type']:<40} {i.get('name', '')}")


def cmd_up(client, a):
    state = load_state()
    if state.get("instance_id"):
        raise VerdaError(f"instance {state['instance_id']} is already in train/.state.json; run 'status' or 'down' first")
    images = [i["image_type"] for i in client.images()]
    if a.image not in images:
        cuda = [i for i in images if "cuda" in i] or images
        raise VerdaError(f"image {a.image} does not exist; pass --image with one of: {', '.join(cuda)}")
    price, currency = price_of(client, a.type, a.currency)
    locations = locations_for(client.availability(), a.type)
    location = a.location or (locations[0] if locations else None)
    if location is None or location not in locations:
        raise VerdaError(f"{a.type} is not available (available in: {', '.join(locations) or 'none'})")
    key_id = ensure_ssh_key(client)
    print(f"PRICE: {a.type} costs {price:.3f} {currency} per hour while it exists. Run 'down' when you are done.")
    body = {
        "instance_type": a.type,
        "image": a.image,
        "ssh_key_ids": [key_id],
        "hostname": a.hostname,
        "location_code": location,
        "os_volume": {"name": f"{a.hostname}-os", "size": a.disk},
        "is_spot": False,
        "contract": "PAY_AS_YOU_GO",
    }
    try:
        instance_id = client.create_instance(body)
    except (VerdaError, requests.RequestException, KeyboardInterrupt) as e:
        raise VerdaError(f"create failed ({e!r}); an instance can still exist, check with 'status'") from e
    state = {
        "instance_id": instance_id,
        "instance_type": a.type,
        "location": location,
        "price_per_hour": price,
        "currency": currency,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    save_state(state)
    print(f"created instance {instance_id} in {location}")
    inst = wait_running(client, instance_id)
    state["ip"] = inst["ip"]
    save_state(state)
    wait_ssh(inst["ip"])
    print(f"running: ssh -i {SSH_KEY} {SSH_USER}@{inst['ip']}")


def cmd_sync(client, a):
    ip = current()["ip"]
    photos = sorted(p.name for p in ROOT.glob(REFERENCE_PHOTOS))
    if not photos:
        print(f"warning: no reference photos ({REFERENCE_PHOTOS}) in {ROOT}")
    sources = [d for d in SYNC_DIRS if (ROOT / d).is_dir()] + photos
    excludes = [f"--exclude={e}" for e in SYNC_EXCLUDES]
    ssh(ip, f"mkdir -p ~/{REMOTE_DIR} && (command -v rsync > /dev/null || (apt-get update -q && apt-get install -y -q rsync))")
    run(["rsync", "-az", "--relative", "-e", shlex.join(ssh_base(ip)[:-1]), *excludes, *sources,
         f"{SSH_USER}@{ip}:{REMOTE_DIR}/"], cwd=ROOT)


def cmd_setup(client, a):
    ip = current()["ip"]
    ssh(ip, f"cd ~/{REMOTE_DIR} && bash train/remote-setup.sh")


def cmd_render(client, a):
    ip = current()["ip"]
    name = a.out or f"{Path(a.profile).stem}-s{a.seed}"
    script = render_script(name, a.profile, a.count, a.seed, a.workers, a.extra)
    remote_job(ip, f"render-{name}", script, follow=not a.detach, extra_logs=[f"logs/{name}-part-00.log"])
    print(f"dataset: ~/{REMOTE_DIR}/data/synth/{name}  (train with --data {name})")


def cmd_train(client, a):
    ip = current()["ip"]
    remote_job(ip, f"train-{a.name}", train_script(a.data, a.model, a.epochs, a.batch, a.name, a.extra), follow=not a.detach)


def cmd_fetch(client, a):
    ip = current()["ip"]
    out = ROOT / "models" / "runs" / a.name
    out.mkdir(parents=True, exist_ok=True)
    sources = [f"{SSH_USER}@{ip}:{REMOTE_DIR}/runs/{a.name}/{f}" for f in FETCH_FILES]
    run(["scp", *ssh_base(ip)[1:-1], *sources, str(out)])
    print(f"fetched to {out}")
    if a.install:
        WEIGHTS.write_bytes((out / "best.pt").read_bytes())
        print(f"installed {out / 'best.pt'} as {WEIGHTS}")


def cmd_down(client, a, ask=input):
    state = load_state()
    instance_id = a.id or state.get("instance_id")
    if not instance_id:
        raise VerdaError("no instance id in train/.state.json; pass --id")
    try:
        inst = client.instance(instance_id)
    except VerdaError as e:
        if e.status != 404:
            raise
        print(f"instance {instance_id} does not exist any more")
        if state.get("instance_id") == instance_id:
            clear_state()
        return 0
    volumes = sorted({v for v in [inst.get("os_volume_id"), *(inst.get("volume_ids") or [])] if v})
    print(f"instance {instance_id}: {inst.get('instance_type')} status {inst.get('status')} ip {inst.get('ip')}")
    print(f"volumes to delete: {', '.join(volumes) or 'none'}")
    if not a.yes and ask(f"Delete instance {instance_id} and its volumes? Type 'yes': ").strip() != "yes":
        print("cancelled; the instance still runs")
        return 1
    result = client.delete_instance(instance_id, volumes)
    for item in result or []:
        if item.get("status") == "error":
            raise VerdaError(f"delete failed: {item.get('error')}")
    print(f"deleted instance {instance_id}")
    if state.get("instance_id") == instance_id:
        clear_state()
    return 0


def cmd_status(client, a):
    state = load_state()
    mine = state.get("instance_id")
    if mine:
        print(f"state: {mine} since {state.get('created_at')} ({state.get('price_per_hour')} {state.get('currency')}/h)")
    else:
        print("state: no instance in train/.state.json")
    instances = client.instances() or []
    for inst in instances:
        mark = "*" if inst.get("id") == mine else " "
        print(f"{mark} {inst.get('id')} {inst.get('instance_type')} {inst.get('status')} ip {inst.get('ip')} "
              f"{inst.get('price_per_hour')}/h {inst.get('location')} {inst.get('hostname')}")
        if inst.get("id") == mine and inst.get("ip") and inst.get("ip") != state.get("ip"):
            state["ip"] = inst["ip"]
            save_state(state)
    if mine and not any(i.get("id") == mine for i in instances):
        print(f"warning: {mine} is not in the instance list; it is probably deleted. Remove train/.state.json if so.")
    if not instances:
        print("no instances")
    try:
        bal = client.balance()
        print(f"balance: {bal['amount']} {bal['currency']}")
    except VerdaError as e:
        print(f"balance unknown: {e}")


COMMANDS = {
    "types": cmd_types, "images": cmd_images, "up": cmd_up, "sync": cmd_sync, "setup": cmd_setup, "render": cmd_render,
    "train": cmd_train, "fetch": cmd_fetch, "down": cmd_down, "status": cmd_status,
}


def parser():
    p = argparse.ArgumentParser(description="Verda GPU instance for REX615 synthetic rendering and training.")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("types", help="A100 instance types with price and availability")
    s.add_argument("--currency", default="eur", choices=["eur", "usd"])
    sub.add_parser("images", help="OS images for instances")
    s = sub.add_parser("up", help="create one A100 instance")
    s.add_argument("--type", default=DEFAULT_TYPE)
    s.add_argument("--image", default=DEFAULT_IMAGE)
    s.add_argument("--location", default=None)
    s.add_argument("--hostname", default=DEFAULT_HOSTNAME)
    s.add_argument("--disk", type=int, default=OS_VOLUME_GB, help="OS volume size in GB")
    s.add_argument("--currency", default="eur", choices=["eur", "usd"])
    sub.add_parser("sync", help="rsync pipeline/, synth/, train/ and the reference photos")
    sub.add_parser("setup", help="run train/remote-setup.sh on the instance")
    s = sub.add_parser("render", help="run synth/render.py in parallel processes")
    s.add_argument("--profile", required=True, help="name in synth/profiles/ (base) or a .json path on the instance")
    s.add_argument("--count", type=int, required=True)
    s.add_argument("--seed", type=int, default=0, help=f"worker k uses seed * {SEED_STRIDE} + k")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--out", default=None, help="dataset name below data/synth/ (default PROFILE-sSEED)")
    s.add_argument("--extra", default="", help="extra arguments for synth/render.py")
    s.add_argument("--detach", action="store_true")
    s = sub.add_parser("train", help="run train/train.py")
    s.add_argument("--data", required=True, help="dataset name below data/synth/")
    s.add_argument("--model", default="yolo26s.pt", choices=["yolo26s.pt", "yolo26m.pt"])
    s.add_argument("--epochs", type=int, default=40)
    s.add_argument("--batch", type=int, default=16)
    s.add_argument("--name", required=True)
    s.add_argument("--extra", default="", help="extra arguments for train/train.py, for example '--hours 0.8'")
    s.add_argument("--detach", action="store_true")
    s = sub.add_parser("fetch", help="copy best.pt, results.csv, args.yaml to models/runs/NAME/")
    s.add_argument("--name", required=True)
    s.add_argument("--install", action="store_true", help="also copy best.pt to models/rex615.pt")
    s = sub.add_parser("down", help="delete the instance and its volumes")
    s.add_argument("--yes", action="store_true")
    s.add_argument("--id", default=None)
    sub.add_parser("status", help="list the instances of the project")
    return p


def warn_running(error):
    state = load_state()
    print(f"error: {error}", file=sys.stderr)
    if state.get("instance_id"):
        print(
            f"WARNING: instance {state['instance_id']} ({state.get('instance_type')}, "
            f"{state.get('price_per_hour')} {state.get('currency')}/h) can still be running. "
            "Check it with 'python train/verda.py status' and delete it with 'python train/verda.py down'.",
            file=sys.stderr,
        )


def main(argv=None, client=None):
    a = parser().parse_args(argv)
    client = client or Client()
    try:
        return COMMANDS[a.command](client, a) or 0
    except (VerdaError, requests.RequestException, KeyboardInterrupt) as e:
        warn_running(e if not isinstance(e, KeyboardInterrupt) else "interrupted")
        return 1
    except Exception as e:
        warn_running(repr(e))
        raise


if __name__ == "__main__":
    sys.exit(main())
