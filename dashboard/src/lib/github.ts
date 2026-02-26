import { Octokit } from "@octokit/rest";
import fs from "fs/promises";
import path from "path";

const REPO_ROOT = path.resolve(process.cwd(), "..");

function isLocal(): boolean {
  return process.env.NODE_ENV === "development";
}

// --- Local filesystem (development) ---

async function localReadFile<T>(filePath: string): Promise<T | null> {
  try {
    const abs = path.join(REPO_ROOT, filePath);
    const raw = await fs.readFile(abs, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

async function localListDir(
  dirPath: string
): Promise<{ name: string; type: string; path: string }[]> {
  try {
    const abs = path.join(REPO_ROOT, dirPath);
    const entries = await fs.readdir(abs, { withFileTypes: true });
    return entries.map((e) => ({
      name: e.name,
      type: e.isDirectory() ? "dir" : "file",
      path: path.join(dirPath, e.name),
    }));
  } catch {
    return [];
  }
}

// --- GitHub API (production) ---

function getOctokit() {
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    console.warn("[github] GITHUB_TOKEN is not set — API calls will fail for private repos");
  }
  return new Octokit({ auth: token });
}

function getOwner(): string {
  const owner = process.env.GITHUB_OWNER;
  if (!owner) throw new Error("GITHUB_OWNER environment variable is not set");
  return owner;
}

function getRepo(): string {
  const repo = process.env.GITHUB_REPO;
  if (!repo) throw new Error("GITHUB_REPO environment variable is not set");
  return repo;
}

// --- Public API ---

export async function getFileContent<T>(filePath: string): Promise<T | null> {
  if (isLocal()) return localReadFile<T>(filePath);

  try {
    const { data } = await getOctokit().repos.getContent({
      owner: getOwner(),
      repo: getRepo(),
      path: filePath,
    });

    if ("content" in data && data.content) {
      const decoded = Buffer.from(data.content, "base64").toString("utf-8");
      return JSON.parse(decoded) as T;
    }
    return null;
  } catch (err) {
    console.error(`[github] Failed to fetch file: ${filePath}`, err instanceof Error ? err.message : err);
    return null;
  }
}

export async function listDirectory(
  dirPath: string
): Promise<{ name: string; type: string; path: string }[]> {
  if (isLocal()) return localListDir(dirPath);

  try {
    const { data } = await getOctokit().repos.getContent({
      owner: getOwner(),
      repo: getRepo(),
      path: dirPath,
    });

    if (Array.isArray(data)) {
      return data.map((item) => ({
        name: item.name,
        type: item.type,
        path: item.path,
      }));
    }
    return [];
  } catch (err) {
    console.error(`[github] Failed to list directory: ${dirPath}`, err instanceof Error ? err.message : err);
    return [];
  }
}

export async function triggerWorkflow(
  workflowFile: string,
  inputs: Record<string, string>
): Promise<boolean> {
  try {
    await getOctokit().actions.createWorkflowDispatch({
      owner: getOwner(),
      repo: getRepo(),
      workflow_id: workflowFile,
      ref: "main",
      inputs,
    });
    return true;
  } catch (err) {
    console.error(`[github] Failed to trigger workflow: ${workflowFile}`, err instanceof Error ? err.message : err);
    return false;
  }
}

export interface WorkflowRun {
  id: number;
  name: string;
  status: string | null;
  conclusion: string | null;
  created_at: string;
  html_url: string;
}

export async function getWorkflowRuns(
  workflowFile: string
): Promise<WorkflowRun[]> {
  const { data } = await getOctokit().actions.listWorkflowRuns({
    owner: getOwner(),
    repo: getRepo(),
    workflow_id: workflowFile,
    per_page: 10,
  });

  return data.workflow_runs.map((run) => ({
    id: run.id,
    name: run.name ?? workflowFile,
    status: run.status,
    conclusion: run.conclusion,
    created_at: run.created_at,
    html_url: run.html_url,
  }));
}
