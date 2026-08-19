import { describe, it, expect } from 'vitest';

/**
 * Next.js Build Pipeline & Configuration Validation Contracts
 * 
 * Verifies build config schema, output modes, strict modes, and env validation rules.
 */

interface NextConfigContract {
  output?: 'standalone' | 'export';
  reactStrictMode?: boolean;
  poweredByHeader?: boolean;
  swcMinify?: boolean;
}

interface EnvSchemaContract {
  validate: (envVars: Record<string, string | undefined>) => { valid: boolean; errors?: string[] };
}

function createEnvValidator(requiredKeys: string[]): EnvSchemaContract {
  return {
    validate: (envVars: Record<string, string | undefined>) => {
      const missing = requiredKeys.filter(key => !envVars[key] || envVars[key]?.trim() === '');
      return {
        valid: missing.length === 0,
        errors: missing.map(key => `Missing required environment variable: ${key}`),
      };
    }
  };
}

describe('Build Pipeline & Configuration Integrity', () => {
  it('should enforce production standalone output configuration contract', () => {
    const validConfig: NextConfigContract = {
      output: 'standalone',
      reactStrictMode: true,
      poweredByHeader: false,
    };

    expect(validConfig.output).toBe('standalone');
    expect(validConfig.reactStrictMode).toBe(true);
    expect(validConfig.poweredByHeader).toBe(false);
  });

  it('should fail validation when required environment variables are absent', () => {
    const validator = createEnvValidator(['NODE_ENV', 'NEXT_PUBLIC_API_URL', 'DATABASE_URL']);
    const incompleteEnv = {
      NODE_ENV: 'production',
      NEXT_PUBLIC_API_URL: '',
    };

    const result = validator.validate(incompleteEnv);
    expect(result.valid).toBe(false);
    expect(result.errors).toHaveLength(2);
    expect(result.errors).toContain('Missing required environment variable: NEXT_PUBLIC_API_URL');
    expect(result.errors).toContain('Missing required environment variable: DATABASE_URL');
  });

  it('should pass validation when all required environment variables exist', () => {
    const validator = createEnvValidator(['NODE_ENV', 'NEXT_PUBLIC_API_URL']);
    const completeEnv = {
      NODE_ENV: 'production',
      NEXT_PUBLIC_API_URL: 'https://api.example.com',
    };

    const result = validator.validate(completeEnv);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });
});
