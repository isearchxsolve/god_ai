/**
 * SignupCrawler — PlaywrightCrawler with stealth, session persistence, and form filling.
 * Handles signup, signin, and form detection across all 25 platforms.
 */

const { PlaywrightCrawler, RequestQueue, Dataset } = require('crawlee');
const { PLATFORMS } = require('./config');
const { StealthUtils } = require('./stealth-utils');
const { SessionManager } = require('./session-manager');
const fs = require('fs-extra');
const path = require('path');

const SCREENSHOT_DIR = process.env.SCREENSHOT_DIR || './screenshots';
fs.ensureDirSync(SCREENSHOT_DIR);

class SignupCrawler {
  constructor(options = {}) {
    this.stealth = new StealthUtils(options);
    this.sessions = new SessionManager();
    this.maxConcurrency = options.maxConcurrency || parseInt(process.env.MAX_CONCURRENCY, 10) || 4;
    this.timeout = options.timeout || parseInt(process.env.REQUEST_TIMEOUT, 10) || 60000;
    this.saveScreenshots = options.saveScreenshots !== false;
    // FIX: Crawlee's fingerprint injection (useFingerprints: true) is itself a bot signal —
    // huggingface.co serves "Let's confirm you are human" when fingerprints are injected,
    // while the same crawler WITHOUT fingerprints renders the signup form normally.
    // Default OFF; opt in per-platform via options.useFingerprints === true.
    this.useFingerprints = options.useFingerprints === true;
  }

  /**
   * Run signup/signin for a single platform.
   */
  async runPlatform(platformName, credentials, mode = 'signup') {
    const config = PLATFORMS[platformName];
    if (!config) {
      throw new Error(`Unknown platform: ${platformName}`);
    }

    const url = config[mode] || config.signup;
    const selectors = config.selectors || {};
    const results = {
      platform: platformName,
      mode,
      url,
      success: false,
      filledFields: {},
      cookies: null,
      screenshot: null,
      logs: [],
      error: null,
    };
    const proxyConfig = await this.stealth.buildProxyConfig();
    const launchOptions = this.stealth.buildLaunchOptions();
    const prevSession = await this.sessions.load(platformName);
    const self = this; // FIX: requestHandler is invoked as a plain function — `this` is undefined inside it

    const crawler = new PlaywrightCrawler({
      proxyConfiguration: proxyConfig,
      launchContext: { launchOptions },
      browserPoolOptions: {
        useFingerprints: this.useFingerprints,
        fingerprintOptions: {
          fingerprintGeneratorOptions: {
            browsers: ['chrome'],
            devices: ['desktop'],
            operatingSystems: ['windows'],
          },
        },
      },
      maxConcurrency: 1, // one platform at a time per call
      requestHandlerTimeoutSecs: this.timeout / 1000,

      async requestHandler({ page, request, log: crawlerLog }) {
        const log = (msg) => {
          crawlerLog.info(msg);
          results.logs.push(msg);
        };

        // ── Restore previous session if available ──
        if (prevSession && prevSession.cookies && prevSession.cookies.length > 0) {
          try {
            await page.context().addCookies(prevSession.cookies);
            log(`[${platformName}] Session restored (${prevSession.cookies.length} cookies)`);
          } catch (e) {
            log(`[${platformName}] Session restore failed: ${e.message}`);
          }
        }

        log(`[${platformName}] Navigating to ${url}`);
        // FIX: addInitScript only applies to FUTURE navigations — inject BEFORE goto
        // so the initial page load is already stealthed (otherwise navigator.webdriver is exposed).
        await self.stealth.injectStealthScripts(page);
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: self.timeout });
        log(`[${platformName}] Stealth scripts injected, page loaded`);

        // Random mouse wander before interaction
        await page.mouse.move(100 + Math.random() * 300, 100 + Math.random() * 300);
        await page.waitForTimeout(500 + Math.random() * 1000);

        // ── Wait for the form to render (SPA hydration) ──
        // Sites like huggingface.co/join render inputs client-side after JS hydration,
        // so the DOM is empty at domcontentloaded. Wait for any known field selector.
        const waitSelectors = [selectors.email, selectors.password, selectors.username, 'input[type="email"]', 'input[type="password"]'].filter(Boolean);
        let formReady = false;
        for (const ws of waitSelectors) {
          try {
            await page.waitForSelector(ws, { state: 'visible', timeout: 8000 });
            formReady = true;
            log(`[${platformName}] Form field visible: ${ws}`);
            break;
          } catch (e) { /* try next selector */ }
        }
        if (!formReady) {
          log(`[${platformName}] No known form field appeared within timeout — proceeding anyway`);
        }
        // Give the SPA a beat to finish hydrating all fields
        await page.waitForTimeout(800 + Math.random() * 700);

        // Diagnostic: log every visible input so failures are self-explaining
        try {
          const inputs = await page.locator('input:visible').all();
          const summary = [];
          for (const inp of inputs) {
            const t = (await inp.getAttribute('type').catch(() => '')) || '';
            const n = (await inp.getAttribute('name').catch(() => '')) || '';
            summary.push(`${t || 'text'}:${n}`);
          }
          log(`[${platformName}] Visible inputs: [${summary.join(', ')}]`);
        } catch (e) { /* non-fatal */ }

        // ── Cloudflare / anti-bot detection ──
        const title = await page.title().catch(() => '');
        const bodyText = await page.locator('body').innerText().catch(() => '');
        if (title.toLowerCase().includes('just a moment') || bodyText.toLowerCase().includes('checking your browser')) {
          log(`[${platformName}] Cloudflare challenge detected — waiting...`);
          let cleared = false;
          for (let i = 0; i < 30; i++) {
            await page.waitForTimeout(1000);
            const newTitle = await page.title().catch(() => '');
            if (!newTitle.toLowerCase().includes('just a moment')) {
              cleared = true;
              break;
            }
          }
          if (!cleared) {
            results.error = 'Cloudflare challenge not cleared';
            return;
          }
        }

        // ── HuggingFace-style "confirm you are human" interstitial ──
        // HF serves this when it suspects automation; clicking Begin usually runs a
        // Turnstile check that passes in a real (non-fingerprinted) browser.
        if (bodyText.toLowerCase().includes("let's confirm you are human") || bodyText.toLowerCase().includes('confirm you are human')) {
          log(`[${platformName}] Human-confirmation interstitial detected — clicking Begin`);
          const beginBtn = page.locator('button:has-text("Begin"), a:has-text("Begin")').first();
          if (await beginBtn.count().catch(() => 0)) {
            await beginBtn.click().catch(() => {});
            // wait for the check to resolve and the form to appear
            let resolved = false;
            for (let i = 0; i < 30; i++) {
              await page.waitForTimeout(1000);
              const nInputs = await page.locator('input:visible').count().catch(() => 0);
              const txt = await page.locator('body').innerText().catch(() => '');
              if (nInputs > 0 || !txt.toLowerCase().includes('confirm you are human')) {
                resolved = true;
                log(`[${platformName}] Human check resolved after ${i + 1}s (inputs: ${nInputs})`);
                break;
              }
            }
            if (!resolved) {
              results.error = 'Human-confirmation check did not resolve (captcha likely required)';
              log(`[${platformName}] ${results.error}`);
              if (self.saveScreenshots) {
                const sp = path.join(SCREENSHOT_DIR, `${platformName}-captcha-${Date.now()}.png`);
                await page.screenshot({ path: sp, fullPage: true }).catch(() => {});
                results.screenshot = sp;
              }
              return;
            }
          }
        }

        // ── Fill form fields ──
        const creds = credentials || {};

        // Email
        if (selectors.email && creds.email) {
          const filled = await self.stealth.humanType(page, selectors.email, creds.email);
          results.filledFields.email = filled;
          if (filled) log(`[${platformName}] Email filled`);
        }

        // Password
        if (selectors.password && creds.password) {
          const filled = await self.stealth.humanType(page, selectors.password, creds.password);
          results.filledFields.password = filled;
          if (filled) log(`[${platformName}] Password filled`);
        }

        // Username
        if (selectors.username && creds.username) {
          const filled = await self.stealth.humanType(page, selectors.username, creds.username);
          results.filledFields.username = filled;
          if (filled) log(`[${platformName}] Username filled`);
        }

        // First name
        if (selectors.firstName && creds.firstName) {
          const filled = await self.stealth.humanType(page, selectors.firstName, creds.firstName);
          results.filledFields.firstName = filled;
          if (filled) log(`[${platformName}] First name filled`);
        }

        // Last name
        if (selectors.lastName && creds.lastName) {
          const filled = await self.stealth.humanType(page, selectors.lastName, creds.lastName);
          results.filledFields.lastName = filled;
          if (filled) log(`[${platformName}] Last name filled`);
        }

        // ── Check terms checkboxes ──
        const checkboxes = await page.locator('input[type="checkbox"]').all();
        for (const cb of checkboxes) {
          const label = await cb.locator('xpath=ancestor::label').innerText().catch(() => '');
          const ariaLabel = await cb.getAttribute('aria-label').catch(() => '');
          const combined = (label + ' ' + ariaLabel).toLowerCase();
          const keywords = ['agree', 'terms', 'accept', 'consent', 'privacy', 'confirm', 'read and agree'];
          if (keywords.some(k => combined.includes(k))) {
            const isChecked = await cb.isChecked().catch(() => false);
            if (!isChecked) {
              await cb.click();
              log(`[${platformName}] Checked terms checkbox`);
            }
          }
        }

        // ── Submit ──
        if (selectors.submit) {
          await self.stealth.humanScroll(page, 300);
          const clicked = await self.stealth.humanClick(page, selectors.submit);
          if (clicked) {
            log(`[${platformName}] Submit clicked`);
            await page.waitForTimeout(2000 + Math.random() * 3000);
          }
        }

        // ── Multi-step flow handling ──
        // Some sites (e.g. huggingface) split signup across steps:
        // step 1 email+password -> Next -> step 2 username -> Create account.
        for (let step = 0; step < 3; step++) {
          await page.waitForTimeout(2000);
          const visibleInputs = await page.locator('input:visible').all();
          let filledAny = false;
          for (const inp of visibleInputs) {
            const type = ((await inp.getAttribute('type').catch(() => '')) || '').toLowerCase();
            const name = (await inp.getAttribute('name').catch(() => '')) || '';
            const autocomplete = (await inp.getAttribute('autocomplete').catch(() => '')) || '';
            const value = await inp.inputValue().catch(() => '');
            if (value) continue; // already filled
            let fillWith = null;
            let field = null;
            if (type === 'password' && creds.password) {
              fillWith = creds.password; field = 'password';
            } else if (type === 'email' && creds.email) {
              fillWith = creds.email; field = 'email';
            } else if (type === 'text' || type === '') {
              const hint = `${name} ${autocomplete}`.toLowerCase();
              if (/user/.test(hint) && creds.username) {
                fillWith = creds.username; field = 'username';
              } else if (/name/.test(hint) && creds.fullName) {
                fillWith = creds.fullName; field = 'fullName';
              }
            }
            if (fillWith) {
              try {
                await inp.click();
                await page.waitForTimeout(150 + Math.random() * 300);
                await page.keyboard.type(fillWith, { delay: 40 + Math.random() * 80 });
                results.filledFields[field] = true;
                filledAny = true;
                log(`[${platformName}] Step ${step + 2}: filled ${field}`);
              } catch (e) {
                log(`[${platformName}] Step ${step + 2}: failed to fill ${field}: ${e.message}`);
              }
            }
          }
          if (!filledAny) break; // no new fields — flow complete or blocked

          // re-check any terms checkboxes revealed in later steps
          const laterBoxes = await page.locator('input[type="checkbox"]:visible').all();
          for (const cb of laterBoxes) {
            const label = await cb.locator('xpath=ancestor::label').innerText().catch(() => '');
            const ariaLabel = await cb.getAttribute('aria-label').catch(() => '');
            const combined = (label + ' ' + ariaLabel).toLowerCase();
            const keywords = ['agree', 'terms', 'accept', 'consent', 'privacy', 'confirm'];
            if (keywords.some(k => combined.includes(k))) {
              const isChecked = await cb.isChecked().catch(() => false);
              if (!isChecked) {
                await cb.click().catch(() => {});
                log(`[${platformName}] Step ${step + 2}: checked terms checkbox`);
              }
            }
          }

          // click the next submit button
          const submitBtn = page.locator('button[type="submit"]:visible').last();
          if (await submitBtn.count().catch(() => 0)) {
            await submitBtn.click().catch(() => {});
            log(`[${platformName}] Step ${step + 2}: submit clicked`);
            await page.waitForTimeout(2500 + Math.random() * 2000);
          } else {
            break;
          }
        }

        // ── Screenshot ──
        if (self.saveScreenshots) {
          const screenshotPath = path.join(SCREENSHOT_DIR, `${platformName}-${Date.now()}.png`);
          await page.screenshot({ path: screenshotPath, fullPage: true });
          results.screenshot = screenshotPath;
          log(`[${platformName}] Screenshot saved: ${screenshotPath}`);
        }

        // ── Save session ──
        const sessionFile = await self.sessions.save(platformName, page.context());
        results.cookies = sessionFile;
        log(`[${platformName}] Session saved`);

        results.success = Object.values(results.filledFields).some(v => v);
      },

      async failedRequestHandler({ request, log, error }) {
        log.error(`[${platformName}] Request failed: ${error.message}`);
        results.error = error.message;
      },
    });

    // FIX: pass the request directly to run() — manually opening RequestQueue + addRequest()
    // then calling bare run() races against the crawler's internal queue init (0 requests processed).
    await crawler.run([{ url, uniqueKey: `${platformName}-${mode}-${Date.now()}` }]);
    await crawler.teardown();

    return results;
  }

  /**
   * Run multiple platforms in parallel.
   */
  async runBatch(jobs) {
    const proxyConfig = await this.stealth.buildProxyConfig();
    const launchOptions = this.stealth.buildLaunchOptions();
    const allResults = [];
    const self = this; // FIX: requestHandler is invoked as a plain function

    const crawler = new PlaywrightCrawler({
      proxyConfiguration: proxyConfig,
      launchContext: { launchOptions },
      browserPoolOptions: {
        useFingerprints: this.useFingerprints,
        fingerprintOptions: {
          fingerprintGeneratorOptions: {
            browsers: ['chrome'],
            devices: ['desktop'],
            operatingSystems: ['windows'],
          },
        },
      },
      maxConcurrency: this.maxConcurrency,
      requestHandlerTimeoutSecs: this.timeout / 1000,

      async requestHandler({ page, request, log: crawlerLog }) {
        const { platformName, credentials, mode } = request.userData;
        const config = PLATFORMS[platformName];
        if (!config) {
          crawlerLog.error(`Unknown platform: ${platformName}`);
          return;
        }

        const selectors = config.selectors || {};
        const result = {
          platform: platformName,
          mode,
          url: request.url,
          success: false,
          filledFields: {},
          cookies: null,
          screenshot: null,
          logs: [],
          error: null,
        };

        // Load session
        const prevSession = await self.sessions.load(platformName);
        if (prevSession) {
          // Note: Crawlee doesn't support per-request context state easily,
          // so we skip session restore in batch mode for simplicity.
        }

        await self.stealth.injectStealthScripts(page);
        await page.mouse.move(100 + Math.random() * 300, 100 + Math.random() * 300);
        await page.waitForTimeout(500 + Math.random() * 1000);

        // Cloudflare check
        const title = await page.title().catch(() => '');
        const bodyText = await page.locator('body').innerText().catch(() => '');
        if (title.toLowerCase().includes('just a moment') || bodyText.toLowerCase().includes('checking your browser')) {
          result.logs.push(`Cloudflare detected on ${platformName}`);
          let cleared = false;
          for (let i = 0; i < 30; i++) {
            await page.waitForTimeout(1000);
            const newTitle = await page.title().catch(() => '');
            if (!newTitle.toLowerCase().includes('just a moment')) {
              cleared = true;
              break;
            }
          }
          if (!cleared) {
            result.error = 'Cloudflare challenge not cleared';
            allResults.push(result);
            return;
          }
        }

        // Fill fields
        const creds = credentials || {};
        for (const [field, selector] of Object.entries(selectors)) {
          if (['email', 'password', 'username', 'firstName', 'lastName'].includes(field) && creds[field]) {
            const filled = await self.stealth.humanType(page, selector, creds[field]);
            result.filledFields[field] = filled;
            if (filled) result.logs.push(`${field} filled`);
          }
        }

        // Check terms
        const checkboxes = await page.locator('input[type="checkbox"]').all();
        for (const cb of checkboxes) {
          const label = await cb.locator('xpath=ancestor::label').innerText().catch(() => '');
          const ariaLabel = await cb.getAttribute('aria-label').catch(() => '');
          const combined = (label + ' ' + ariaLabel).toLowerCase();
          const keywords = ['agree', 'terms', 'accept', 'consent', 'privacy', 'confirm', 'read and agree'];
          if (keywords.some(k => combined.includes(k))) {
            const isChecked = await cb.isChecked().catch(() => false);
            if (!isChecked) {
              await cb.click();
              result.logs.push('Checked terms checkbox');
            }
          }
        }

        // Submit
        if (selectors.submit) {
          await self.stealth.humanScroll(page, 300);
          const clicked = await self.stealth.humanClick(page, selectors.submit);
          if (clicked) {
            result.logs.push('Submit clicked');
            await page.waitForTimeout(2000 + Math.random() * 3000);
          }
        }

        // Screenshot
        if (self.saveScreenshots) {
          const screenshotPath = path.join(SCREENSHOT_DIR, `${platformName}-${Date.now()}.png`);
          await page.screenshot({ path: screenshotPath, fullPage: true });
          result.screenshot = screenshotPath;
        }

        // Save session
        const sessionFile = await self.sessions.save(platformName, page.context());
        result.cookies = sessionFile;
        result.success = Object.values(result.filledFields).some(v => v);
        allResults.push(result);
      },

      async failedRequestHandler({ request, log, error }) {
        const { platformName } = request.userData;
        log.error(`[${platformName}] Failed: ${error.message}`);
        allResults.push({
          platform: platformName,
          error: error.message,
          success: false,
        });
      },
    });

    // FIX: pass requests directly to run() — see runPlatform for why manual queue.addRequest races.
    const requests = jobs.map((job) => ({
      url: PLATFORMS[job.platform]?.[job.mode] || PLATFORMS[job.platform]?.signup,
      userData: job,
      uniqueKey: `${job.platform}-${job.mode}-${Date.now()}`,
    }));
    await crawler.run(requests);
    await crawler.teardown();

    return allResults;
  }
}

module.exports = { SignupCrawler };
