"""eddic lore bot — Discord Q&A over the campaign's player projection.

Answers when @mentioned (or on every message in AUTO_CHANNEL_IDS),
reading only the corpus it was given. The corpus self-refreshes by
polling its source (freshness contract): local mode fingerprints the
projection directory; cloud mode polls the wiki repo's HEAD SHA and
refetches the tarball on change. `!lore reload` exists as the owner's
escape hatch, never the mechanism.

Config (variables.txt beside this file, or real env, env wins):
  DISCORD_TOKEN                                required
  PROVIDER=anthropic|openai                    default anthropic
  ANTHROPIC_API_KEY / OPENAI_API_KEY           whichever PROVIDER needs
  CORPUS_DIR=dist/player                       local mode (default)
  GITHUB_REPO=owner/repo CORPUS_SUBDIR=dist/player GITHUB_TOKEN=...
                                               cloud mode (tarball)
  MODEL=  (defaults per provider)  MAX_TOKENS=800  REFRESH_MINUTES=5
  AUTO_CHANNEL_IDS=1,2   OWNER_ID=...  COOLDOWN_SECONDS=15
  PERSONA_FILE=persona.md  PLAYERS_FILE=       (optional roster,
                                               injected after the
                                               cache breakpoint,
                                               never in the corpus)
  SITE_URL=https://...                         page links in answers
  QUESTION_LOG=questions.jsonl                 what the table asked
                                               (empty or "off" records
                                               nothing); DIGEST_DAYS=14
                                               retention, DIGEST_WEEKDAY=0
                                               DIGEST_HOUR=10 when the
                                               weekly digest is sent to
                                               OWNER_ID, DIGEST_FILE=
                                               digest-latest.md
"""

import asyncio
import os
import time
from pathlib import Path

import discord

import botlib
import providers

HERE = Path(__file__).resolve().parent
botlib.load_variables(HERE / "variables.txt")

TOKEN = os.environ["DISCORD_TOKEN"]
PROVIDER = os.environ.get("PROVIDER", "anthropic")
MODEL = os.environ.get("MODEL") or providers.DEFAULT_MODELS[PROVIDER]
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "800"))
REFRESH = int(os.environ.get("REFRESH_MINUTES", "5"))
AUTO_CHANNELS = {int(c) for c in
                 os.environ.get("AUTO_CHANNEL_IDS", "").split(",") if c}
# optionally confine the bot to one category (a "group" of channels):
# when set, @mentions outside it are ignored — no answering in the
# dice or music channels
CATEGORY_IDS = {int(c) for c in
                os.environ.get("CATEGORY_IDS", "").split(",") if c}
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
COOLDOWN = int(os.environ.get("COOLDOWN_SECONDS", "15"))
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")

# What the table asked: a short, DM-side record of the questions put to
# the bot, aggregated into a weekly digest for OWNER_ID. It holds only
# what the owner could already scroll back and read in the channel —
# question text, time, pages cited — plus a one-way tag that exists so
# "!lore forget" can find a player's rows. It never leaves this host:
# not the corpus, not the projection, not the repo, not the site.
_log_name = os.environ.get("QUESTION_LOG", "questions.jsonl").strip()
QUESTION_LOG = (HERE / _log_name) if _log_name and _log_name != "off" else None
QUESTION_DAYS = int(os.environ.get("DIGEST_DAYS", "14"))
DIGEST_WEEKDAY = int(os.environ.get("DIGEST_WEEKDAY", "0"))    # 0 = Monday
DIGEST_HOUR = int(os.environ.get("DIGEST_HOUR", "10"))         # host's clock
DIGEST_FILE = HERE / os.environ.get("DIGEST_FILE", "digest-latest.md")
SALT_FILE = HERE / "questions-salt.txt"
OPTOUT_FILE = HERE / "questions-optout.txt"

persona = (HERE / os.environ.get("PERSONA_FILE", "persona.md")).read_text(
    encoding="utf-8")
if SITE_URL:
    # the citation rule needs the URL beside it, not 60 KB away in
    # the corpus header — models bind adjacent facts, not distant ones
    persona += (f"\n\nThe published site root is {SITE_URL} — cite "
                f"pages exactly like "
                f"[Page Title]({SITE_URL}/path/to/page) "
                f"(the page's wiki path with `.md` stripped).")
players = ""
if os.environ.get("PLAYERS_FILE"):
    players = (HERE / os.environ["PLAYERS_FILE"]).read_text(encoding="utf-8")

llm = providers.get_provider(PROVIDER)
intents = discord.Intents.default()
intents.message_content = True          # enable in the dev portal too,
client = discord.Client(intents=intents)  # or the bot is online but deaf

# optional capabilities extend the same always-on bot; the convene
# module vendors convene.py beside this file (session lifecycle:
# native scheduled events, quorum, recap announce)
try:
    import convene as _convene
    capability = _convene.setup(client)
except ImportError:
    capability = None
except Exception as e:                      # a capability must never
    print(f"convene setup failed, continuing without it: {e}")
    capability = None

state = {"corpus": "", "stamp": "", "loaded": 0.0}
last_reply = {}
salt = botlib.log_salt(SALT_FILE) if QUESTION_LOG else ""
optouts = botlib.read_optouts(OPTOUT_FILE) if QUESTION_LOG else set()
digest_state = {"last_sent": ""}

PRIVACY_NOTE = (
    "When you ask me something in this server I write down the question, "
    "the time, and which pages I pointed you at — nothing else. No names, "
    "no handles, no other messages, and never anything you send me "
    "privately. It stays on your DM's own computer for {days} days and is "
    "then deleted, and it is only ever used for a weekly summary of what "
    "the table has been asking about. Say `!lore forget` and I will delete "
    "yours and stop recording you; `!lore remember` turns it back on.")


def asker_of(message):
    return botlib.asker_tag(message.author.id, salt) if QUESTION_LOG else ""


def record_question(message, question, reply, outcome):
    """Log one question, or decline to. Never records a private message
    to the bot (the owner cannot scroll back and read those) and never
    records a player who has opted out."""
    if not QUESTION_LOG or message.guild is None:
        return
    who = asker_of(message)
    if who in optouts:
        return
    try:                                    # the record is never worth
        cited = botlib.cited_paths(          # an answer the table missed
            reply, botlib.page_paths(state["corpus"]))
        botlib.log_question(
            QUESTION_LOG,
            botlib.question_record(question, cited=cited,
                                   outcome=outcome or
                                   ("answered" if cited else "uncited"),
                                   who=who),
            keep_days=QUESTION_DAYS)
    except Exception as e:
        print(f"question log error: {e}")


def load_corpus():
    if GITHUB_REPO:
        state["stamp"] = botlib.github_head_sha(
            GITHUB_REPO, os.environ["GITHUB_TOKEN"],
            os.environ.get("GITHUB_BRANCH", "master"))
        state["corpus"] = botlib.corpus_from_tarball(
            GITHUB_REPO, os.environ["GITHUB_TOKEN"],
            os.environ.get("CORPUS_SUBDIR", "dist/player"),
            os.environ.get("GITHUB_BRANCH", "master"))
    else:
        src = HERE / os.environ.get("CORPUS_DIR", "dist/player")
        state["stamp"] = botlib.dir_fingerprint(src)
        state["corpus"] = botlib.corpus_from_dir(src)
    state["loaded"] = time.time()
    print(f"corpus loaded: {len(state['corpus']) // 1024} KB")


async def freshness_poll():
    while True:
        await asyncio.sleep(REFRESH * 60)
        try:
            if GITHUB_REPO:
                head = botlib.github_head_sha(
                    GITHUB_REPO, os.environ["GITHUB_TOKEN"],
                    os.environ.get("GITHUB_BRANCH", "master"))
                stale = head != state["stamp"]
            else:
                src = HERE / os.environ.get("CORPUS_DIR", "dist/player")
                stale = botlib.dir_fingerprint(src) != state["stamp"]
            if stale:
                await asyncio.to_thread(load_corpus)
                if capability:                      # announce new recaps
                    try:
                        await capability.on_corpus_refresh(
                            state["corpus"])
                    except Exception as ce:
                        print(f"capability refresh failed: {ce}")
        except Exception as e:                      # poll must survive
            print(f"freshness poll error: {e}")


def corpus_text():
    return (f"CAMPAIGN WIKI (site: {SITE_URL or 'unpublished'})"
            f"\n\n{state['corpus']}")


async def answer(message):
    now = time.time()
    if now - last_reply.get(message.channel.id, 0) < COOLDOWN:
        return
    last_reply[message.channel.id] = now
    history = []
    async for m in message.channel.history(limit=15):
        history.append(f"{m.author.display_name}: {m.clean_content}")
    history.reverse()
    question = botlib.strip_bot_mention(message.content, client.user.id)
    prompt = ("Recent channel messages:\n" + "\n".join(history)
              + f"\n\nAnswer this question from the wiki:\n{question}")
    async with message.channel.typing():
        try:
            reply = await asyncio.to_thread(
                llm.complete, model=MODEL, max_tokens=MAX_TOKENS,
                corpus_text=corpus_text(), persona=persona,
                roster=players, prompt=prompt)
            for chunk in botlib.split_message(reply):
                await message.reply(chunk, mention_author=False)
            record_question(message, question, reply, "")
        except Exception as e:
            print(f"answer error: {e}")
            record_question(message, question, "", "failed")
            await message.add_reaction("❌")


def build_digest(days=7):
    rows = botlib.read_questions(QUESTION_LOG) if QUESTION_LOG else []
    return botlib.render_digest(
        botlib.weekly_digest(rows, state["corpus"], days=days))


async def send_digest(text):
    """The digest is DM-only material and goes exactly one place: a
    private message to the owner. It is never posted to a channel, never
    written into the wiki, and never staged to any player surface."""
    owner = await client.fetch_user(OWNER_ID)
    for chunk in botlib.split_message(text):
        await owner.send(chunk)
    # also on disk (gitignored), so the owner's prep agent can read it
    DIGEST_FILE.write_text(text, encoding="utf-8")


async def digest_loop():
    """Wake hourly; send the week's digest on the chosen day. Missing a
    run costs one week's summary and nothing else."""
    while True:
        await asyncio.sleep(3600)
        try:
            if not (QUESTION_LOG and OWNER_ID):
                continue
            if botlib.digest_due(digest_state["last_sent"],
                                 DIGEST_WEEKDAY, DIGEST_HOUR):
                await send_digest(build_digest())
                digest_state["last_sent"] = time.strftime("%Y-%m-%d")
        except Exception as e:
            print(f"digest error: {e}")


@client.event
async def on_ready():
    await asyncio.to_thread(load_corpus)
    client.loop.create_task(freshness_poll())
    client.loop.create_task(digest_loop())
    if capability:
        try:                                # never let a capability
            await capability.ready(state["corpus"])  # break the bot
        except Exception as e:
            print(f"capability ready failed: {e}")
    print(f"ready as {client.user}")


@client.event
async def on_message(message):
    if message.author.bot:
        return
    text = message.content.strip()
    if text.startswith("!lore"):
        cmd = text[5:].strip().lower()
        # anyone may ask what is recorded and opt out of it
        if cmd.startswith("privacy"):
            await message.reply(PRIVACY_NOTE.format(days=QUESTION_DAYS)
                                if QUESTION_LOG else
                                "I keep no record of anyone's questions.",
                                mention_author=False)
            return
        if cmd.startswith(("forget", "remember")):
            if not QUESTION_LOG:
                await message.reply("I keep no record of anyone's "
                                    "questions.", mention_author=False)
                return
            who = asker_of(message)
            out = cmd.startswith("forget")
            botlib.set_optout(OPTOUT_FILE, who, out)
            if out:
                optouts.add(who)
            else:
                optouts.discard(who)
            gone = botlib.forget_asker(QUESTION_LOG, who) if out else 0
            await message.reply(
                f"Done — {gone} of your question(s) deleted, and I will "
                "not record any more of yours." if out else
                "Done — I will include your questions again from now on.",
                mention_author=False)
            return
        if message.author.id != OWNER_ID:
            return
        if "reload" in cmd:
            await asyncio.to_thread(load_corpus)
            await message.reply("corpus reloaded", mention_author=False)
        elif "digest" in cmd:
            await send_digest(build_digest())
            await message.reply("digest sent to your messages",
                                mention_author=False)
        else:
            age = int(time.time() - state["loaded"])
            asked = len(botlib.read_questions(QUESTION_LOG)) \
                if QUESTION_LOG else 0
            await message.reply(
                f"corpus {len(state['corpus']) // 1024} KB, loaded {age}s "
                f"ago, stamp {state['stamp'][:12]}, {asked} question(s) on "
                f"record", mention_author=False)
        return
    if CATEGORY_IDS and getattr(message.channel, "category_id", None) \
            not in CATEGORY_IDS:
        return                              # outside the bot's category
    mentioned = client.user in message.mentions
    if mentioned or message.channel.id in AUTO_CHANNELS:
        await answer(message)


if __name__ == "__main__":
    client.run(TOKEN)
