"""Render the SmartRFP combined film+tour HTML to an MP4 via headless Chromium.

Usage:
  python render.py --sample              # grab a few preview frames (PNG) for review
  python render.py --out smartrfp.mp4    # full render to MP4
  python render.py --out x.mp4 --fps 24 --scale 1.5 --start 0 --end 30   # custom

Serves the folder over HTTP (Babel can't fetch external .jsx under file://),
drives a deterministic timeline via window.__setTime, screenshots the
#rfp-canvas element per frame, and pipes JPEG frames to a bundled ffmpeg.
"""
import argparse, functools, http.server, os, socket, subprocess, sys, threading, time
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
CLIP = {"x": 0, "y": 0, "width": 1280, "height": 720}

def start_server():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k): super().__init__(*a, directory=HERE, **k)
        def log_message(self, *a): pass
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), Quiet)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port

def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def boot_page(pw, port, scale, page_path="index.html", w=1280, h=720):
    browser = pw.chromium.launch(args=["--force-color-profile=srgb", "--disable-lcd-text"])
    page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
    errors = []
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.goto(f"http://127.0.0.1:{port}/{page_path}?render=1", wait_until="load")
    # wait for harness + fonts + images
    page.wait_for_function("window.__ready === true", timeout=60000)
    page.wait_for_function("document.fonts.ready.then(()=>true)", timeout=30000)
    total = page.evaluate("window.__duration")
    # warm a frame so images start loading, then wait for all images decoded
    page.evaluate("window.__setTime(0.01)")
    page.evaluate("""async () => {
      const imgs = Array.from(document.images);
      await Promise.all(imgs.map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; })));
    }""")
    return browser, page, total, errors

def seek_and_settle(page, t):
    # single round-trip: set time, wait two paints, and only block on images that
    # aren't decoded yet (empty/near-free once a scene's screenshot is cached).
    page.evaluate("""async (t) => {
      window.__setTime(t);
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      const imgs = Array.from(document.images).filter(i => !i.complete);
      if (imgs.length) await Promise.all(imgs.map(i => new Promise(r => { i.onload = i.onerror = r; })));
    }""", t)

def render_video(args, port):
    """Real-time capture: let the timeline auto-play and record with Playwright,
    then transcode the webm to a clean H.264 MP4. Fast (~real-time) vs frame-stepping."""
    import tempfile, glob, shutil
    vdir = tempfile.mkdtemp(prefix="smartrfp_vid_")
    W, H = args.width, args.height
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--force-color-profile=srgb", "--autoplay-policy=no-user-gesture-required"])
        ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1,
                                  record_video_dir=vdir, record_video_size={"width": W, "height": H})
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{port}/{args.page}?render=1", wait_until="load")
        page.wait_for_function("window.__ready === true", timeout=60000)
        page.wait_for_function("document.fonts.ready.then(()=>true)", timeout=30000)
        total = page.evaluate("window.__duration")
        # warm all images so first frames aren't blank
        page.evaluate("window.__setTime(0.01)")
        page.evaluate("""async () => { const xs=[...document.images]; await Promise.all(xs.map(i=>i.complete?0:new Promise(r=>{i.onload=i.onerror=r;}))); }""")
        page.evaluate("window.__setTime(0)")
        print(f"[video] recording real-time · TOTAL={total:.1f}s")
        t0 = time.time()
        page.evaluate("window.__play()")
        page.wait_for_function("window.__done === true", timeout=int((total + 30) * 1000))
        print(f"[video] playback done in {time.time()-t0:.0f}s · finalizing webm")
        page.wait_for_timeout(400)
        ctx.close()          # flushes the video file
        browser.close()
    webms = glob.glob(os.path.join(vdir, "*.webm"))
    if not webms:
        print("[video] ERROR: no webm produced"); return
    webm = max(webms, key=os.path.getsize)
    outpath = os.path.join(HERE, args.out)
    vf = ("scale=1920:1080:flags=lanczos," if H < 1080 else "") + "format=yuv420p"
    # The webm includes a static lead (page-load → __play). Keep only the playback
    # window by seeking to the last `total` seconds from the end.
    ff = [ffmpeg_exe(), "-y", "-sseof", f"-{total + 0.15:.2f}", "-i", webm, "-t", f"{total:.2f}",
          "-vf", vf, "-r", str(args.fps),
          "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-movflags", "+faststart", outpath]
    print("[video] transcoding webm -> mp4")
    subprocess.run(ff, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(vdir, ignore_errors=True)
    sz = os.path.getsize(outpath) / 1e6 if os.path.exists(outpath) else 0
    print(f"[video] DONE -> {outpath} ({sz:.1f} MB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--video", action="store_true", help="fast real-time capture via Playwright video recording")
    ap.add_argument("--page", default="index.html")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--out", default="SmartRFP-Final.mp4")
    ap.add_argument("--fps", type=float, default=24)
    ap.add_argument("--scale", type=float, default=1.5)   # 1.5 → 1920x1080 output
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--quality", type=int, default=92)
    ap.add_argument("--times", default=None, help="comma-separated seconds for --sample")
    ap.add_argument("--calib", action="store_true", help="overlay coordinate grid (DemoShot)")
    args = ap.parse_args()

    global CLIP
    CLIP = {"x": 0, "y": 0, "width": args.width, "height": args.height}

    httpd, port = start_server()

    if args.video:
        return render_video(args, port)

    with sync_playwright() as pw:
        browser, page, total, errors = boot_page(pw, port, args.scale, args.page, args.width, args.height)
        print(f"[render] harness ready · TOTAL={total:.2f}s · viewport 1280x720 @ {args.scale}x")

        if args.calib:
            page.evaluate("window.__CALIB = true")
        if args.sample:
            if args.times:
                samples = {f"t{float(x):g}": float(x) for x in args.times.split(",")}
            else:
                samples = {
                    "01-title": 5, "02-flow": 70, "03-match": 150, "04-match-inset": 174,
                    "05-dash": 200, "06-dash-inset": 219, "07-email-newrfp": 282, "08-email-picked": 287,
                    "09-email-status": 296, "10-reminder": 321, "11-analytics-inset": 369,
                    "12-value": 450, "13-tour-intro": 462, "14-tour-login": 469, "15-tour-dash": 480,
                    "16-tour-match": 530, "17-tour-audit": 600, "18-tour-outro": int(total) - 6,
                }
            outdir = os.path.join(HERE, "samples"); os.makedirs(outdir, exist_ok=True)
            for name, t in samples.items():
                if t >= total: continue
                seek_and_settle(page, t)
                page.screenshot(path=os.path.join(outdir, f"{name}.png"), clip=CLIP)
                print(f"  sample {name} @ {t}s")
            if errors:
                print("\n[render] JS messages:"); [print("  " + e) for e in errors[:40]]
            else:
                print("[render] no JS errors")
            browser.close(); httpd.shutdown(); return

        # full render → pipe JPEG frames to ffmpeg
        end = args.end if args.end is not None else total
        nframes = int(round((end - args.start) * args.fps))
        outpath = os.path.join(HERE, args.out)
        ff = [ffmpeg_exe(), "-y", "-f", "image2pipe", "-framerate", str(args.fps),
              "-i", "-", "-vf", "scale=1920:1080:flags=lanczos,format=yuv420p",
              "-c:v", "libx264", "-preset", "medium", "-crf", "18",
              "-movflags", "+faststart", "-r", str(args.fps), outpath]
        proc = subprocess.Popen(ff, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.time()
        for f in range(nframes):
            tt = args.start + f / args.fps
            seek_and_settle(page, tt)
            jpg = page.screenshot(type="jpeg", quality=args.quality, clip=CLIP)
            proc.stdin.write(jpg)
            if f % 120 == 0 or f == nframes - 1:
                el = time.time() - t0
                eta = (el / (f + 1)) * (nframes - f - 1)
                print(f"  frame {f+1}/{nframes} ({tt:.1f}s) · {el:.0f}s elapsed · ETA {eta/60:.1f}m", flush=True)
        proc.stdin.close(); proc.wait()
        browser.close(); httpd.shutdown()
        if errors:
            print("[render] JS messages during render:"); [print("  " + e) for e in errors[:20]]
        sz = os.path.getsize(outpath) / 1e6 if os.path.exists(outpath) else 0
        print(f"[render] DONE → {outpath} ({sz:.1f} MB, {nframes} frames @ {args.fps}fps)")

if __name__ == "__main__":
    main()
