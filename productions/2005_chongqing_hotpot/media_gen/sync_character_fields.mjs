import fs from "node:fs/promises";
import path from "node:path";
import { Store } from "/home/zhongwenyu/project/playlets-studio/lib/store.mjs";

// Load DATABASE_URL from playlets-studio/.env without printing it
const envPath = "/home/zhongwenyu/project/playlets-studio/.env";
const envLines = (await fs.readFile(envPath, "utf8")).split(/\r?\n/);
let dbUrl = process.env.DATABASE_URL || "";
for (const line of envLines) {
  const m = line.match(/^\s*DATABASE_URL\s*=\s*(.+)\s*$/);
  if (m) {
    dbUrl = m[1].replace(/^['"]|['"]$/g, "");
    break;
  }
}
if (!dbUrl) throw new Error("Missing DATABASE_URL");

const payloadPath = process.argv[2];
const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
const store = new Store(dbUrl, "/home/zhongwenyu/project/playlets-studio/playlets");

try {
  // IMPORTANT: Do NOT call store.init() per AGENTS.md §3! Use store.mutate() directly.
  await store.mutate(payload.projectId, (p) => {
    if (payload.stylePrompt) p.stylePrompt = payload.stylePrompt;

    // Update media metadata (type: 'character-sheet' / 'character-view') cleanly if provided
    const mediaMeta = payload.mediaUpdates || {};
    for (const m of p.media) {
      if (mediaMeta[m.id]) {
        Object.assign(m, mediaMeta[m.id]);
      }
    }

    // Optional cleanup of failed voice-source test media
    if (Array.isArray(payload.removeMediaIds) && payload.removeMediaIds.length) {
      const rm = new Set(payload.removeMediaIds);
      p.media = p.media.filter((m) => !rm.has(m.id));
    }

    // Update character/scene/prop asset bindings
    for (const upd of payload.assetUpdates || []) {
      const a = p.assets.find((x) => x.id === upd.assetId);
      if (!a) continue;
      if (upd.description) a.description = upd.description;
      if (upd.prompt) a.prompt = upd.prompt;
      if (upd.imageId) a.imageId = upd.imageId;
      if (upd.sheetImageId) a.sheetImageId = upd.sheetImageId;
      if (upd.frontImageId) a.frontImageId = upd.frontImageId;
      if (upd.viewIds) a.viewIds = upd.viewIds;
      if (upd.globalCharacterKey) a.globalCharacterKey = upd.globalCharacterKey;
      if (upd.globalCostumeKey) a.globalCostumeKey = upd.globalCostumeKey;
      if (upd.voiceSampleId) a.voiceSampleId = upd.voiceSampleId;
      if (upd.voiceDuration) a.voiceDuration = upd.voiceDuration;
      if (upd.voiceProvider) a.voiceProvider = upd.voiceProvider;
      if (upd.voiceReview) a.voiceReview = upd.voiceReview;
      if (upd.globalVoiceId) a.globalVoiceId = upd.globalVoiceId;
      if (upd.voiceProfile) a.voiceProfile = upd.voiceProfile;
    }
  });
  console.log("Synced project fields via Store.mutate successfully.");
} finally {
  await store.pool.end();
}
