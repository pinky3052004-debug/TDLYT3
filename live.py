#!/usr/bin/env python3
"""YouTube broadcast ဖန်တီး + ffmpeg နဲ့ stream (မနက်/ညနေ ၂ ကြိမ် × ၃ channel title)"""
import os, json, time, glob, shutil, subprocess, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

MMT = ZoneInfo("Asia/Yangon")
SESSION = os.environ.get("SESSION", "morning")   # morning | evening | test
TEST = SESSION == "test"

# ---------- ပြင်ရန် ----------
SUFFIXES = [""]                                       # အခု live ၁ ခုတည်း
# SUFFIXES = ["", " VIP", " VVIP"]                    # live ၃ ခု ပြန်လုပ်ချင်ရင် အပေါ်စာကြောင်းကိုဖျက်ပြီး ဒါကိုဖွင့်
SESSIONS = [                                          # မြန်မာအချိန်
    {"name": "morning", "label": "မနက်", "draw": "12:01 PM", "slot": "12:01", "start": "10:30", "end": "12:30", "clip": ("11:59", "12:02")},
    {"name": "evening", "label": "ညနေ", "draw": "04:30 PM", "slot": "16:30", "start": "14:30", "end": "17:00", "clip": ("16:29", "16:32")},
]
PLAYLIST_TITLE = "2D Result {year}"                           # playlist နာမည် (နှစ်အလိုက်အလိုအလျောက်)
CLIP_TITLE = "({date}) {label} ({draw}) 2D ရလဒ်"   # ဖြတ်ထားတဲ့ video ရဲ့ title အသစ်
DESCRIPTION = open(os.path.join(os.path.dirname(__file__), "description.txt"), encoding="utf-8").read().strip()
# -----------------------------
CLIP_DESCRIPTION = DESCRIPTION
UPLOAD_CLIP = os.environ.get("YT_UPLOAD_CLIP", "1") == "1"
BASE = os.path.dirname(os.path.abspath(__file__))
REC_DIR = "/tmp/rec"                       # stream ကို ၁ မိနစ်စီ အပိုင်းလေးတွေအဖြစ် မှတ်တမ်းသိမ်း
CLIPS_DIR = os.path.join(BASE, "clips")

AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")
AUDIO_FILTER = "aresample=44100:async=1,aformat=sample_rates=44100:channel_layouts=stereo,volume=0.6"   # volume ပြင်ရန်

SILENT = ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]

def audio_ok(path):
    """ဖိုင်က တကယ်ဖွင့်လို့ရတဲ့ audio ဟုတ်မဟုတ် ffprobe နဲ့စစ်၊ မကောင်းရင် ကျော်"""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "format=duration", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=30)
        dur = float(r.stdout.strip().split("\n")[0])
        if r.returncode == 0 and dur > 1:
            return True
    except Exception:
        pass
    print("skip bad audio:", os.path.basename(path), flush=True)
    return False

def audio_input():
    """audio/ folder ထဲက သီချင်းတွေကို ရောနှောပြီး အဆုံးမရှိ ပြန်ဖွင့်။ မရှိရင် အသံတိတ်။"""
    import glob, random
    files = [f for ext in ("mp3", "m4a", "wav", "ogg", "flac") for f in glob.glob(os.path.join(AUDIO_DIR, "*." + ext))]
    if not files:
        print("audio/ ထဲမှာ ဖိုင်မရှိ -> အသံတိတ်", flush=True)
        return ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    files = [f for f in files if audio_ok(f)]
    if not files:
        print("audio ဖိုင်အားလုံး မသုံးနိုင် -> အသံတိတ်", flush=True)
        return SILENT
    random.shuffle(files)
    with open("/tmp/playlist.txt", "w", encoding="utf-8") as f:
        for _ in range(max(1, 400 // len(files))):          # ပုံတူရေးထပ် = ပြန်ဖွင့် (stream_loop မသုံး)
            random.shuffle(files)
            for p in files:
                f.write("file '" + p.replace("'", "'\\''") + "'\n")
    print(f"audio playlist: {len(files)} tracks", flush=True)
    return ["-f", "concat", "-safe", "0", "-i", "/tmp/playlist.txt"]

_tok = {"v": None, "exp": 0}

def token():
    if time.time() < _tok["exp"] - 60:
        return _tok["v"]
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data, timeout=30) as r:
        j = json.loads(r.read())
    _tok["v"], _tok["exp"] = j["access_token"], time.time() + j["expires_in"]
    return _tok["v"]

def api(method, path, params=None, body=None, quiet=False):
    url = "https://www.googleapis.com/youtube/v3/" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else (b"" if method == "POST" else None)
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        if not quiet:
            print("API error:", path, e.read().decode()[:500], flush=True)
        raise

def make_title(day, session, suffix):
    d = f"{day.day}.{day.month}.{day.year}"           # 6.10.2026 (သုညမပါ)
    return f"({d}) {session['label']} ({session['draw']}) 2D3D Live တိုက်ရိုက်{suffix}"

def create_broadcast(title):
    start = (datetime.now(timezone.utc) + timedelta(seconds=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # stream key အသစ် (အလိုအလျောက်)
    st = api("POST", "liveStreams", {"part": "snippet,cdn,contentDetails"}, {
        "snippet": {"title": title},
        "cdn": {"frameRate": "variable", "ingestionType": "rtmp", "resolution": "variable"},
        "contentDetails": {"isReusable": False}})
    # broadcast ID အသစ် (အလိုအလျောက်)
    br = api("POST", "liveBroadcasts", {"part": "snippet,status,contentDetails"}, {
        "snippet": {"title": title, "description": DESCRIPTION, "scheduledStartTime": start},
        "status": {"privacyStatus": "private" if TEST else "public", "selfDeclaredMadeForKids": False},
        "contentDetails": {"enableAutoStart": True, "enableAutoStop": True}})
    api("POST", "liveBroadcasts/bind", {"id": br["id"], "part": "id,contentDetails", "streamId": st["id"]})
    info = st["cdn"]["ingestionInfo"]
    key = info["streamName"]
    print("::add-mask::" + key, flush=True)           # log ထဲ key မပေါ်စေရန်
    print(f"created: {br['id']} | {title}", flush=True)
    return {"id": br["id"], "url": info["ingestionAddress"] + "/" + key}

def complete(bid):
    """live ဖြစ်ခဲ့ရင် complete၊ မစခဲ့ဘူးဆိုရင် (stream မတက်) broadcast ကို ဖျက်"""
    try:
        st = api("GET", "liveBroadcasts", {"part": "status", "id": bid}, quiet=True)
        life = st["items"][0]["status"]["lifeCycleStatus"] if st.get("items") else "gone"
        if life in ("live", "testing"):
            api("POST", "liveBroadcasts/transition", {"broadcastStatus": "complete", "id": bid, "part": "status"}, quiet=True)
            print("completed:", bid, flush=True)
        elif life in ("created", "ready"):
            api("DELETE", "liveBroadcasts", {"id": bid}, quiet=True)
            print("never started -> deleted:", bid, flush=True)
        else:
            print("status", life, ":", bid, flush=True)
    except Exception as e:
        print("complete skipped:", bid, flush=True)

def read_result(slot):
    try:
        st = json.load(open(os.path.join(BASE, "state", "state.json"), encoding="utf-8"))
        return " - " + str(st["snapshots"][slot]["twod"])
    except Exception:
        return ""

def make_clip(w0, w1, out):
    """REC_DIR ထဲက အပိုင်းလေးတွေထဲက w0..w1 (UTC) ကို ဖြတ်ပြီး out (mp4) ထုတ်"""
    segs = []
    for f in sorted(glob.glob(os.path.join(REC_DIR, "*.ts"))):
        try:
            t = datetime.strptime(os.path.basename(f)[:15], "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
            segs.append((t, f))
        except ValueError:
            pass
    pick = [(t, f) for t, f in segs if t < w1 and t + timedelta(seconds=75) > w0]
    if not pick:
        print("clip: ဒီအချိန်အတွက် မှတ်တမ်းမရှိ", flush=True); return None
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open("/tmp/clip_list.txt", "w") as f:
        for _, p in pick:
            f.write(f"file '{p}'\n")
    ss = max(0.0, (w0 - pick[0][0]).total_seconds())
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
        "-i", "/tmp/clip_list.txt", "-ss", f"{ss:.2f}", "-t", f"{(w1 - w0).total_seconds():.0f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out])
    if r.returncode != 0 or not os.path.exists(out):
        print("clip: ffmpeg မအောင်မြင်", flush=True); return None
    print("clip saved:", out, flush=True)
    return out

def upload_video(path, title, description, privacy):
    size = os.path.getsize(path)
    meta = {"snippet": {"title": title, "description": description, "categoryId": "24"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(meta).encode(), method="POST", headers={
            "Authorization": "Bearer " + token(), "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"})
    try:
        loc = urllib.request.urlopen(req, timeout=60).headers["Location"]
        with open(path, "rb") as f:
            put = urllib.request.Request(loc, data=f, method="PUT",
                headers={"Content-Length": str(size), "Content-Type": "video/mp4"})
            vid = json.loads(urllib.request.urlopen(put, timeout=900).read())["id"]
        print("uploaded clip:", vid, "|", title, flush=True)
        return vid
    except urllib.error.HTTPError as e:
        print("upload error:", e.read().decode()[:400], flush=True)
    except Exception as e:
        print("upload error:", e, flush=True)

def get_playlist_id(title, privacy):
    """နာမည်တူ playlist ရှိရင်သုံး၊ မရှိရင် အသစ်ဆောက်"""
    page = None
    while True:
        params = {"part": "snippet", "mine": "true", "maxResults": 50}
        if page:
            params["pageToken"] = page
        r = api("GET", "playlists", params)
        for it in r.get("items", []):
            if it["snippet"]["title"] == title:
                return it["id"]
        page = r.get("nextPageToken")
        if not page:
            break
    r = api("POST", "playlists", {"part": "snippet,status"}, {
        "snippet": {"title": title, "description": title},
        "status": {"privacyStatus": privacy}})
    print("created playlist:", title, flush=True)
    return r["id"]

def add_to_playlist(video_id, title, privacy):
    try:
        pid = get_playlist_id(title, privacy)
        api("POST", "playlistItems", {"part": "snippet"}, {"snippet": {
            "playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": video_id}}})
        print("added to playlist:", title, flush=True)
    except Exception as e:
        print("playlist failed:", e, flush=True)

def clip_and_upload(s, day, run_start):
    if TEST:
        w0 = run_start + timedelta(seconds=60); w1 = w0 + timedelta(seconds=120)
    elif s.get("clip"):
        w0 = at(day, s["clip"][0]).astimezone(timezone.utc); w1 = at(day, s["clip"][1]).astimezone(timezone.utc)
    else:
        return
    d = f"{day.day}.{day.month}.{day.year}"
    title = ("TEST " if TEST else "") + CLIP_TITLE.format(date=d, label=s["label"], draw=s["draw"],
                                                           result=read_result(s["slot"]))
    out = make_clip(w0, w1, os.path.join(CLIPS_DIR, f"{day:%Y-%m-%d}_{s['name']}.mp4"))
    if out and UPLOAD_CLIP:
        vid = upload_video(out, title, CLIP_DESCRIPTION, "private" if TEST else "public")
        if vid:
            pl = PLAYLIST_TITLE.format(year=day.year)
            add_to_playlist(vid, ("TEST " + pl) if TEST else pl, "private" if TEST else "public")
    shutil.rmtree(REC_DIR, ignore_errors=True)

def at(day, hhmm):
    h, m = map(int, hhmm.split(":"))
    return datetime(day.year, day.month, day.day, h, m, tzinfo=MMT)

def run_session(s, day):
    now = datetime.now(MMT)
    if TEST:
        end = now + timedelta(minutes=5)
    else:
        start, end = at(day, s["start"]), at(day, s["end"])
        if now >= end:
            print("skip", s["label"]); return
        if now < start:
            time.sleep((start - now).total_seconds())
    broadcasts = []
    for suf in SUFFIXES:
        try:
            broadcasts.append(create_broadcast(("TEST " if TEST else "") + make_title(day, s, suf)))
        except Exception as e:
            print("create failed:", e, flush=True)
    if not broadcasts:
        return
    dur = max(60, int((end - datetime.now(MMT)).total_seconds()))
    shutil.rmtree(REC_DIR, ignore_errors=True); os.makedirs(REC_DIR)
    outs = [f"[f=flv:onfail=ignore]{b['url']}" for b in broadcasts]          # encode တစ်ခါတည်း၊ output ၃ ခု
    outs.append(f"[f=segment:segment_time=60:segment_format=mpegts:strftime=1:reset_timestamps=1:onfail=ignore]{REC_DIR}/%Y%m%d_%H%M%S.ts")
    tee = "|".join(outs)
    run_start = datetime.now(timezone.utc)
    audio = audio_input()
    fails = 0
    while True:
        left = int((end - datetime.now(MMT)).total_seconds())
        if left < 20:
            break
        t0 = time.time()
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "warning",
            "-f", "x11grab", "-draw_mouse", "0", "-framerate", "30", "-video_size", "1280x720", "-i", ":99",
            *audio,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "veryfast", "-b:v", "3000k", "-maxrate", "3000k", "-bufsize", "6000k",
            "-pix_fmt", "yuv420p", "-g", "60", "-af", AUDIO_FILTER, "-c:a", "aac", "-b:a", "128k",
            "-flags", "+global_header", "-t", str(left), "-f", "tee", tee],
            env=dict(os.environ, TZ="UTC"))
        if r.returncode == 0:
            break                                  # အချိန်ပြည့်လို့ ပုံမှန်ပြီး
        fails += 1
        print(f"ffmpeg exited rc={r.returncode} after {int(time.time()-t0)}s (fail #{fails})", flush=True)
        if audio is not SILENT:
            print("-> အသံတိတ်နဲ့ ပြန်ကြိုးစား", flush=True)
            audio = SILENT
        if fails >= 5:
            break
        time.sleep(5)
    for b in broadcasts:
        complete(b["id"])
    try:
        clip_and_upload(s, day, run_start)      # 11:59-12:02 ကို ဖြတ် -> video အသစ် (တစ်ခုတည်း)
    except Exception as e:
        print("clip failed:", e, flush=True)

if __name__ == "__main__":
    day = datetime.now(MMT)
    if TEST:   # test ဆိုရင် လက်ရှိအချိန်နဲ့ကိုက်တဲ့ session ကို ရွေး (13:30 မတိုင်ခင် = မနက်၊ ပြီးရင် ညနေ)
        names = ["morning"] if day.hour * 60 + day.minute < 13 * 60 + 30 else ["evening"]
    else:
        names = [SESSION]
    for s in [x for x in SESSIONS if x["name"] in names]:
        run_session(s, day)
