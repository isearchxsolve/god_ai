import { storage } from "./storage";

export async function checkAdvancedFilters(
  tokenAddress: string, 
  pair: any, 
  heliusKey: string
): Promise<{ safe: boolean; reason: string }> {
  let isAdvancedSafe = true;
  let advReason = "advanced_filters_passed";

  // 1. Organic Graduation Speed (Pump.fun)
  if (tokenAddress.endsWith("pump") && pair.dexId === "raydium") {
    // If the token was created and hit Raydium in less than 5 minutes, it's highly botted.
    const ageSeconds = (Date.now() - (pair.pairCreatedAt || Date.now())) / 1000;
    // Raydium pair age. If it's less than 60 seconds since creation, it's very fresh.
    // For pump.fun graduation we ideally want >15m to fill the curve.
    if (ageSeconds < 60) {
      console.log(`[ADV-FILTER] $${pair.baseToken?.symbol} - Pump.fun graduation too fast (botted)`);
    }
  }

  // 2. TweetScout (Twitter Influencer Graph)
  if (pair.info && pair.info.socials) {
    const twitter = pair.info.socials.find((s: any) => s.type === "twitter");
    if (twitter && process.env.TWEETSCOUT_API_KEY) {
      try {
        const username = twitter.url.split("/").pop();
        const tsRes = await fetch(`https://api.tweetscout.io/v2/score-by-username/${username}`, {
          headers: { "ApiKey": process.env.TWEETSCOUT_API_KEY }
        });
        if (tsRes.ok) {
          const tsData = await tsRes.json();
          if (tsData.score < 100) {
            return { safe: false, reason: `tweetscout_score_too_low(${tsData.score})` };
          }
        }
      } catch (err) {
        console.log(`[ADV-FILTER] TweetScout API error:`, err);
      }
    }
  }

  // 3. BubbleMaps (Supply Clustering / Bundles)
  if (process.env.BUBBLEMAPS_API_KEY) {
    try {
      const bmRes = await fetch(`https://api.bubblemaps.io/v1/solana/token/${tokenAddress}`, {
        headers: { "X-API-KEY": process.env.BUBBLEMAPS_API_KEY }
      });
      if (bmRes.ok) {
        const bmData = await bmRes.json();
        if (bmData.clusterScore > 70) {
           return { safe: false, reason: `bubblemaps_dev_bundle_detected(${bmData.clusterScore})` };
        }
      }
    } catch (err) {
      console.log(`[ADV-FILTER] BubbleMaps API error:`, err);
    }
  }

  // 4. Developer History Profiling (Helius RPC)
  if (heliusKey) {
    try {
      const rpcUrl = `https://mainnet.helius-rpc.com/?api-key=${heliusKey}`;
      const sigRes = await fetch(rpcUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: 1,
          method: "getSignaturesForAddress",
          params: [tokenAddress, { limit: 10 }]
        })
      });
      if (sigRes.ok) {
        const sigData = await sigRes.json();
        if (sigData.result && sigData.result.length > 0) {
            // Full trace logic goes here.
            // For now, logging to indicate Helius Developer Profiling is active.
            // console.log(`[ADV-FILTER] Helius Developer trace complete for $${pair.baseToken?.symbol}`);
        }
      }
    } catch (err) {
      console.log(`[ADV-FILTER] Helius Developer Profiling error:`, err);
    }
  }

  return { safe: isAdvancedSafe, reason: advReason };
}
