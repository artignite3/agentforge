import { bundle } from "@remotion/bundler";
import {
  selectComposition,
  renderMedia,
  renderStill,
  ensureBrowser,
  openBrowser,
} from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
const root = path.resolve(import.meta.dirname, "..");
const hash = createHash("sha256");
function fingerprint(directory) {
  for (const entry of fs
    .readdirSync(directory, { withFileTypes: true })
    .sort((a, b) => a.name.localeCompare(b.name))) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) fingerprint(file);
    else {
      hash.update(path.relative(root, file));
      hash.update(fs.readFileSync(file));
    }
  }
}
fingerprint(path.join(root, "src"));
fingerprint(path.join(root, "public/fonts"));
fingerprint(path.join(root, "public/reference"));
hash.update(fs.readFileSync(path.join(root, "package-lock.json")));
const sourceHash = hash.digest("hex").slice(0, 12);
const out = path.join(root, "out");
fs.mkdirSync(out, { recursive: true });
await ensureBrowser();
const serveUrl = await bundle({
  entryPoint: path.join(root, "src/index.ts"),
  publicDir: path.join(root, "public"),
  outDir: path.join(out, ".bundle"),
});
const chromiumOptions = { gl: "swangle" };
let browser = await openBrowser("chrome", { chromiumOptions });
const composition = await selectComposition({
  serveUrl,
  id: "AgentForgeLaunch",
  chromiumOptions,
  puppeteerInstance: browser,
  timeoutInMilliseconds: 90000,
});
if (process.argv.includes("--stills")) {
  const specified = process.argv.find((x) => x.startsWith("--frames="));
  const frames = specified
    ? specified.slice(9).split(",").map(Number)
    : [
        0, 30, 78, 126, 194, 210, 270, 360, 449, 490, 574, 634, 699, 750, 779,
        824, 874, 915, 990, 1060, 1109, 1165, 1240, 1349,
      ];
  fs.mkdirSync(path.join(out, "stills"), { recursive: true });
  for (const frame of frames) {
    await renderStill({
      serveUrl,
      composition,
      frame,
      output: path.join(
        out,
        "stills",
        `frame-${String(frame).padStart(4, "0")}.png`,
      ),
      imageFormat: "png",
      chromiumOptions,
      puppeteerInstance: browser,
      timeoutInMilliseconds: 90000,
    });
    console.log(`Still ${frame}`);
  }
} else {
  await browser.close({ silent: true });
  const directory = path.join(out, ".segments");
  fs.mkdirSync(directory, { recursive: true });
  const files = [];
  for (let start = 0; start < 1350; start += 150) {
    const segment = path.join(
      directory,
      `segment-${sourceHash}-${String(start).padStart(4, "0")}.mp4`,
    );
    files.push(segment);
    if (fs.existsSync(segment) && fs.statSync(segment).size > 10000) {
      const probe = spawnSync(
        path.join(
          root,
          "node_modules/@remotion/compositor-win32-x64-msvc/ffprobe.exe",
        ),
        [
          "-v",
          "error",
          "-select_streams",
          "v:0",
          "-show_entries",
          "stream=nb_frames",
          "-of",
          "json",
          segment,
        ],
        { encoding: "utf8" },
      );
      if (
        probe.status === 0 &&
        JSON.parse(probe.stdout).streams?.[0]?.nb_frames === "150"
      ) {
        console.log(`Resume verified segment ${start}`);
        continue;
      }
    }
    let completed = false;
    for (let attempt = 1; attempt <= 3 && !completed; attempt++) {
      browser = await openBrowser("chrome", { chromiumOptions });
      try {
        await renderMedia({
          serveUrl,
          composition,
          frameRange: [start, start + 149],
          muted: true,
          codec: "h264",
          outputLocation: segment,
          chromiumOptions,
          puppeteerInstance: browser,
          timeoutInMilliseconds: 90000,
          concurrency: 1,
          disableSharedMemoryCapture: true,
          disallowParallelEncoding: true,
          x264Preset: "veryfast",
          crf: 17,
          pixelFormat: "yuv420p",
          jpegQuality: 95,
          imageFormat: "jpeg",
          ffmpegOverride: ({ args }) =>
            args.includes("libx264")
              ? [
                  ...args.slice(0, -1),
                  "-threads",
                  "2",
                  "-x264-params",
                  "threads=2:lookahead_threads=1",
                  args[args.length - 1],
                ]
              : args,
        });
        completed = true;
        console.log(
          `Completed frames ${start}–${start + 149} (${Math.round(((start + 150) / 1350) * 100)}%)`,
        );
      } catch (error) {
        console.log(
          `Segment ${start}, attempt ${attempt}: ${error.message.slice(0, 200)}`,
        );
        if (attempt === 3) throw error;
      } finally {
        await browser.close({ silent: true });
      }
    }
  }
  const ffmpeg = path.join(
    root,
    "node_modules/@remotion/compositor-win32-x64-msvc/ffmpeg.exe",
  );
  const list = path.join(directory, "concat.txt");
  fs.writeFileSync(
    list,
    files.map((file) => `file '${file.replaceAll("\\", "/")}'`).join("\n"),
  );
  const temp = path.join(out, "Project_Launch_Cinematic_finalizing.mp4");
  const mux = spawnSync(
    ffmpeg,
    [
      "-y",
      "-hide_banner",
      "-loglevel",
      "error",
      "-f",
      "concat",
      "-safe",
      "0",
      "-i",
      list,
      "-i",
      path.join(root, "public/audio/master.wav"),
      "-map",
      "0:v:0",
      "-map",
      "1:a:0",
      "-c:v",
      "copy",
      "-c:a",
      "aac",
      "-b:a",
      "320k",
      "-threads",
      "2",
      "-t",
      "45",
      "-movflags",
      "+faststart",
      temp,
    ],
    { encoding: "utf8" },
  );
  if (mux.status !== 0) throw new Error(mux.stderr);
  fs.renameSync(temp, path.join(out, "Project_Launch_Cinematic.mp4"));
  console.log("Rendered out/Project_Launch_Cinematic.mp4");
}
if (process.argv.includes("--stills")) await browser.close({ silent: true });
