#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { Presentation, PresentationFile } = require("@oai/artifact-tool");

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const FIG = path.join(ROOT, "figures");
const AUDIT = path.join(ROOT, "audit");
const RENDER = path.join(AUDIT, "presentation_render");
const LAYOUT = path.join(AUDIT, "presentation_layout");
const OUTPUT = path.join(ROOT, "Kiva_Final_Presentation_2026-09-04.pptx");
const FIGURE_FILES = [
  "fig01_channel_scenarios.png",
  "fig02_specification_forest.png",
  "fig03_year_scenarios.png",
  "fig04_holdout_comparison.png",
  "fig05_holdout_calibration.png",
  "fig06_sample_flow.png",
  "fig07_current_joint_support.png",
  "fig08_sector_calibration_gaps.png",
];
const speakerNoteSources = new WeakMap();

const C = {
  canvas: "#FFFFFF",
  ink: "#000000",
  softInk: "#334155",
  muted: "#64748B",
  panel: "#EDEDED",
  paleBlue: "#D0EDFA",
  rule: "#B8BCC4",
  accent: "#3D8DFF",
  accentLight: "#6DCBF4",
  teal: "#10A7A0",
  gold: "#E5A93D",
  coral: "#F0655B",
};

const FONT = "Helvetica Neue";

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

function addText(slide, text, position, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name: options.name ?? "text",
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: FONT,
    fontSize: options.fontSize ?? 24,
    color: options.color ?? C.ink,
    bold: options.bold ?? false,
    alignment: options.alignment ?? "left",
    verticalAlignment: options.verticalAlignment ?? "top",
    autoFit: options.autoFit ?? "shrinkText",
  };
  return shape;
}

function addRect(slide, position, fill, options = {}) {
  return slide.shapes.add({
    geometry: options.geometry ?? "rect",
    name: options.name ?? "panel",
    position,
    fill,
    line: {
      style: "solid",
      fill: options.lineFill ?? fill,
      width: options.lineWidth ?? 0,
    },
    ...(options.borderRadius ? { borderRadius: options.borderRadius } : {}),
  });
}

function addRule(slide, left, top, width, color = C.rule, height = 2) {
  return addRect(slide, { left, top, width, height }, color, { name: "rule" });
}

function header(slide, title, page, section = "KIVA NARRATIVE ATTENTION") {
  addText(slide, section, { left: 42, top: 28, width: 390, height: 24 }, { fontSize: 13, bold: true, color: C.muted, name: "section-label" });
  addText(slide, title, { left: 42, top: 62, width: 1120, height: 78 }, { fontSize: 39, bold: true, name: "slide-title" });
  addText(slide, String(page).padStart(2, "0"), { left: 1184, top: 28, width: 54, height: 24 }, { fontSize: 13, alignment: "right", color: C.muted, name: "page-number" });
}

function footer(slide, source, page) {
  addRule(slide, 42, 676, 1196, C.rule, 1);
  addText(slide, source, { left: 42, top: 684, width: 1030, height: 20 }, { fontSize: 10.5, color: C.muted, name: "source-footer" });
  addText(slide, `5 GUYS · ${String(page).padStart(2, "0")}`, { left: 1084, top: 684, width: 154, height: 20 }, { fontSize: 10.5, color: C.muted, alignment: "right", name: "team-footer" });
  speakerNoteSources.set(slide, source);
}

function note(slide, text) {
  const source = speakerNoteSources.get(slide);
  const enriched = source ? `${text}\n\n[Sources]\n${source}` : text;
  slide.speakerNotes.textFrame.setText(enriched);
  slide.speakerNotes.setVisible(true);
}

function addImage(slide, imageBytes, position, alt, fit = "contain") {
  const blob = imageBytes.buffer.slice(
    imageBytes.byteOffset,
    imageBytes.byteOffset + imageBytes.byteLength,
  );
  return slide.images.add({ blob, contentType: "image/png", alt, fit, position });
}

function stat(slide, x, y, number, label, color = C.accent, width = 250) {
  addText(slide, number, { left: x, top: y, width, height: 64 }, { fontSize: 48, bold: true, color, name: `stat-${label}` });
  addText(slide, label, { left: x, top: y + 67, width, height: 54 }, { fontSize: 17, color: C.softInk });
}

function bullet(slide, x, y, width, lead, body, color = C.accent) {
  addRect(slide, { left: x, top: y + 7, width: 10, height: 10 }, color, { geometry: "ellipse" });
  addText(slide, lead, { left: x + 24, top: y, width, height: 26 }, { fontSize: 20, bold: true });
  addText(slide, body, { left: x + 24, top: y + 30, width, height: 54 }, { fontSize: 17, color: C.softInk });
}

function buildDeck(figures) {
  const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });

  // Slide 1 — cover (Codex Grid sparse cover silhouette).
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    addText(slide, "UNSW MARKETING ANALYTICS HACKATHON 2026 · FINAL", { left: 42, top: 38, width: 650, height: 28 }, { fontSize: 15, bold: true, color: C.muted, name: "cover-eyebrow" });
    addText(slide, "When Every Story\nSounds the Same", { left: 42, top: 154, width: 770, height: 220 }, { fontSize: 76, bold: true, verticalAlignment: "bottom", name: "cover-title" });
    addText(slide, "The attention bottleneck is what is live beside it.", { left: 42, top: 410, width: 690, height: 52 }, { fontSize: 28, color: C.softInk, name: "cover-subtitle" });
    addText(slide, "Ruiyang Zheng · Ruohan Wang · Hongxin Luo · Yiou Liu · Jingzhi Hu", { left: 42, top: 612, width: 750, height: 30 }, { fontSize: 15, color: C.muted, name: "team-names" });
    for (let i = 0; i < 11; i += 1) {
      const height = 80 + i * 22;
      addRect(slide, { left: 895 + i * 23, top: 620 - height, width: 11, height }, i < 7 ? C.paleBlue : C.accent, { name: `market-bar-${i}` });
    }
    addText(slide, "LIVE MARKET", { left: 895, top: 640, width: 245, height: 24 }, { fontSize: 13, bold: true, color: C.muted, alignment: "right" });
    note(slide, "Good morning. Kiva borrowers are often encouraged to tell a more distinctive story. But a story is never seen in isolation. It appears beside other live requests, often using similar recurring language. Our question is: when every story sounds the same, is the bottleneck competition right now, repetition from the recent past, or both? Our answer is more selective—and more useful—than we expected. The most reliable signal is what is live beside a story when that story enters the market.");
  }

  // Slide 2 — mechanism split.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    header(slide, "Two candidate channels imply two different tests", 2);
    addRule(slide, 640, 166, 1, C.rule, 444);
    addText(slide, "CURRENT", { left: 42, top: 170, width: 250, height: 26 }, { fontSize: 16, bold: true, color: C.accent });
    addText(slide, "Many live alternatives\n+ similar stories", { left: 42, top: 210, width: 470, height: 110 }, { fontSize: 34, bold: true });
    addText(slide, "Active saturation asks what a lender could choose at the focal loan’s posting moment.", { left: 42, top: 338, width: 500, height: 76 }, { fontSize: 19, color: C.softInk });
    addRect(slide, { left: 42, top: 458, width: 516, height: 118 }, C.paleBlue, { name: "current-action" });
    addText(slide, "TEST", { left: 66, top: 479, width: 90, height: 25 }, { fontSize: 15, bold: true, color: C.accent });
    addText(slide, "Listing cadence + exposure mix", { left: 66, top: 513, width: 440, height: 36 }, { fontSize: 25, bold: true });

    addText(slide, "RECENT-LISTING PROXY", { left: 688, top: 170, width: 300, height: 26 }, { fontSize: 16, bold: true, color: C.gold });
    addText(slide, "Similar same-sector posts\n35–65 days earlier", { left: 688, top: 210, width: 470, height: 110 }, { fontSize: 34, bold: true });
    addText(slide, "A posting-age lexical proxy tests wear-out without observing exposure, page exit or memory.", { left: 688, top: 338, width: 500, height: 76 }, { fontSize: 19, color: C.softInk });
    addRect(slide, { left: 688, top: 458, width: 516, height: 118 }, "#F8EED8", { name: "recent-action" });
    addText(slide, "TEST", { left: 712, top: 479, width: 90, height: 25 }, { fontSize: 15, bold: true, color: C.gold });
    addText(slide, "Editorial refresh + templates", { left: 712, top: 513, width: 440, height: 36 }, { fontSize: 25, bold: true });
    footer(slide, "Research design from the finalist proposal; definitions frozen before outcome modelling.", 2);
    note(slide, "We separate two candidate channels that can both look like slower funding. Active saturation means many live alternatives with strong focal-to-pool lexical overlap. The recent measure captures similar same-sector language posted 35 to 65 days earlier. It tests a wear-out hypothesis, but it does not observe exposure, page exit or lender memory. The distinction changes what to test: current competition points to timing and exposure; a validated wear-out mechanism would point to editorial refresh.");
  }

  // Slide 3 — sample and design.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    header(slide, "1.23 million training loans reconstruct each listing’s market at posting", 3);
    addText(slide, "2016", { left: 58, top: 182, width: 70, height: 28 }, { fontSize: 18, bold: true });
    addText(slide, "2024", { left: 780, top: 182, width: 70, height: 28 }, { fontSize: 18, bold: true, alignment: "right" });
    addRule(slide, 92, 224, 700, C.ink, 3);
    for (let i = 0; i < 9; i += 1) addRect(slide, { left: 90 + i * 87.5, top: 216, width: 16, height: 16 }, C.accent, { geometry: "ellipse" });
    addText(slide, "FIT", { left: 92, top: 254, width: 110, height: 26 }, { fontSize: 14, bold: true, color: C.accent });
    addText(slide, "Text IDF · scalers · HDFE", { left: 92, top: 280, width: 530, height: 36 }, { fontSize: 24, bold: true });

    addRect(slide, { left: 858, top: 170, width: 346, height: 170 }, C.panel, { name: "holdout-panel" });
    addText(slide, "2025 HOLDOUT", { left: 884, top: 194, width: 294, height: 25 }, { fontSize: 15, bold: true, color: C.teal });
    addText(slide, "133,409", { left: 884, top: 228, width: 294, height: 54 }, { fontSize: 43, bold: true, color: C.teal });
    addText(slide, "No refit · out-of-time evaluation", { left: 884, top: 286, width: 294, height: 30 }, { fontSize: 17, color: C.softInk });

    stat(slide, 42, 398, "1,234,131", "Main training loans", C.accent, 290);
    stat(slide, 356, 398, "600", "Exact pool identity checks", C.ink, 260);
    stat(slide, 650, 398, "2 outcomes", "Funding time + 72 hours", C.ink, 250);
    stat(slide, 936, 398, "UTC", "One frozen time basis", C.ink, 220);
    addText(slide, "Country + activity + week fixed effects · country/week two-way clustered standard errors", { left: 42, top: 584, width: 1080, height: 34 }, { fontSize: 18, color: C.softInk });
    footer(slide, "Sources: outputs/model_sample_flow.csv; outputs/frozen_spec.csv; outputs/pool_identity_summary.csv", 3);
    note(slide, "Our main training analysis contains 1,234,131 loans. For each focal listing, current volume is how many alternatives are available and current overlap is the focal story's mean lexical similarity to that active pool. We build a separate posting-age proxy from listings 35 to 65 days earlier. We compare masked and recurring-language-removed text, test time-based windows, and evaluate log one plus funding hours plus 72-hour funding. Every valid record has a raised date, so the analysis is conditional on this raised-only extract. The 2025 holdout is never used to refit preprocessing or the model.");
  }

  // Slide 4 — hero evidence image.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    addImage(slide, figures["fig01_channel_scenarios.png"], { left: 18, top: 24, width: 1244, height: 534 }, "Current and recent scenario estimates with confidence intervals");
    addRect(slide, { left: 42, top: 584, width: 1196, height: 62 }, C.panel, { name: "association-warning" });
    addText(slide, "ASSOCIATION · NOT AN INTERVENTION FORECAST", { left: 66, top: 604, width: 650, height: 24 }, { fontSize: 16, bold: true, color: C.coral });
    addText(slide, "Both scenario endpoints are populated in observed training support.", { left: 716, top: 604, width: 490, height: 24 }, { fontSize: 16, alignment: "right", color: C.softInk });
    footer(slide, "Source: outputs/scenario_contrasts.csv; outputs/joint_support_summary.csv", 4);
    note(slide, "This is our strongest diagnostic result. On the log one plus hours outcome, moving the current environment jointly from the 25th to the 75th percentile corresponds to a 124.38 percent higher conditional geometric mean of one plus funding hours, with an interval from 103.74 to 147.11 percent and a ratio of 2.24. This is not an arithmetic mean duration. The independent 72-hour co-outcome is 14.68 percentage points lower, with an interval from minus 17.69 to minus 11.68. Both endpoints are populated, but these remain associations, not intervention forecasts.");
  }

  // Slide 5 — text representation.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    header(slide, "The current signal depends partly on how text is represented", 5);
    addText(slide, "CURRENT INTERACTION", { left: 42, top: 170, width: 390, height: 24 }, { fontSize: 14, bold: true, color: C.muted });
    addText(slide, "Masked use", { left: 42, top: 222, width: 220, height: 30 }, { fontSize: 20, bold: true });
    addRect(slide, { left: 262, top: 220, width: 396, height: 34 }, C.panel, { name: "raw-track" });
    addRect(slide, { left: 262, top: 220, width: 322, height: 34 }, C.accent, { name: "raw-bar" });
    addText(slide, ".1016", { left: 596, top: 218, width: 100, height: 34 }, { fontSize: 24, bold: true, color: C.accent });
    addText(slide, "p = .0033", { left: 706, top: 224, width: 120, height: 24 }, { fontSize: 16, color: C.softInk });

    addText(slide, "Recurring language removed", { left: 42, top: 308, width: 220, height: 56 }, { fontSize: 20, bold: true });
    addRect(slide, { left: 262, top: 318, width: 396, height: 34 }, C.panel, { name: "residual-track" });
    addRect(slide, { left: 262, top: 318, width: 166, height: 34 }, C.accentLight, { name: "residual-bar" });
    addText(slide, ".0523", { left: 442, top: 316, width: 100, height: 34 }, { fontSize: 24, bold: true, color: C.accent });
    addText(slide, "p = .129", { left: 552, top: 322, width: 120, height: 24 }, { fontSize: 16, color: C.softInk });

    addText(slide, "Masked description", { left: 42, top: 416, width: 220, height: 30 }, { fontSize: 20, bold: true });
    addRect(slide, { left: 262, top: 414, width: 396, height: 34 }, C.panel, { name: "description-track" });
    addRect(slide, { left: 262, top: 414, width: 396, height: 34 }, C.teal, { name: "description-bar" });
    addText(slide, ".1323", { left: 672, top: 412, width: 100, height: 34 }, { fontSize: 24, bold: true, color: C.teal });
    addText(slide, "p < .001", { left: 782, top: 418, width: 120, height: 24 }, { fontSize: 16, color: C.softInk });

    addRule(slide, 922, 180, 1, C.rule, 368);
    addText(slide, "What this means", { left: 966, top: 190, width: 250, height: 32 }, { fontSize: 25, bold: true });
    bullet(slide, 966, 252, 226, "Signal attenuates", "Recurring language may contribute to the masked-use association.", C.accent);
    bullet(slide, 966, 366, 226, "Not a decomposition", "The coefficient difference itself was not formally tested.", C.coral);
    bullet(slide, 966, 480, 226, "Shift the burden", "Test platform and partner processes—not louder borrower stories.", C.teal);
    footer(slide, "Sources: outputs/robustness.csv; outputs/description_robustness.csv", 5);
    note(slide, "Using masked use text, the current interaction is 0.1016 with p 0.0033. After removing recurring language, it falls to 0.0523 with p 0.129. The estimate roughly halves and is no longer distinguishable from zero. That does not prove templates explain half because the coefficient difference itself was not formally tested. Description text gives a significant current interaction of 0.1323, while its recent interaction is not significant. Together, this shifts the managerial focus from borrower rewriting toward platform and partner processes.");
  }

  // Slide 6 — recent null.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    header(slide, "The recent-listing proxy shows no detectable joint penalty", 6);
    addText(slide, "LOG-TIME BACK-TRANSFORM", { left: 42, top: 188, width: 300, height: 24 }, { fontSize: 14, bold: true, color: C.muted });
    addText(slide, "−1.43%", { left: 42, top: 226, width: 330, height: 90 }, { fontSize: 68, bold: true, color: C.gold });
    addText(slide, "95% CI  −15.82%  to  +15.43%", { left: 42, top: 322, width: 430, height: 34 }, { fontSize: 20, color: C.softInk });
    addRule(slide, 42, 396, 526, C.rule, 3);
    addRule(slide, 290, 380, 3, C.ink, 36);
    addRect(slide, { left: 166, top: 388, width: 250, height: 18 }, C.gold, { name: "recent-ci-time" });
    addRect(slide, { left: 282, top: 382, width: 16, height: 30 }, C.gold, { geometry: "ellipse", name: "recent-point-time" });
    addText(slide, "0", { left: 278, top: 420, width: 28, height: 22 }, { fontSize: 14, alignment: "center", color: C.muted });

    addText(slide, "72-HOUR PROBABILITY", { left: 682, top: 188, width: 320, height: 24 }, { fontSize: 14, bold: true, color: C.muted });
    addText(slide, "−0.51pp", { left: 682, top: 226, width: 380, height: 90 }, { fontSize: 68, bold: true, color: C.gold });
    addText(slide, "95% CI  −3.86pp  to  +2.84pp", { left: 682, top: 322, width: 450, height: 34 }, { fontSize: 20, color: C.softInk });
    addRule(slide, 682, 396, 526, C.rule, 3);
    addRule(slide, 930, 380, 3, C.ink, 36);
    addRect(slide, { left: 804, top: 388, width: 247, height: 18 }, C.gold, { name: "recent-ci-72" });
    addRect(slide, { left: 912, top: 382, width: 16, height: 30 }, C.gold, { geometry: "ellipse", name: "recent-point-72" });
    addText(slide, "0", { left: 918, top: 420, width: 28, height: 22 }, { fontSize: 14, alignment: "center", color: C.muted });

    addRect(slide, { left: 42, top: 502, width: 1166, height: 98 }, C.panel, { name: "recent-conclusion" });
    addText(slide, "Intervals cross zero", { left: 68, top: 526, width: 310, height: 32 }, { fontSize: 27, bold: true });
    addText(slide, "A posting-age proxy does not support broad average wear-out—not that wear-out is impossible.", { left: 402, top: 523, width: 770, height: 50 }, { fontSize: 21, color: C.softInk });
    footer(slide, "Source: outputs/scenario_contrasts.csv", 6);
    note(slide, "The recent-listing proxy tells a different story. Its representative P25-to-P75 log-time back-transform is minus 1.43 percent, with a 95 percent interval from minus 15.82 to plus 15.43. The 72-hour contrast is minus 0.51 percentage points, with an interval from minus 3.86 to plus 2.84. Both cross zero. Because the main measure is a posting-age lexical proxy rather than observed exposure, we do not find support for an average wear-out claim. That is not the same as proving wear-out can never occur.");
  }

  // Slide 7 — robustness forest.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    addImage(slide, figures["fig02_specification_forest.png"], { left: 24, top: 20, width: 1232, height: 607 }, "Specification forest plot for current and recent interactions");
    addText(slide, "Current survives 14/16-day windows and description. Recent does not survive the time-based or description checks.", { left: 60, top: 626, width: 1130, height: 38 }, { fontSize: 19, bold: true, alignment: "center" });
    footer(slide, "Sources: outputs/robustness.csv; outputs/description_robustness.csv", 7);
    note(slide, "There is an important nuance. The raw recent-listing interaction is statistically positive, but it answers a local conditional question. The joint scenario asks about the net log-time contrast when recent volume and overlap move together. The current interaction remains positive in both 14-day and 16-day posting-window checks and appears again with description text, but it attenuates and crosses zero after recurring-language removal. The recent-listing interaction does not survive the time-based checks or description sensitivity. The honest conclusion is a strong but representation-sensitive current diagnostic association, not a broad wear-out claim.");
  }

  // Slide 8 — holdout.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    addImage(slide, figures["fig04_holdout_comparison.png"], { left: 64, top: 26, width: 1152, height: 650 }, "Relative holdout deterioration after adding narrative features");
    footer(slide, "Source: outputs/holdout_validation.csv · Differences are descriptive; paired uncertainty not estimated.", 8);
    note(slide, "A variable can explain a historical association without improving future prediction. On the 2025 holdout, the narrative-enhanced model does not outperform controls-only on the main operational metrics. Log-hour MAE is 0.9822 versus 0.9663; Brier is 0.1369 versus 0.1354; AUC is 0.8921 versus 0.8987. Log-loss improves slightly. Because we have not estimated paired uncertainty for these metric differences, we say did not outperform, not significantly worsened. These results do not support deploying a scoring engine.");
  }

  // Slide 9 — experiments.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    header(slide, "The evidence supports experiments on the market—not borrower scoring", 9);
    addText(slide, "PILOT A", { left: 42, top: 170, width: 180, height: 24 }, { fontSize: 14, bold: true, color: C.accent });
    addText(slide, "Stagger or diversify\nlive exposure", { left: 42, top: 207, width: 420, height: 88 }, { fontSize: 34, bold: true });
    addText(slide, "Randomize inside pre-defined high-current-saturation states.", { left: 42, top: 310, width: 435, height: 56 }, { fontSize: 19, color: C.softInk });
    addRule(slide, 42, 400, 438, C.accent, 6);
    addText(slide, "Business as usual", { left: 42, top: 422, width: 180, height: 26 }, { fontSize: 16, bold: true });
    addText(slide, "→", { left: 232, top: 411, width: 54, height: 38 }, { fontSize: 32, bold: true, alignment: "center", color: C.accent });
    addText(slide, "Staggered / diversified", { left: 296, top: 422, width: 220, height: 26 }, { fontSize: 16, bold: true });

    addRule(slide, 640, 166, 1, C.rule, 386);
    addText(slide, "PILOT B", { left: 688, top: 170, width: 180, height: 24 }, { fontSize: 14, bold: true, color: C.teal });
    addText(slide, "Test partner-approved\ntemplate alternatives", { left: 688, top: 207, width: 500, height: 88 }, { fontSize: 34, bold: true });
    addText(slide, "Do not ask borrowers for more sensitive or more burdensome storytelling.", { left: 688, top: 310, width: 500, height: 56 }, { fontSize: 19, color: C.softInk });
    addRule(slide, 688, 400, 500, C.teal, 6);
    addText(slide, "Current template", { left: 688, top: 422, width: 160, height: 26 }, { fontSize: 16, bold: true });
    addText(slide, "→", { left: 858, top: 411, width: 54, height: 38 }, { fontSize: 32, bold: true, alignment: "center", color: C.teal });
    addText(slide, "Approved variants", { left: 922, top: 422, width: 220, height: 26 }, { fontSize: 16, bold: true });

    addRect(slide, { left: 42, top: 510, width: 1166, height: 112 }, C.panel, { name: "guardrail-strip" });
    addText(slide, "PRIMARY", { left: 66, top: 532, width: 100, height: 22 }, { fontSize: 13, bold: true, color: C.muted });
    addText(slide, "Funding time · 72-hour probability", { left: 66, top: 560, width: 365, height: 30 }, { fontSize: 20, bold: true });
    addText(slide, "GUARDRAILS", { left: 486, top: 532, width: 120, height: 22 }, { fontSize: 13, bold: true, color: C.muted });
    addText(slide, "Total funding · fairness · borrower workload", { left: 486, top: 560, width: 540, height: 30 }, { fontSize: 20, bold: true });
    addText(slide, "NO SCORE", { left: 1060, top: 540, width: 122, height: 38 }, { fontSize: 22, bold: true, color: C.coral, alignment: "right" });
    footer(slide, "Recommendation derived from scenario, robustness and 2025 holdout evidence.", 9);
    note(slide, "Our recommendation is deliberately narrower. When current saturation is high, test whether staggering similar listings or diversifying exposure improves funding. Separately, test partner-approved template alternatives without adding borrower burden. These should be small randomized pilots. Primary outcomes are time to funding and 72-hour probability; guardrails include total funding, fairness and borrower workload. Saturation identifies a market condition worth testing. It does not measure borrower quality and must not rank or penalize borrowers.");
  }

  // Slide 10 — close.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    addText(slide, "WHAT WE LEARNED", { left: 42, top: 42, width: 320, height: 28 }, { fontSize: 15, bold: true, color: C.muted });
    addText(slide, "Change the market\naround the story.", { left: 42, top: 126, width: 810, height: 188 }, { fontSize: 70, bold: true });
    addRule(slide, 42, 358, 1196, C.ink, 2);
    addText(slide, "01", { left: 42, top: 398, width: 60, height: 42 }, { fontSize: 25, bold: true, color: C.accent });
    addText(slide, "Current attention pressure is the strongest practical signal.", { left: 112, top: 394, width: 1040, height: 48 }, { fontSize: 25, bold: true });
    addText(slide, "02", { left: 42, top: 480, width: 60, height: 42 }, { fontSize: 25, bold: true, color: C.gold });
    addText(slide, "The recent-listing proxy does not support broad wear-out.", { left: 112, top: 476, width: 1040, height: 48 }, { fontSize: 25, bold: true });
    addText(slide, "03", { left: 42, top: 562, width: 60, height: 42 }, { fontSize: 25, bold: true, color: C.teal });
    addText(slide, "Test prospectively; do not deploy a borrower score.", { left: 112, top: 558, width: 1040, height: 48 }, { fontSize: 25, bold: true });
    addText(slide, "5 GUYS · UNSW 2026", { left: 42, top: 660, width: 300, height: 24 }, { fontSize: 13, bold: true, color: C.muted });
    speakerNoteSources.set(slide, "Sources: outputs/scenario_contrasts.csv; outputs/robustness.csv; outputs/holdout_validation.csv");
    note(slide, "Our analysis leaves three conclusions. First, the strongest diagnostic signal is current attention pressure, although it is sensitive to text representation. Second, the recent-listing proxy does not support broad wear-out. Third, narrative features do not add reliable 2025 predictive value on the main operational metrics. Our model is not ready to score borrowers—and that is exactly why our recommendation is safer: change the market around the story, test it prospectively, and scale only what improves funding without shifting the burden onto borrowers.");
  }

  // Slide 11 — appendix sample flow.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    addText(slide, "APPENDIX · DATA", { left: 42, top: 24, width: 280, height: 24 }, { fontSize: 13, bold: true, color: C.muted });
    addImage(slide, figures["fig06_sample_flow.png"], { left: 42, top: 48, width: 820, height: 500 }, "Sample flow from valid duration through train and holdout");
    addRule(slide, 892, 72, 1, C.rule, 486);
    bullet(slide, 930, 100, 250, "Raised-only extract", "Every valid row has a raised date; no observable right censoring.", C.coral);
    bullet(slide, 930, 226, 250, "Six invalid durations", "Raised timestamp precedes posting; excluded from outcome analysis.", C.coral);
    bullet(slide, 930, 352, 250, "Frozen split", "2016–24 fit; 2025 remains out of time.", C.teal);
    bullet(slide, 930, 478, 250, "No private text", "Names, exact locations and full descriptions stay outside the final ZIP.", C.teal);
    footer(slide, "Sources: outputs/model_sample_flow.csv; outputs/data_profile_summary.csv; outputs/status_raised_crosstab.csv", 11);
    note(slide, "Appendix: the source has 1,453,846 loans; six invalid negative-duration rows are excluded. Every valid row has raisedDate, so a true right-censored AFT model is not supported by this extract. The final package omits raw personal text and exact locations.");
  }

  // Slide 12 — pool/support audit.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    addText(slide, "APPENDIX · VALIDATION", { left: 42, top: 24, width: 320, height: 24 }, { fontSize: 13, bold: true, color: C.muted });
    addImage(slide, figures["fig07_current_joint_support.png"], { left: 26, top: 48, width: 940, height: 495 }, "Current volume and focal-to-pool lexical-overlap quartile support heatmaps");
    addRect(slide, { left: 984, top: 88, width: 254, height: 150 }, C.panel, { name: "identity-stat" });
    addText(slide, "600", { left: 1008, top: 112, width: 210, height: 58 }, { fontSize: 48, bold: true, color: C.accent });
    addText(slide, "raw + residual\nidentity checks", { left: 1008, top: 176, width: 210, height: 48 }, { fontSize: 17, color: C.softInk });
    addRect(slide, { left: 984, top: 266, width: 254, height: 150 }, C.panel, { name: "error-stat" });
    addText(slide, "2.89e−14", { left: 1008, top: 290, width: 210, height: 58 }, { fontSize: 38, bold: true, color: C.teal });
    addText(slide, "maximum raw\nabsolute error", { left: 1008, top: 354, width: 210, height: 48 }, { fontSize: 17, color: C.softInk });
    addText(slide, "PASS · threshold 1e−9", { left: 1000, top: 460, width: 222, height: 30 }, { fontSize: 20, bold: true, color: C.teal, alignment: "center" });
    addText(slide, "Support is descriptive—it does not establish causality.", { left: 1000, top: 512, width: 222, height: 46 }, { fontSize: 16, color: C.softInk, alignment: "center" });
    footer(slide, "Sources: outputs/pool_identity_summary.csv; outputs/joint_support_summary.csv", 12);
    note(slide, "Appendix: the rolling vector-sum implementation is verified against exact brute-force similarity for 200 focal loans across three pools, 600 checks total. Maximum raw error is 2.89e-14, well inside the 1e-9 gate. The P25/P75 endpoints have populated local support, but support does not establish causality.");
  }

  // Slide 13 — model specification.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    header(slide, "The model separates current and recent environments within a fixed specification", 13, "APPENDIX · MODEL");
    addRect(slide, { left: 42, top: 170, width: 1196, height: 98 }, C.panel, { name: "formula-band" });
    addText(slide, "log(1 + funding hours)  ~  C + H + C×H + V + G + V×G + controls  |  fixed effects", { left: 68, top: 199, width: 1144, height: 42 }, { fontSize: 25, bold: true, alignment: "center" });

    addText(slide, "CURRENT", { left: 42, top: 320, width: 180, height: 24 }, { fontSize: 14, bold: true, color: C.accent });
    addText(slide, "C", { left: 42, top: 358, width: 64, height: 48 }, { fontSize: 36, bold: true, color: C.accent });
    addText(slide, "log1p active same-sector count", { left: 106, top: 367, width: 300, height: 30 }, { fontSize: 19 });
    addText(slide, "H", { left: 42, top: 424, width: 64, height: 48 }, { fontSize: 36, bold: true, color: C.accent });
    addText(slide, "focal-to-active-pool lexical overlap", { left: 106, top: 433, width: 300, height: 30 }, { fontSize: 19 });
    addText(slide, "C×H", { left: 42, top: 490, width: 84, height: 48 }, { fontSize: 36, bold: true, color: C.accent });
    addText(slide, "current saturation interaction", { left: 126, top: 499, width: 280, height: 30 }, { fontSize: 19 });

    addText(slide, "RECENT", { left: 454, top: 320, width: 180, height: 24 }, { fontSize: 14, bold: true, color: C.gold });
    addText(slide, "V", { left: 454, top: 358, width: 64, height: 48 }, { fontSize: 36, bold: true, color: C.gold });
    addText(slide, "log1p [35,65)d decayed posting weight", { left: 518, top: 367, width: 320, height: 30 }, { fontSize: 18 });
    addText(slide, "G", { left: 454, top: 424, width: 64, height: 48 }, { fontSize: 36, bold: true, color: C.gold });
    addText(slide, "decayed focal-to-pool lexical overlap", { left: 518, top: 433, width: 320, height: 30 }, { fontSize: 18 });
    addText(slide, "V×G", { left: 454, top: 490, width: 84, height: 48 }, { fontSize: 36, bold: true, color: C.gold });
    addText(slide, "recent saturation interaction", { left: 538, top: 499, width: 280, height: 30 }, { fontSize: 19 });

    addRule(slide, 862, 316, 1, C.rule, 250);
    addText(slide, "CONTROLS + FE", { left: 906, top: 320, width: 260, height: 24 }, { fontSize: 14, bold: true, color: C.muted });
    addText(slide, "Loan amount\nBorrower count\nRepayment term\nPlatform 7-day volume", { left: 906, top: 360, width: 280, height: 140 }, { fontSize: 20, color: C.softInk });
    addText(slide, "Country · activity · week", { left: 906, top: 510, width: 290, height: 64 }, { fontSize: 18, bold: true });
    footer(slide, "Source: src/fit_main_models.py; outputs/frozen_spec.csv", 13);
    note(slide, "Appendix: this is the main HDFE specification. C is log one plus active count and H is focal-to-active-pool lexical overlap. V is log one plus decayed posting weight for listings 35 to 65 days earlier and G is the corresponding lexical overlap. The recent pair is a posting-age proxy, not observed exposure or page exit. All components are standardized from 2016 to 2024 before interactions are created. Fixed effects and controls reduce confounding but do not create causal identification.");
  }

  // Slide 14 — temporal heterogeneity.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    addImage(slide, figures["fig03_year_scenarios.png"], { left: 26, top: 22, width: 1228, height: 597 }, "Year-specific scenario associations with confidence bands");
    addRect(slide, { left: 156, top: 606, width: 968, height: 46 }, C.panel, { name: "hetero-boundary" });
    addText(slide, "DESCRIPTIVE HETEROGENEITY · NOT A TARGETING RULE", { left: 180, top: 618, width: 920, height: 24 }, { fontSize: 16, bold: true, alignment: "center", color: C.coral });
    footer(slide, "Source: outputs/rq3_year_effects.csv; outputs/rq3_global_tests.csv", 14);
    note(slide, "Appendix: year-specific scenario associations vary materially. We do not convert this volatility into a year or subgroup ranking. The global heterogeneity screens are descriptive and do not estimate every cross-group covariance induced by shared week shocks.");
  }

  // Slide 15 — calibration and fairness.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    addText(slide, "APPENDIX · DEPLOYMENT BOUNDARY", { left: 42, top: 24, width: 360, height: 24 }, { fontSize: 13, bold: true, color: C.muted });
    addImage(slide, figures["fig05_holdout_calibration.png"], { left: 42, top: 64, width: 492, height: 500 }, "Controls and narrative 2025 calibration curves");
    addImage(slide, figures["fig08_sector_calibration_gaps.png"], { left: 554, top: 64, width: 684, height: 500 }, "Sector-level 2025 calibration gaps");
    addRect(slide, { left: 42, top: 580, width: 1196, height: 72 }, C.panel, { name: "calibration-close" });
    addText(slide, "Imperfect calibration + no consistent incremental lift = experiment triage only", { left: 70, top: 600, width: 1140, height: 34 }, { fontSize: 24, bold: true, alignment: "center" });
    footer(slide, "Sources: outputs/holdout_calibration.csv; outputs/fairness_diagnostics.csv", 15);
    note(slide, "Appendix: 2025 calibration remains imperfect, with material gaps in several sectors. These diagnostics reinforce the no-deployment boundary. We do not use group membership for targeting; fairness diagnostics are guardrails for future prospective experiments.");
  }

  // Slide 16 — evidence gates.
  {
    const slide = presentation.slides.add();
    slide.background.fill = C.canvas;
    header(slide, "Every headline claim has an explicit evidence gate", 16, "APPENDIX · AUDIT");
    const rows = [
      ["Source intake", "Restricted opcode audit", "PASS", "0 dangerous opcodes"],
      ["Text leakage", "Train-only IDF + scaler", "PASS", "2016–24 fit; fixed on 2025"],
      ["Pool algebra", "Brute-force identity", "PASS", "max 2.89e−14"],
      ["Scenario support", "Endpoint neighbourhood", "PASS", "minimum 4,716 loans"],
      ["Current signal", "14/16d + description + residual", "CAVEAT", "positive except residual CI crosses 0"],
      ["Recent claim", "Joint + time checks", "NO CLAIM", "intervals cross zero"],
      ["Deployment", "2025 incremental lift", "NO DEPLOY", "MAE/Brier/AUC do not win"],
    ];
    const y0 = 178;
    const heights = 60;
    const xs = [42, 270, 620, 782];
    const widths = [228, 350, 162, 456];
    ["STAGE", "GATE", "STATUS", "EVIDENCE"].forEach((t, i) => addText(slide, t, { left: xs[i], top: 150, width: widths[i], height: 22 }, { fontSize: 13, bold: true, color: C.muted }));
    rows.forEach((r, idx) => {
      const y = y0 + idx * heights;
      if (idx % 2 === 0) addRect(slide, { left: 42, top: y - 6, width: 1196, height: 52 }, C.panel, { name: `audit-row-${idx}` });
      addText(slide, r[0], { left: xs[0] + 12, top: y + 4, width: widths[0] - 24, height: 26 }, { fontSize: 17, bold: true });
      addText(slide, r[1], { left: xs[1] + 12, top: y + 4, width: widths[1] - 24, height: 26 }, { fontSize: 17 });
      addText(slide, r[2], { left: xs[2] + 12, top: y + 4, width: widths[2] - 24, height: 26 }, { fontSize: 16, bold: true, color: r[2] === "PASS" ? C.teal : (r[2] === "CAVEAT" ? C.gold : C.coral) });
      addText(slide, r[3], { left: xs[3] + 12, top: y + 4, width: widths[3] - 24, height: 26 }, { fontSize: 17, color: C.softInk });
    });
    addText(slide, "Full bilingual judge Q&A: JUDGE_QA_BILINGUAL.md", { left: 42, top: 624, width: 670, height: 26 }, { fontSize: 18, bold: true });
    addText(slide, "All exact tables: outputs/ · Reproducible notebooks: notebooks/", { left: 720, top: 624, width: 518, height: 26 }, { fontSize: 16, alignment: "right", color: C.softInk });
    footer(slide, "Sources: audit/ manifests; outputs/ validated CSV tables", 16);
    note(slide, "Appendix: this summarizes the gates behind the claims. Passing a computation gate does not broaden the claim boundary. The current association is supported by active, posting-window and description specifications but is sensitive to recurring-language removal. Broad wear-out and deployment remain explicitly unsupported.");
  }

  return presentation;
}

async function main() {
  await fs.mkdir(RENDER, { recursive: true });
  await fs.mkdir(LAYOUT, { recursive: true });
  const figures = Object.fromEntries(
    await Promise.all(
      FIGURE_FILES.map(async (filename) => [filename, await fs.readFile(path.join(FIG, filename))]),
    ),
  );
  const presentation = buildDeck(figures);

  for (const [index, slide] of presentation.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    const png = await presentation.export({ slide, format: "png", scale: 1.25 });
    await writeBlob(path.join(RENDER, `${stem}.png`), png);
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(LAYOUT, `${stem}.layout.json`), await layout.text());
  }

  const montage = await presentation.export({ format: "webp", montage: true, scale: 0.65 });
  await writeBlob(path.join(AUDIT, "presentation_montage.webp"), montage);
  const inspect = await presentation.inspect({ kind: "slide,textbox,shape,image,chart,notes,layout", maxChars: 100000 });
  await fs.writeFile(path.join(AUDIT, "presentation_inspect.ndjson"), inspect.ndjson, "utf8");

  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(OUTPUT);

  const figureHashes = {};
  for (const filename of FIGURE_FILES) {
    figureHashes[filename] = crypto.createHash("sha256").update(figures[filename]).digest("hex");
  }
  await fs.writeFile(
    path.join(AUDIT, "presentation_build_manifest.json"),
    JSON.stringify(
      {
        slide_count: presentation.slides.items.length,
        core_slides: 10,
        appendix_slides: 6,
        slide_size_px: [1280, 720],
        design_system: "Codex Grid",
        output: path.basename(OUTPUT),
        figure_sha256: figureHashes,
        speaker_notes_embedded: true,
      },
      null,
      2,
    ),
    "utf8",
  );
  console.log(`Wrote ${OUTPUT} with ${presentation.slides.items.length} slides.`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
