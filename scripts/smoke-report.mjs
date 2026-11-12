import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
import { createApp } from '../server/app.mjs';

const server = createApp(null).listen(0, '127.0.0.1');
await new Promise(resolve => server.once('listening', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  let calls = 0;
  await page.route('**/api/report-insights', async route => {
    const body = route.request().postDataJSON();
    assert.equal(body.provider, calls === 0 ? 'deepseek' : 'qwen');
    assert.equal(body.model, calls === 0 ? 'deepseek-flash' : 'qwen-plus');
    assert.equal(body.apiKey, 'test-key-123');
    assert.equal(body.report.period, '2026年10月');
    if (++calls === 3) return route.fulfill({ status: 502, contentType: 'application/json', body: JSON.stringify({ error: 'qwen_401' }) });
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ analysis: { summary: '本期信贷管理处罚较多。', recommendations: ['核对授信流程。'], legalNotes: [] } }) });
  });
  await page.goto(base);
  await page.locator('#generateReport:not([disabled])').waitFor({ timeout: 30000 });
  await page.locator('#periodFilter .multi-trigger').click();
  await page.locator('#periodFilter input[data-leaf][value="2026-10"]').check();
  await page.locator('#periodFilter .multi-trigger').click();
  await page.locator('#generateReport').click();
  assert.equal(await page.locator('#aiSettings').evaluate(element => element.open), true);
  await page.locator('#aiKey').fill('test-key-123');
  await page.locator('#aiSettingsForm button[type="submit"]').click();
  await page.getByText('本期信贷管理处罚较多。').waitFor();
  assert.match(await page.locator('#reportBody h2').innerText(), /2026年10月/);
  assert.equal(await page.locator('.report-chart-card').count(), 4);
  assert.equal(await page.locator('.report-fine').count(), 10);
  assert.equal(await page.locator('#reportPrint').isEnabled(), true);
  if (process.env.REPORT_SCREENSHOT) await page.screenshot({ path: process.env.REPORT_SCREENSHOT, fullPage: true });
  await page.emulateMedia({ media: 'print' });
  assert.equal(await page.locator('#reportView').evaluate(element => getComputedStyle(element).display), 'block');
  assert.equal(await page.locator('.sidebar').evaluate(element => getComputedStyle(element).display), 'none');
  await page.emulateMedia({ media: 'screen' });
  await page.locator('#openAiSettings').click();
  await page.locator('#aiProvider').selectOption('qwen');
  assert.equal(await page.locator('#aiRegionGroup').isVisible(), true);
  await page.locator('#aiRegion').selectOption('singapore');
  await page.locator('#aiKey').fill('test-key-123');
  await page.locator('#aiSettingsForm button[type="submit"]').click();
  await page.locator('#regenerateReport').click();
  await page.getByText('本期信贷管理处罚较多。').waitFor();
  await page.locator('#regenerateReport').click();
  await page.locator('#reportStatus').getByText('API Key 无效、地域不匹配或无权调用该模型。').waitFor();
  assert.equal(await page.locator('#reportPrint').isEnabled(), false);
  console.log('Report browser smoke test passed.');
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
