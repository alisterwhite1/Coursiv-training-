require('dotenv').config();
const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const Anthropic = require('@anthropic-ai/sdk');

if (!process.env.ANTHROPIC_API_KEY) {
  console.error('\n  ❌  ANTHROPIC_API_KEY is not set.');
  console.error('  Add it to a .env file in this folder:');
  console.error('\n      ANTHROPIC_API_KEY=sk-ant-...\n');
  process.exit(1);
}

const app = express();
const upload = multer({ dest: 'uploads/', limits: { fileSize: 20 * 1024 * 1024 } });
const client = new Anthropic();

app.use(express.static('public'));

function extractText(filePath, originalName) {
  const ext = path.extname(originalName).toLowerCase();
  if (ext === '.pdf') {
    const pdfParse = require('pdf-parse');
    const buffer = fs.readFileSync(filePath);
    return pdfParse(buffer).then(data => data.text);
  } else if (ext === '.docx' || ext === '.doc') {
    const mammoth = require('mammoth');
    return mammoth.extractRawText({ path: filePath }).then(result => result.value);
  } else if (ext === '.txt') {
    return Promise.resolve(fs.readFileSync(filePath, 'utf8'));
  }
  return Promise.reject(new Error(`Unsupported file type: ${ext}`));
}

app.post('/api/compare', upload.fields([
  { name: 'submitted', maxCount: 1 },
  { name: 'specification', maxCount: 1 }
]), async (req, res) => {
  const submittedFile = req.files?.submitted?.[0];
  const specFile = req.files?.specification?.[0];

  if (!submittedFile || !specFile) {
    return res.status(400).json({ error: 'Both documents are required.' });
  }

  let submittedText, specText;
  try {
    [submittedText, specText] = await Promise.all([
      extractText(submittedFile.path, submittedFile.originalname),
      extractText(specFile.path, specFile.originalname)
    ]);
  } catch (err) {
    return res.status(422).json({ error: `Could not extract text: ${err.message}` });
  } finally {
    [submittedFile.path, specFile.path].forEach(p => fs.unlink(p, () => {}));
  }

  const MAX_CHARS = 40000;
  if (submittedText.length > MAX_CHARS) submittedText = submittedText.slice(0, MAX_CHARS) + '\n[... truncated]';
  if (specText.length > MAX_CHARS) specText = specText.slice(0, MAX_CHARS) + '\n[... truncated]';

  const prompt = `You are a compliance auditor. You will compare a submitted document against a specification document and produce a detailed compliance report.

## Specification Document
${specText}

## Submitted Document
${submittedText}

## Your Task
Analyse the submitted document against every requirement in the specification document. Produce a structured compliance report with the following sections:

1. **Overall Compliance Summary** — A brief verdict (Compliant / Partially Compliant / Non-Compliant) with a one-paragraph summary.

2. **Compliance Score** — An estimated percentage score (0–100%) with a brief justification.

3. **Requirements Met** — A bullet list of specification requirements that the submitted document satisfies. For each, quote or reference the relevant section.

4. **Requirements Not Met** — A bullet list of specification requirements that are missing or inadequate in the submitted document. For each, explain what is missing and why it matters.

5. **Partial Compliance** — Requirements that are partially addressed but need improvement, with specific guidance on what needs to change.

6. **Recommendations** — Concrete, prioritised action items to bring the submitted document into full compliance.

Be specific, referencing actual content from both documents where possible.`;

  try {
    const message = await client.messages.create({
      model: 'claude-opus-4-8',
      max_tokens: 4096,
      messages: [{ role: 'user', content: prompt }]
    });

    const report = message.content[0].text;
    res.json({ report });
  } catch (err) {
    res.status(500).json({ error: `AI analysis failed: ${err.message}` });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Compliance checker running on http://localhost:${PORT}`));
