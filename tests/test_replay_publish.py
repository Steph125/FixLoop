"""Publication GitHub Pages (spec/07-replay-mode, RPL-T11).

`replay/publish.py` copie les sessions choisies vers `replay/published/`
(suivi par git) + `index.json` + `links.json`, sans déclencher le workflow.
Aucun réseau.
"""

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "replay"))

import deploy_check  # noqa: E402
import publish  # noqa: E402
from build_replay import build  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def synthetic(name, **kw):
    base = {"name": name, "title": f"Session {name}", "filmed": "2026-10-31",
            "source": "synthetic", "debounce_frames": 4, "bike_id": "demo-velo",
            "demo_history": False, "segments": [["off", 2], ["on", 4]],
            "user_done": [1.5, 3.0]}
    base.update(kw)
    return base


def build_two(build_dir, bikes):
    for name in ("pub-A", "pub-B"):
        build(synthetic(name), build_dir, bikes_root=bikes / name)


def test_publish_copies_chosen_sessions_and_links(tmp_path):
    build_dir = tmp_path / "build"
    build_two(build_dir, tmp_path / "bikes")
    dest = tmp_path / "published"
    info = publish.publish(["pub-A"], build_dir=build_dir, published_dir=dest)
    assert (dest / "pub-A" / "video.mp4").is_file()
    assert (dest / "pub-A" / "meta.json").is_file()
    assert not (dest / "pub-B").exists()  # non choisie : non publiée
    index = json.loads((dest / "index.json").read_text(encoding="utf-8"))
    assert [s["name"] for s in index] == ["pub-A"]  # ces sessions seulement
    links = json.loads((dest / "links.json").read_text(encoding="utf-8"))
    assert links["repo"] == "https://github.com/Steph125/FixLoop"
    assert links["benchmark"].startswith("https://github.com/")  # RPL-T7 : lien GitHub
    assert links["benchmark"].endswith("eval/benchmark/report.md")
    assert "video" not in links and "live" not in links  # absents = non affichés
    assert info["sessions"] == ["pub-A"]


def test_publish_with_video_and_live_urls(tmp_path):
    build_dir = tmp_path / "build"
    build_two(build_dir, tmp_path / "bikes")
    dest = tmp_path / "published"
    publish.publish(["pub-A", "pub-B"], build_dir=build_dir, published_dir=dest,
                    video="https://example.invalid/demo.mp4",
                    live="https://example.invalid/direct")
    links = json.loads((dest / "links.json").read_text(encoding="utf-8"))
    assert links["video"] == "https://example.invalid/demo.mp4"
    assert links["live"] == "https://example.invalid/direct"
    index = json.loads((dest / "index.json").read_text(encoding="utf-8"))
    assert [s["name"] for s in index] == ["pub-A", "pub-B"]


def assemble_site_like_pages_yml(tmp_path):
    """Assemble public/ comme .github/workflows/pages.yml (sans le déclencher)."""
    build_dir = tmp_path / "build"
    build_two(build_dir, tmp_path / "bikes")
    published = tmp_path / "published"
    publish.publish(["pub-A"], build_dir=build_dir, published_dir=published)
    site = tmp_path / "public"
    (site / "build").mkdir(parents=True)
    for name in ("replay.html", "replay.js", "style.css", "lib.js"):
        shutil.copy(ROOT / "web" / name, site / name)
    shutil.copy(ROOT / "web" / "replay.html", site / "index.html")  # pages.yml
    for child in (published).iterdir():
        target = site / "build" / child.name
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy(child, target)
    return site


def test_deploy_check_accepts_published_site(tmp_path):
    site = assemble_site_like_pages_yml(tmp_path)
    assert deploy_check.check_build(site) == []  # RPL-T11 : publiable


def test_deploy_check_refuses_external_fetch(tmp_path):
    site = assemble_site_like_pages_yml(tmp_path)
    js = site / "replay.js"
    js.write_text(js.read_text(encoding="utf-8") + '\nfetch("https://example.invalid/x");\n',
                  encoding="utf-8")
    errors = deploy_check.check_build(site)
    assert any("externe" in e for e in errors)  # RPL-R1.4 : aucun appel externe


def test_deploy_check_refuses_secrets_and_big_video(tmp_path):
    site = assemble_site_like_pages_yml(tmp_path)
    (site / "build" / ".env").write_text("MODEL_API_KEY=xyz\n", encoding="utf-8")
    (site / "build" / "costs.jsonl").write_text("{}\n", encoding="utf-8")
    video = site / "build" / "pub-A" / "video.mp4"
    with video.open("r+b") as fh:  # 16 Mo épars, jamais commité (tmp_path)
        fh.seek(16 * 1024 * 1024)
        fh.write(b"\x00")
    errors = deploy_check.check_build(site)
    assert any(".env" in e for e in errors)
    assert any(".jsonl" in e for e in errors)
    assert any("15" in e for e in errors)  # RPL-R7.1 : vidéo de plus de 15 Mo


def test_deploy_check_refuses_video_copied_without_ffmpeg(tmp_path):
    site = assemble_site_like_pages_yml(tmp_path)
    meta_path = site / "build" / "pub-A" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["video_codec"] = "opencv-mp4v"  # construite sans ffmpeg (RPL-D5)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    errors = deploy_check.check_build(site)
    assert any("opencv-mp4v" in e for e in errors)  # mal lue sur téléphone : refusée
