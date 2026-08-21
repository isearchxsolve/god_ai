import { describe, it, expect } from 'vitest';

export interface SandboxExecutionOptions {
  command: string[];
  args: string[];
  cwd: string;
  allowedPaths: string[];
  envFilter: string[];
  timeoutMs: number;
}

export interface SandboxExecutionResult {
  exitCode: number;
  stdout: string;
  stderr: string;
  blockedViolation?: string;
}

export interface SandboxExecutor {
  execute(opts: SandboxExecutionOptions): Promise<SandboxExecutionResult>;
}

describe('ASES v3.1 Baseline: Execution Sandbox Security', () => {
  const mockSandbox: SandboxExecutor = {
    async execute(opts: SandboxExecutionOptions): Promise<SandboxExecutionResult> {
      // Rule 1: Command array check (no shell concatenation string allowed)
      if (opts.args.some((arg) => arg.includes(';') || arg.includes('&&') || arg.includes('|'))) {
        return {
          exitCode: 126,
          stdout: '',
          stderr: 'SECURITY_VIOLATION: Shell meta-characters prohibited in execution arguments',
          blockedViolation: 'SHELL_INJECTION_DETECTED'
        };
      }

      // Rule 2: Path traversal check
      if (opts.cwd.includes('..') || !opts.allowedPaths.some((p) => opts.cwd.startsWith(p))) {
        return {
          exitCode: 127,
          stdout: '',
          stderr: 'SECURITY_VIOLATION: Path traversal outside sandbox root detected',
          blockedViolation: 'PATH_TRAVERSAL_DETECTED'
        };
      }

      // Rule 3: Timeout enforcement
      if (opts.timeoutMs <= 0 || opts.timeoutMs > 30000) {
        return {
          exitCode: 124,
          stdout: '',
          stderr: 'SECURITY_VIOLATION: Timeout configuration out of bounds',
          blockedViolation: 'INVALID_TIMEOUT_BOUNDS'
        };
      }

      return { exitCode: 0, stdout: 'Execution successful', stderr: '' };
    }
  };

  it('should block execution attempts containing shell chaining injection attacks', async () => {
    const maliciousOpts: SandboxExecutionOptions = {
      command: ['node'],
      args: ['index.js', '; cat /etc/passwd'],
      cwd: '/sandbox/workspace',
      allowedPaths: ['/sandbox/workspace'],
      envFilter: ['NODE_ENV'],
      timeoutMs: 5000
    };

    const result = await mockSandbox.execute(maliciousOpts);
    expect(result.exitCode).not.toBe(0);
    expect(result.blockedViolation).toBe('SHELL_INJECTION_DETECTED');
  });

  it('should block execution when directory path traverses outside allowed sandbox workspace', async () => {
    const traversalOpts: SandboxExecutionOptions = {
      command: ['npm'],
      args: ['test'],
      cwd: '/sandbox/workspace/../../root',
      allowedPaths: ['/sandbox/workspace'],
      envFilter: ['NODE_ENV'],
      timeoutMs: 5000
    };

    const result = await mockSandbox.execute(traversalOpts);
    expect(result.exitCode).not.toBe(0);
    expect(result.blockedViolation).toBe('PATH_TRAVERSAL_DETECTED');
  });
});
