
require('dotenv').config();
const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');

const HELIUS_RPC = process.env.SOLANA_RPC_URL;
const HELIUS_WSS = HELIUS_RPC ? HELIUS_RPC.replace('https://', 'wss://') : '';
const CANDIDATES_FILE = path.join(__dirname, 'candidates.csv');

// Verified Solana program IDs (post-graduation venues only)
const RAYDIUM_AMM_V4 = '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8';
const PUMPSWAP_AMM  = 'pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA';

const MIN_LP_USD = 0;
const MIN_AGE_HOURS = 0;
const MAX_AGE_HOURS = 72;
const MIN_VOL_LIQ_RATIO = 0;
const MAX_VOL_LIQ_RATIO = 100;
const MAX_TOP_HOLDER_PCT = 20;   // includes LP, so cap is looser than 10%
const MAX_TOP10_HOLDERS_PCT = 60; // same reason

const SOL_MINT = 'So11111111111111111111111111111111111111112';

if (!fs.existsSync(CANDIDATES_FILE)) {
    fs.writeFileSync(CANDIDATES_FILE,
        'timestamp,mint,rugcheck_score,liq_usd,age_hours,top1_pct,top10_pct,vol_liq_ratio,dexscreener_url\n');
}

function log(msg) { console.log(`[${new Date().toISOString()}] ${msg}`); }

async function rugcheckPass(mint) {
    try {
        const r = await fetch(`https://api.rugcheck.xyz/v1/tokens/${mint}/report/summary`);
        if (!r.ok) return { pass: false, reason: `rugcheck http ${r.status}` };
        const d = await r.json();
        if (d.mintAuthority) return { pass: false, reason: 'mint authority not revoked' };
        if (d.freezeAuthority) return { pass: false, reason: 'freeze authority not revoked' };
        const risks = d.risks || [];
        if (risks.some(x => x.level === 'danger')) return { pass: false, reason: 'rugcheck danger flag' };
        if (risks.some(x => x.level === 'high'))   return { pass: false, reason: 'rugcheck high-risk flag' };
        return { pass: true, score: d.score ?? 0 };
    } catch (e) { return { pass: false, reason: `rugcheck err: ${e.message}` }; }
}

async function dexscreenerPass(mint) {
    try {
        const r = await fetch(`https://api.dexscreener.com/latest/dex/tokens/${mint}`);
        if (!r.ok) return { pass: false, reason: `dex http ${r.status}` };
        const d = await r.json();
        const sol = (d.pairs || []).filter(p => p.chainId === 'solana');
        if (!sol.length) return { pass: false, reason: 'no solana pair' };
        const best = sol.sort((a, b) => (b.liquidity?.usd || 0) - (a.liquidity?.usd || 0))[0];
        const liq = best.liquidity?.usd || 0;
        const vol = best.volume?.h24 || 0;
        const ageH = (Date.now() - (best.pairCreatedAt || Date.now())) / 3600000;
        const ratio = liq > 0 ? vol / liq : 0;
        if (liq < MIN_LP_USD)      return { pass: false, reason: `liq $${liq.toFixed(0)} < $${MIN_LP_USD}` };
        if (ageH < MIN_AGE_HOURS)  return { pass: false, reason: `age ${ageH.toFixed(1)}h < ${MIN_AGE_HOURS}h` };
        if (ageH > MAX_AGE_HOURS)  return { pass: false, reason: `age ${ageH.toFixed(1)}h > ${MAX_AGE_HOURS}h` };
        if (ratio < MIN_VOL_LIQ_RATIO) return { pass: false, reason: `vol/liq ${ratio.toFixed(2)} (dead)` };
        if (ratio > MAX_VOL_LIQ_RATIO) return { pass: false, reason: `vol/liq ${ratio.toFixed(2)} (wash)` };
        return { pass: true, liq, ageH, ratio, url: best.url };
    } catch (e) { return { pass: false, reason: `dex err: ${e.message}` }; }
}

async function holderPass(mint) {
    try {
        const lg = await (await fetch(HELIUS_RPC, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'getTokenLargestAccounts', params: [mint] })
        })).json();
        const accs = lg.result?.value || [];
        // if (accs.length < 10) return { pass: false, reason: 'too few large holders' };
        const sup = await (await fetch(HELIUS_RPC, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'getTokenSupply', params: [mint] })
        })).json();
        const total = Number(sup.result?.value?.amount || 0);
        if (!total) return { pass: false, reason: 'zero supply' };
        const top1  = (Number(accs[0].amount) / total) * 100;
        const top10 = accs.slice(0, 10).reduce((s, a) => s + Number(a.amount), 0) / total * 100;
        if (top1  > MAX_TOP_HOLDER_PCT)   return { pass: false, reason: `top1 ${top1.toFixed(1)}%` };
        if (top10 > MAX_TOP10_HOLDERS_PCT) return { pass: false, reason: `top10 ${top10.toFixed(1)}%` };
        return { pass: true, top1, top10 };
    } catch (e) { return { pass: false, reason: `holder err: ${e.message}` }; }
}

const seen = new Set();
const q = [];
let busy = false;

async function evaluate(mint) {
    const row = [
        new Date().toISOString(), mint, '0', '0', '0', '0', '0', '0', 'none'
    ].join(',') + '\n';
    fs.appendFileSync(CANDIDATES_FILE, row);
    log(`★ FAST INJECT: ${mint} | Queued to engine in milliseconds!`);
}

async function drain() {
    if (busy) return; busy = true;
    while (q.length) {
        const m = q.shift();
        if (seen.has(m)) continue;
        seen.add(m);
        try { await evaluate(m); } catch (e) { log(`eval err: ${e.message}`); }
        await new Promise(r => setTimeout(r, 600));
    }
    busy = false;
}

function extractMints(logs) {
    const out = new Set();
    const MINT_REGEX = /[1-9A-HJ-NP-Za-km-z]{32,44}/g;
    for (const l of logs) {
        if (l.includes('Program log: initialize2') || l.includes('InitializeMint')) {
            const m = l.match(MINT_REGEX);
            if (m) m.forEach(x => {
                if (x.endsWith('pump')) out.add(x);
            });
        }
    }
    return [...out];
}

function connect(program) {
    const ws = new WebSocket(HELIUS_WSS);
    ws.on('open', () => {
        log(`WSS subscribed to ${program.slice(0, 8)}…`);
        ws.send(JSON.stringify({
            jsonrpc: '2.0', id: 1, method: 'logsSubscribe',
            params: [{ mentions: [program] }, { commitment: 'confirmed' }]
        }));
    });
    let msgCount = 0;
    ws.on('message', async raw => {
        try {
            const m = JSON.parse(raw);
            const signature = m?.params?.result?.value?.signature;
            const logs = m?.params?.result?.value?.logs;
            if (!signature || !logs) return;
            const isInit = logs.some(l => l.includes('initialize2') || l.includes('InitializePool') || l.includes('CreatePool') || l.includes('InitializeMint2') || l.includes('Instruction: Create'));
            if (!isInit) return;
            
            log(`Detected init signature: ${signature}`);
            let mints = new Set();
            try {
                const res = await fetch(HELIUS_RPC, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        jsonrpc: '2.0', id: 1, method: 'getTransaction',
                        params: [signature, { encoding: 'jsonParsed', maxSupportedTransactionVersion: 0 }]
                    })
                });
                const data = await res.json();
                if (data?.error) log(`RPC Error: ${JSON.stringify(data.error)}`);
                const pBalances = data?.result?.meta?.postTokenBalances || [];
                log(`Found ${pBalances.length} token balances in tx ${signature}`);
                for (const b of pBalances) {
                    if (b.mint && b.mint !== SOL_MINT && b.mint.length >= 32) mints.add(b.mint);
                }
            } catch (err) {
                log(`RPC Fetch Error: ${err.message}`);
            }
            
            if (mints.size === 0) {
                log(`Fallback: extracting mints from logs for ${signature}`);
                const extracted = extractMints(logs);
                extracted.forEach(m => {
                    if (m !== SOL_MINT) mints.add(m);
                });
            }
            if (mints.size === 0) log(`No valid new token mints found in tx ${signature}`);
            
            [...mints].forEach(x => {
                log(`Queued newly initialized mint: ${x}`);
                q.push(x);
            });
            drain();
        } catch (e) {
            log(`WSS message error: ${e.message}`);
        }
    });
    ws.on('close', () => { log(`WSS closed ${program.slice(0, 8)}, reconnecting…`); setTimeout(() => connect(program), 3000); });
    ws.on('error', e => log(`WSS error: ${e.message}`));
}

log('Scanner starting (no private key, read-only)…');
connect(RAYDIUM_AMM_V4);
connect(PUMPSWAP_AMM);

