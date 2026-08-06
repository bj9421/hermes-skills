#!/usr/bin/env node
/**
 * Notehub 工作進度 UI 驗證模板（手機模式）— 2026-08-06 使用者要求自我驗證。
 *
 * 用法：複製此檔到 /opt/data/tmp/，改：
 *   - JOB_TITLE_FILTER：要驗證的 job 標題片段（如 'Cherry Studio' 或 'TEST-增量-PPT'）
 *   - 斷言值（卡片數、checkbox 勾選數、檔案路徑數）
 * 執行：node /opt/data/tmp/verify_xxx.js
 *
 * 前置：bookmark-manager server 已在 5001 跑；Playwright chromium 在
 * /opt/data/tmp/pw-browsers/chromium_headless_shell-1234/chrome-linux/headless_shell
 */
const { chromium, devices } = require('playwright');
const { spawnSync } = require('child_process');
const BASE = 'http://localhost:5001';
const EXEC = '/opt/data/tmp/pw-browsers/chromium_headless_shell-1234/chrome-linux/headless_shell';
const DB = '/opt/data/projects/bookmark-manager/bookmarks.db';

// ── 每支驗證改這裡 ──
const JOB_TITLE_FILTER = 'Cherry Studio';   // job 標題片段
const EXPECT_TOTAL_CARDS = 2;                // 卡片總數
const EXPECT_CHECKED = 4;                    // 目標卡勾選數（逐字稿/整理/音檔/PPT = 4）
const EXPECT_PATH_COUNT = 4;                 // 📁 檔案路徑數
const EXPECT_PCT = null;                     // 期望百分比（null = 不檢查）
// ──────────────────

const py = (code) => spawnSync('python', ['-c', code]);

async function main() {
    const browser = await chromium.launch({ headless: true, executablePath: EXEC, args: ['--no-sandbox'] });
    // ⚠️ 手機模式：必須用 devices['iPhone 13']（含 deviceScaleFactor），不能只設 viewport
    const context = await browser.newContext({ ...devices['iPhone 13'], viewport: { width: 390, height: 844 } });
    const page = await context.newPage();
    let failed = 0;
    page.on('pageerror', err => { failed++; console.log('  ❌ pageerror:', err.message); });

    await page.goto(BASE, { waitUntil: 'networkidle' });
    await page.locator('button.hamburger-btn').first().click();   // ☰ 開 sidebar → 自動切工作進度
    await page.waitForTimeout(2000);                              // 等 job 載入（poll 5s，等 1-2 輪）

    const total = await page.locator('.nh-progress-item').count();
    console.log(`卡片總數: ${total} ${total === EXPECT_TOTAL_CARDS ? '✅' : `❌ 應 ${EXPECT_TOTAL_CARDS}`}`);
    if (total !== EXPECT_TOTAL_CARDS) failed++;

    const item = page.locator('.nh-progress-item').filter({ hasText: JOB_TITLE_FILTER }).first();
    const cnt = await item.count();
    console.log(`目標卡 ${JOB_TITLE_FILTER}: ${cnt} ${cnt === 1 ? '✅' : '❌'}`);
    if (cnt !== 1) failed++;

    if (cnt === 1) {
        // checkbox：容器是 .nh-checks（不是 .nh-artifacts）
        const boxes = await item.locator('.nh-checks input[type="checkbox"]').count();
        console.log(`checkbox 數: ${boxes} ${boxes === 5 ? '✅' : '❌'}`);
        if (boxes !== 5) failed++;
        const labels = await item.locator('.nh-checks label').allTextContents();
        const checked = await item.locator('.nh-checks input[type="checkbox"]:checked').count();
        console.log(`勾選數: ${checked}/5 ${checked === EXPECT_CHECKED ? '✅' : '❌'}`);
        console.log(`  labels: ${labels.join(', ')}`);
        if (checked !== EXPECT_CHECKED) failed++;

        if (EXPECT_PCT) {
            const pctText = await item.locator('.nh-pct').textContent();
            console.log(`百分比: ${pctText.trim()} ${pctText.includes(EXPECT_PCT) ? '✅' : '❌'}`);
            if (!pctText.includes(EXPECT_PCT)) failed++;
            const width = await item.locator('.nh-bar-fill').evaluate(el => el.style.width).catch(() => '');
            console.log(`進度條寬度: ${width} ${width === EXPECT_PCT ? '✅' : '❌'}`);
            if (width !== EXPECT_PCT) failed++;
        }

        // 檔案路徑
        const summary = await item.locator('details.nh-path-toggle summary').first().textContent().catch(() => '');
        console.log(`檔案路徑: ${summary.trim()} ${summary.includes(`(${EXPECT_PATH_COUNT})`) ? '✅' : '❌ 應 (${EXPECT_PATH_COUNT})`}`);
        if (!summary.includes(`(${EXPECT_PATH_COUNT})`)) failed++;
        await item.locator('details.nh-path-toggle summary').first().click();
        await page.waitForTimeout(400);
        const paths = await item.locator('.nh-path').allTextContents();
        console.log(`展開路徑數: ${paths.length} ${paths.length === EXPECT_PATH_COUNT ? '✅' : '❌'}`);
        const hasPpt = paths.some(p => p.includes('.pptx'));
        console.log(`含 PPT 路徑: ${hasPpt ? '✅' : '❌'}`);
        if (paths.length !== EXPECT_PATH_COUNT || !hasPpt) failed++;
    }

    // 截圖 + 自己 vision 確認（使用者要求：不要沒確認就丟給使用者）
    await item.scrollIntoViewIfNeeded().catch(() => {});
    await page.waitForTimeout(300);
    const shot = '/opt/data/tmp/nh_verify.png';
    await page.screenshot({ path: shot });
    console.log(`📸 截圖: ${shot} — 記得 vision_analyze 自己看過再回報`);

    await browser.close();
    console.log(`\n${failed === 0 ? '✅✅ 全部通過' : `❌ ${failed} 項失敗`}`);
    process.exit(failed === 0 ? 0 : 1);
}
main().catch(e => { console.error('FATAL:', e.message); process.exit(1); });
