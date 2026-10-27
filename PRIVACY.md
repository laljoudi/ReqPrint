# ReqPrint Privacy Policy

Last updated: October 2026

ReqPrint is a student portfolio project that turns a plain-language idea into a structured Software Requirements Specification (SRS) and can optionally create the result in Jira. This page explains what data the app handles. It is written to match how the code actually works.

## Summary

- ReqPrint has no database and does not save your documents or conversations on its servers.
- Your text is sent to an AI provider (Groq) to generate the output.
- If you connect Jira, an encrypted connection cookie is stored in your browser.
- Please do not enter confidential, personal or client data.

## What the app handles

### Text you type
Your project description, pasted notes, answers to questions, and refinement instructions are sent from your browser to the ReqPrint server and then to Groq to produce questions, requirements and reviews. The server does not write this text to a database or to files. The Word export is built in memory and streamed back to you.

### Data sent to Groq (AI provider)
Depending on the step, Groq receives: your project category, your description or notes, the questions and your answers, and the generated document (for refine and review). When you push to Jira, Groq receives each story's id, role, text, and, only if you turn on AI sub-tasks, its acceptance criteria. Groq does not receive Jira tokens, cookies, project names or dates.

### Jira (only if you choose to connect)
ReqPrint uses Atlassian OAuth 2.0. If you connect and push, the app sends to your Jira site: the project name you choose, an epic, stories, acceptance criteria, sprints, optional sub-tasks, and the labels `reqprint` and the project category. It does not send your interview answers or original notes. You can revoke access at any time from your Atlassian account settings.

## Cookies and browser storage

| Name | Purpose | Contents | Lifetime |
| --- | --- | --- | --- |
| `jira_conn` | Keeps your Jira connection | Encrypted refresh token, site id, site URL and site name. HttpOnly. | Up to 90 days |
| `jira_oauth_state` | Protects the login against forgery (CSRF) | A random value | 10 minutes |

The browser also keeps a small `localStorage` record for each document you push to Jira (a hashed document id, project key, project URL, date and story count). No tokens and no document text are stored there. You can clear all of this from your browser settings.

## Logs and temporary data

- The server logs error types and fixed messages. It does not log your text, your Groq key, tokens or cookies.
- Server logs may include request addresses, and error logs may include Jira project keys, labels or story ids.
- Rate limiting keeps a per-visitor counter in memory. It is lost when the server restarts.
- Hosting is provided by Render, which keeps its own infrastructure logs.

## Sharing

Your data goes only to Groq (AI processing), Atlassian/Jira (only if you connect and push), and Render (hosting). ReqPrint does not sell data and does not use it for advertising.

## Your choices

- Do not connect Jira, and no Jira data is ever stored.
- Disconnect Jira in the app, or revoke access in your Atlassian account.
- Clear your cookies and site data to remove everything stored in your browser.

## Contact

Questions or requests: Aljoudi1layan@gmail.com


## Changes

If this policy changes, the date above will be updated.
