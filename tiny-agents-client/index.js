// Tiny Agents: an MCP-powered agent in ~50 lines of code
import 'dotenv/config';
import fs from 'fs';
import path from 'path';
import zlib from 'zlib';
import AdmZip from 'adm-zip';
import { Agent } from '@huggingface/mcp-client';

const SERVERS = [
  {
    command: 'npx',
    args: ['@modelcontextprotocol/server-filesystem', 'C:/Users/nikit/Desktop'],
    env: { PATH: process.env.PATH },
  },
];

const agent = new Agent({
  provider: process.env.PROVIDER ?? 'nebius',
  model: process.env.MODEL_ID ?? 'Qwen/Qwen2.5-72B-Instruct',
  apiKey: process.env.HF_TOKEN,
  servers: SERVERS,
});

// Custom tool: search files by name or type
async function searchFiles(pattern) {
  const desktopPath = 'C:/Users/nikit/Desktop';
  const files = await fs.promises.readdir(desktopPath);
  let searchPattern = pattern.trim();
  // Handle 'all PDF files', 'all .txt files', 'all txt files', etc.
  const typeMatch = searchPattern.match(/all\s+\.?([a-z0-9]+) files?/i);
  if (typeMatch) {
    // e.g. 'pdf' or '.txt' -> '.pdf' or '.txt'
    let ext = typeMatch[1].trim();
    if (!ext.startsWith('.')) ext = '.' + ext;
    searchPattern = ext + '$';
  }
  // Also handle '.pdf files', 'pdf files', etc.
  const extMatch = searchPattern.match(/^\.?([a-z0-9]+) files?$/i);
  if (extMatch) {
    let ext = extMatch[1];
    searchPattern = '.' + ext + '$';
  }
  // Only escape dots for regex, not double-escape
  const regex = new RegExp(searchPattern.replace(/\./g, '\\.') .replace(/\*/g, '.*'), 'i');
  const matched = files.filter(f => regex.test(f));
  if (matched.length === 0) return `No files found matching '${pattern}'.`;
  return `Found files: ${matched.join(', ')}`;
}

// Custom tool: move/copy files
async function moveOrCopyFile(src, dest, move = true) {
  const desktopPath = 'C:/Users/nikit/Desktop';
  const srcPath = path.join(desktopPath, src);
  const destPath = path.join(desktopPath, dest);
  try {
    if (!fs.existsSync(srcPath)) return `Source file '${src}' not found.`;
    if (move) {
      await fs.promises.rename(srcPath, destPath);
      return `Moved '${src}' to '${dest}'.`;
    } else {
      await fs.promises.copyFile(srcPath, destPath);
      return `Copied '${src}' to '${dest}'.`;
    }
  } catch (err) {
    return `Error: ${err.message}`;
  }
}

// Custom tool: edit file contents (append/replace)
async function editFile(fileName, appendText, replaceText, replaceWith) {
  const desktopPath = 'C:/Users/nikit/Desktop';
  const filePath = path.join(desktopPath, fileName);
  try {
    if (!fs.existsSync(filePath)) return `File '${fileName}' not found.`;
    let content = await fs.promises.readFile(filePath, 'utf8');
    if (appendText) {
      content += '\n' + appendText;
    }
    if (replaceText && replaceWith !== undefined) {
      content = content.replace(new RegExp(replaceText, 'g'), replaceWith);
    }
    await fs.promises.writeFile(filePath, content, 'utf8');
    return `File '${fileName}' updated.`;
  } catch (err) {
    return `Error editing file: ${err.message}`;
  }
}

// Custom tool: create folder
async function createFolder(folderName) {
  const desktopPath = 'C:/Users/nikit/Desktop';
  const folderPath = path.join(desktopPath, folderName);
  try {
    await fs.promises.mkdir(folderPath, { recursive: true });
    return `Folder '${folderName}' created.`;
  } catch (err) {
    return `Error creating folder: ${err.message}`;
  }
}

// Custom tool: compress files into zip (basic, using zlib)
async function compressFiles(fileNames, zipName) {
  const desktopPath = 'C:/Users/nikit/Desktop';
  const zipPath = path.join(desktopPath, zipName);
  try {
    const zip = new AdmZip();
    for (const fileName of fileNames) {
      const filePath = path.join(desktopPath, fileName);
      if (fs.existsSync(filePath)) {
        zip.addLocalFile(filePath);
      }
    }
    zip.writeZip(zipPath);
    return `Compressed files into '${zipName}'.`;
  } catch (err) {
    return `Error compressing files: ${err.message}`;
  }
}

// Custom tool: summarize file contents
async function summarizeFile(fileName, outputFileName = null, zipInnerFile = null) {
  const desktopPath = 'C:/Users/nikit/Desktop';
  const filePath = path.join(desktopPath, fileName);
  try {
    if (!fs.existsSync(filePath)) return `File '${fileName}' not found.`;
    let summary = '';
    if (fileName.endsWith('.zip')) {
      const zip = new AdmZip(filePath);
      const entries = zip.getEntries();
      if (entries.length === 0) {
        summary = `Zip file '${fileName}' is empty.`;
      } else if (zipInnerFile) {
        // Summarize a specific file inside the zip
        const entry = entries.find(e => !e.isDirectory && e.entryName === zipInnerFile);
        if (!entry) {
          summary = `File '${zipInnerFile}' not found in zip archive '${fileName}'.`;
        } else {
          const content = entry.getData().toString('utf8');
          let agentSummary = '';
          try {
            const response = agent.run(`Summarize the following text. Only use the text provided.\n\n${content}`);
            for await (const message of response) {
              if (message?.content) agentSummary += message.content;
            }
          } catch (e) {
            agentSummary = '[Error generating summary]';
          }
          if (!agentSummary.trim()) {
            // Fallback: show full content (no line limit)
            agentSummary = content;
          }
          summary = `Summary of '${zipInnerFile}' from '${fileName}':\n${agentSummary}`;
        }
      } else {
        // Gather all .txt content
        let allText = '';
        let fileList = [];
        for (const e of entries) {
          if (!e.isDirectory && e.entryName.endsWith('.txt')) {
            let content = e.getData().toString('utf8');
            if (content.trim()) {
              allText += `\n--- ${e.entryName} ---\n${content}\n`;
              fileList.push(e.entryName);
            }
          }
        }
        if (!allText.trim()) {
          summary = `Zip file '${fileName}' contains no non-empty .txt files to summarize.`;
        } else if (allText.length > 16000) {
          summary = `Zip file '${fileName}' contains too much text to summarize at once.`;
        } else {
          // Debug: show the actual text being sent to the LLM
          console.log('[Debug] Text sent to LLM for summarization:', allText);
          let agentSummary = '';
          try {
            const prompt = `Write a concise summary of the following text extracted from these files: ${fileList.join(", ")}. Only use the text provided below.\n\n${allText}`;
            const response = agent.run(prompt);
            for await (const message of response) {
              if (message?.content) agentSummary += message.content;
            }
          } catch (e) {
            agentSummary = '[Error generating summary]';
          }
          if (!agentSummary.trim()) {
            // Fallback: show full content (no line limit)
            agentSummary = allText;
          }
          summary = `Summary of all .txt files in '${fileName}':\n${agentSummary}`;
        }
      }
    } else {
      // Try to read as text, otherwise show size or unsupported message
      let content = '';
      let agentSummary = '';
      try {
        content = await fs.promises.readFile(filePath, 'utf8');
        const response = agent.run(`Summarize the following text. Only use the text provided.\n\n${content}`);
        for await (const message of response) {
          if (message?.content) agentSummary += message.content;
        }
        if (!agentSummary.trim()) {
          // Fallback: show full content (no line limit)
          agentSummary = content;
        }
        summary = `Summary of '${fileName}':\n${agentSummary}`;
      } catch (e) {
        // If not readable as text, show size or unsupported message
        try {
          const stats = await fs.promises.stat(filePath);
          summary = `File '${fileName}' size: ${stats.size} bytes. Cannot summarize as text.`;
        } catch (e2) {
          summary = `File '${fileName}': Unable to read or summarize.`;
        }
      }
    }
    // Debug: log summary to console for troubleshooting
    if (outputFileName) {
      const outputPath = path.join(desktopPath, outputFileName);
      let toWrite = (summary || '').trim();
      if (!toWrite) {
        toWrite = '[No summary generated. There may be a bug.]';
      }
      await fs.promises.writeFile(outputPath, toWrite + '\n', 'utf8');
      // Also log to console for debug
      console.log('[Debug] Summary written to file:', toWrite);
      return `Summary saved to '${outputFileName}'.`;
    }
    return summary;
  } catch (err) {
    return `Error summarizing file: ${err.message}`;
  }
}

// Custom tool: true file deletion and cleanup
async function trueDelete(fileName) {
  const desktopPath = 'C:/Users/nikit/Desktop';
  const filePath = path.join(desktopPath, fileName);
  try {
    if (fs.existsSync(filePath)) {
      await fs.promises.unlink(filePath);
      return `File '${fileName}' was permanently deleted.`;
    } else {
      // Try to clean up .deleted_* files
      const deletedPattern = new RegExp(`^\\.deleted.*${fileName.replace(/\\./g, '\\.')}.*$`);
      const files = await fs.promises.readdir(desktopPath);
      let deletedFiles = files.filter(f => deletedPattern.test(f));
      let deletedCount = 0;
      for (const f of deletedFiles) {
        await fs.promises.unlink(path.join(desktopPath, f));
        deletedCount++;
      }
      if (deletedCount > 0) {
        return `Cleaned up ${deletedCount} deleted file(s) for '${fileName}'.`;
      }
      return `File '${fileName}' not found.`;
    }
  } catch (err) {
    return `Error deleting file '${fileName}': ${err.message}`;
  }
}

(async () => {
  await agent.loadTools();
  process.stdout.write('Ask me anything (Ctrl+C to exit):\n');
  process.stdin.setEncoding('utf8');
  for await (const line of process.stdin) {
    const prompt = line.trim();
    if (!prompt) continue;

    // Intercept delete requests
    const deleteMatch = prompt.match(/delete (?:the )?file ([^ ]+) from my desktop/i);
    if (deleteMatch) {
      const fileName = deleteMatch[1];
      const result = await trueDelete(fileName);
      console.log(result);
      process.stdout.write('> ');
      continue;
    }

    // Intercept search files
    const searchMatch = prompt.match(/find (.+) on my desktop|search for files? (.+)/i);
    if (searchMatch) {
      const pattern = searchMatch[1] || searchMatch[2];
      const result = await searchFiles(pattern);
      console.log(result);
      process.stdout.write('> ');
      continue;
    }

    // Intercept move/copy files
    const moveMatch = prompt.match(/move ([^ ]+) to ([^ ]+)/i);
    if (moveMatch) {
      const result = await moveOrCopyFile(moveMatch[1], moveMatch[2], true);
      console.log(result);
      process.stdout.write('> ');
      continue;
    }
    const copyMatch = prompt.match(/copy ([^ ]+) to ([^ ]+)/i);
    if (copyMatch) {
      const result = await moveOrCopyFile(copyMatch[1], copyMatch[2], false);
      console.log(result);
      process.stdout.write('> ');
      continue;
    }

    // Intercept edit file (append)
    const appendMatch = prompt.match(/append '(.+)' to ([^ ]+)/i);
    if (appendMatch) {
      let fileName = appendMatch[2].replace(/[.,!?;:]+$/, '');
      const result = await editFile(fileName, appendMatch[1]);
      console.log(result);
      process.stdout.write('> ');
      continue;
    }
    // Intercept edit file (replace)
    const replaceMatch = prompt.match(/replace '(.+)' with '(.+)' in ([^ ]+)/i);
    if (replaceMatch) {
      let fileName = replaceMatch[3].replace(/[.,!?;:]+$/, '');
      const result = await editFile(fileName, null, replaceMatch[1], replaceMatch[2]);
      console.log(result);
      process.stdout.write('> ');
      continue;
    }

    // Intercept create folder
    const folderMatch = prompt.match(/create (?:a )?folder named ([^ ]+)/i);
    if (folderMatch) {
      const result = await createFolder(folderMatch[1]);
      console.log(result);
      process.stdout.write('> ');
      continue;
    }

    // Intercept compress files
    const zipMatch = prompt.match(/zip (.+) into ([^ ]+)/i);
    if (zipMatch) {
      const fileNames = zipMatch[1].split(/,| and /).map(f => f.trim());
      const zipName = zipMatch[2];
      const result = await compressFiles(fileNames, zipName);
      console.log(result);
      process.stdout.write('> ');
      continue;
    }

    // Intercept summarize file (with optional output file and zip inner file)
    const summarizeZipInnerSaveMatch = prompt.match(/summarize the contents of ([^ ]+) from ([^ ]+) and save to ([^ ]+)/i);
    if (summarizeZipInnerSaveMatch) {
      const result = await summarizeFile(summarizeZipInnerSaveMatch[2], summarizeZipInnerSaveMatch[3], summarizeZipInnerSaveMatch[1]);
      console.log(result);
      process.stdout.write('> ');
      continue;
    }
    const summarizeZipInnerMatch = prompt.match(/summarize the contents of ([^ ]+) from ([^ ]+)/i);
    if (summarizeZipInnerMatch) {
      const result = await summarizeFile(summarizeZipInnerMatch[2], null, summarizeZipInnerMatch[1]);
      console.log(result);
      process.stdout.write('> ');
      continue;
    }
    const summarizeSaveMatch = prompt.match(/summarize the contents of ([^ ]+) and save to ([^ ]+)/i);
    if (summarizeSaveMatch) {
      const result = await summarizeFile(summarizeSaveMatch[1], summarizeSaveMatch[2]);
      console.log(result);
      process.stdout.write('> ');
      continue;
    }
    const summarizeMatch = prompt.match(/summarize the contents of ([^ ]+)/i);
    if (summarizeMatch) {
      const result = await summarizeFile(summarizeMatch[1]);
      console.log(result);
      process.stdout.write('> ');
      continue;
    }

    // Default: use agent
    const response = agent.run(prompt);
    for await (const message of response) {
      if (message?.content) {
        console.log(message.content);
      }
    }
    process.stdout.write('> ');
  }
})();