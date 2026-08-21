```javascript
// server/routes/generate.js
const express = require('express');
const router = express.Router();
const jwt = require('jsonwebtoken');
const fetch = require('node-fetch');

// --- Auth Middleware ---
// Requires a Bearer JWT token in the Authorization header.
const requireBearerJWT = (req, res, next) => {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ 
      error: 'Unauthorized', 
      message: 'Authentication required. Provide a Bearer token.' 
    });
  }

  const token = authHeader.split(' ')[1];

  try {
    // Verify the token using the secret from environment variables.
    // expiresIn is ignored by verify, but ensures validity.
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    
    // Attach user payload to request for downstream usage if needed
    req.user = decoded;
    next();
  } catch (err) {
    if (err.name === 'TokenExpiredError') {
      return res.status(401).json({ 
        error: 'TokenExpired', 
        message: 'Your session has expired. Please login again.' 
      });
    }
    
    return res.status(401).json({ 
      error: 'InvalidToken', 
      message: 'Invalid or malformed authentication token.' 
    });
  }
};

// --- Validation Middleware ---
const validateGenerateInput = (req, res, next) => {
  const { prompt, stack } = req.body;

  if (typeof prompt !== 'string' || prompt.trim() === '') {
    return res.status(400).json({ 
      error: 'ValidationError', 
      message: 'Field "prompt" is required and must be a non-empty string.' 
    });
  }

  if (typeof stack !== 'string' || stack.trim() === '') {
    return res.status(400).json({ 
      error: 'ValidationError', 
      message: 'Field "stack" is required and must be a non-empty string.' 
    });
  }

  next();
};

// --- POST /code ---
// Calls NVIDIA NIM to generate code based on the prompt and target stack.
router.post('/code', requireBearerJWT, validateGenerateInput, async (req, res) => {
  try {
    const { prompt, stack } = req.body;
    
    // Configuration for NVIDIA NIM API
    const NIM_BASE_URL = process.env.NVIDIA_NIM_BASE_URL || 'https://integrate.api.nvidia.com/v1';
    const NIM_API_KEY = process.env.NVIDIA_NIM_API_KEY;
    const NIM_MODEL = process.env.NVIDIA_NIM_MODEL || 'meta/llama3-70b-instruct';

    if (!NIM_API_KEY) {
      console.error('[Generate] Missing NVIDIA_NIM_API_KEY environment variable');
      return res.status(500).json({ 
        error: 'ServerError', 
        message: 'Code generation is not properly configured.' 
      });
    }

    // Construct the payload for standard OpenAI-compatible Chat Completions API (used by NIM)
    const systemInstruction = `You are an expert senior software engineer. 
Your task is to generate clean, highly performant, and production-ready code.
The user will provide a prompt and a target technical stack. 
Output ONLY the raw code without markdown formatting blocks, explanations, or comments unless explicitly requested.
Target Stack: ${stack}.`;

    const fetchPayload = {
      model: NIM_MODEL,
      messages: [
        { role: 'system', content: systemInstruction },
        { role: 'user', content: prompt }
      ],
      temperature: 0.2,    // Lower temperature for more deterministic code generation
      max_tokens: 4000,    // Ensure enough space for standard files
      top_p: 0.7,
      stream: false
    };

    const nimResponse = await fetch(`${NIM_BASE_URL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${NIM_API_KEY}`
      },
      body: JSON.stringify(fetchPayload)
    });

    const rawBody = await nimResponse.text();

    if (!nimResponse.ok) {
      console.error(`[Generate] NVIDIA NIM Error ${nimResponse.status}: ${rawBody}`);
      return res.status(502).json({ 
        error: 'AIProviderError', 
        message: 'The code generation AI provider returned an error.' 
      });
    }

    let parsedData;
    try {
      parsedData = JSON.parse(rawBody);
    } catch (e) {
      console.error('[Generate] Failed to parse NIM JSON response:', e.message);
      return res.status(502).json({ 
        error: 'AIProviderError', 
        message: 'Received malformed response from AI provider.' 
      });
    }

    const generatedCode = parsedData?.choices?.[0]?.message?.content;

    if (!generatedCode) {
      console.error('[Generate] Empty or invalid completion returned from NIM:', parsedData);
      return res.status(502).json({ 
        error: 'AIProviderError', 
        message: 'The AI provider did not return any generated content.' 
      });
    }

    return res.status(200).json({
      code: generatedCode.trim()
    });

  } catch (err) {
    console.error('[Generate] Unexpected Server Error:', err);
    return res.status(500).json({ 
      error: 'ServerError', 
      message: 'An unexpected internal server error occurred.' 
    });
  }
});

module.exports = router;
```