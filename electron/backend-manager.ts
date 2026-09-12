import fs from 'fs';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import http from 'http';
import { app } from 'electron';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DEFAULT_PORT = 8765;
const HEALTH_PATH = '/api/health';

export class BackendManager {
  private process: ChildProcess | null = null;
  private port = DEFAULT_PORT;
  private baseUrl = `http://127.0.0.1:${DEFAULT_PORT}`;

  getBaseUrl(): string {
    return this.baseUrl;
  }

  async start(): Promise<void> {
    const backendDir = this.resolveBackendDir();
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    const appModule = 'app.main:app';

    this.process = spawn(
      pythonCmd,
      ['-m', 'uvicorn', appModule, '--host', '127.0.0.1', '--port', String(this.port)],
      {
        cwd: backendDir,
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1',
          AAP_DATA_DIR: this.getDataDir(),
        },
        stdio: ['ignore', 'pipe', 'pipe'],
      }
    );

    this.process.stdout?.on('data', (data: Buffer) => {
      console.log('[backend]', data.toString().trim());
    });

    this.process.stderr?.on('data', (data: Buffer) => {
      console.error('[backend]', data.toString().trim());
    });

    await this.waitForHealthy(60000);
  }

  stop(): void {
    if (this.process && !this.process.killed) {
      this.process.kill();
      this.process = null;
    }
  }

  private resolveBackendDir(): string {
    if (process.env.AAP_BACKEND_DIR) {
      return process.env.AAP_BACKEND_DIR;
    }
    // dev: repo/backend; packaged: resources/backend
    const devPath = path.join(__dirname, '..', 'backend');
    const prodPath = path.join(process.resourcesPath, 'backend');
    if (fs.existsSync(path.join(prodPath, 'app', 'main.py'))) {
      return prodPath;
    }
    return devPath;
  }

  private getDataDir(): string {
    return path.join(app.getPath('userData'), 'data');
  }

  private waitForHealthy(timeoutMs: number): Promise<void> {
    const start = Date.now();
    return new Promise((resolve, reject) => {
      const check = () => {
        const req = http.get(`${this.baseUrl}${HEALTH_PATH}`, (res) => {
          if (res.statusCode === 200) {
            resolve();
          } else if (Date.now() - start > timeoutMs) {
            reject(new Error('Backend health check failed'));
          } else {
            setTimeout(check, 500);
          }
        });
        req.on('error', () => {
          if (Date.now() - start > timeoutMs) {
            reject(new Error('Backend failed to start'));
          } else {
            setTimeout(check, 500);
          }
        });
        req.end();
      };
      check();
    });
  }
}
