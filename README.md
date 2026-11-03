# 3DSnitch: Nintendo 3DS GitHub Watcher

A small, fully automated bot that keeps an eye on GitHub for **Nintendo 3DS** projects (homebrew, custom firmware, emulators, tools, ports, games) and sends you a short AI-written summary of what's new, straight to Telegram.

**Live demo:** [t.me/N3DSnitch](https://t.me/N3DSnitch)

> 🇺🇦 **Messages are in Ukrainian by default.** You can switch to any language, see [Changing the language](#changing-the-language).

## What it does

Every few hours it:

1. **Searches GitHub** for recently updated repositories using a set of 3DS-related terms (`3ds`, `libctru`, `devkitPro`, `3dsx`, `Luma3DS`, and more). Many 3DS projects never mention "Nintendo", so it searches by community vocabulary rather than by one keyword.
2. **Checks what changed** since the last run: new commits and new releases.
3. **Asks an AI (Google Gemini, free tier)** to decide whether the repo is really about the Nintendo 3DS (filtering out 3ds Max, 3-D Secure and so on), then to write a short description of the project and a plain-language summary of the changes.
4. **Posts it to Telegram.** If several versions came out between checks, you get one combined summary with a list of versions, not a wall of duplicates.

If nothing relevant changed, it stays quiet.

## Features

- Runs on its own with **GitHub Actions** (no server needed)
- **Free to run**: GitHub Actions + Gemini free tier + Telegram bot
- Catches up on everything since the last successful run, so a delayed run misses nothing
- AI relevance filter for ambiguous "3ds" results
- **Blacklist** for repos or whole accounts you don't want to see (`blacklist.txt`)
- Send to one person, several people, a group, or a channel
- Remembers repos it has already analyzed to save API usage

## Setup

You don't need to be a developer. About 20-30 minutes.

1. **Fork or copy this repo** to your own GitHub account.
2. **Get a free Gemini API key** at [aistudio.google.com](https://aistudio.google.com) (Get API key).
3. **Create a Telegram bot:** message [@BotFather](https://t.me/BotFather), send `/newbot`, and copy the token. Then send any message to your new bot and open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` to find your chat ID.
4. **Add three secrets** in your repo under *Settings → Secrets and variables → Actions*:

   | Secret | Value |
   |---|---|
   | `GEMINI_API_KEY` | your Gemini key |
   | `TELEGRAM_BOT_TOKEN` | token from BotFather |
   | `TELEGRAM_CHAT_ID` | your chat ID (several IDs can be separated by commas) |

5. In *Settings → Actions → General → Workflow permissions*, choose **Read and write permissions** (the bot saves its progress to `state.json`).
6. Open the **Actions** tab, pick **3DS repo watcher**, and click **Run workflow** to test.

After that it runs automatically on the schedule in `.github/workflows/watcher.yml` (`0 */6 * * *` means every 6 hours; use `0 */3 * * *` for every 3 hours).

## Configuration

| What | Where |
|---|---|
| Search terms | `SEARCH_TERMS` list at the top of `watcher.py` |
| AI model | `MODEL` in `watcher.py` (change it if Google retires the current one) |
| Maximum catch-up window | `MAX_LOOKBACK_HOURS` in `watcher.py` |
| Hide repos or accounts | `blacklist.txt` (`owner/repo` or `owner/*`, one per line) |
| Check frequency | `cron` line in `.github/workflows/watcher.yml` |

## Changing the language

The language is set by one instruction in the AI prompt in `watcher.py`: find the line starting with `Write the text values of ...` and replace `Ukrainian` with your language. Also translate the two labels in the message (`Зміни:` and `Нова версія` / `Нові версії`) near the end of the file.

## Notes

- Since the repo is public, your `blacklist.txt` and `state.json` are visible to everyone. Your API keys and bot token are **not**, as long as they are stored as GitHub secrets and never written into a file.
- The free Gemini tier has daily limits. This bot only calls the AI for repos that actually changed, so normal usage stays well within them.
- Summaries are AI-generated and can occasionally be wrong. Always check the linked repo before downloading anything.

## Disclaimer

This project only reports publicly available information from GitHub. It is not affiliated with Nintendo, GitHub, Google or Telegram. Nintendo 3DS is a trademark of Nintendo.
