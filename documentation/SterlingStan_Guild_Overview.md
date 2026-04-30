# SterlingStan — Guild Bot Overview

**For:** Sterling Guild Leadership
**Prepared by:** Zarkion
**Version:** 1.0

---

## What Is SterlingStan?

SterlingStan is a custom Discord bot built specifically for the Sterling guild in AdventureQuest Worlds. Its core job is to give the guild a proper roster — a living, searchable record that links each member's Discord account to their AQW character name and their favorite classes. Officers can look up any member instantly, view the full guild roster, and manage records on behalf of members who need help.

The bot lives entirely inside Discord. Members and officers interact with it using slash commands (the `/command` style that Discord suggests to you as you type). There is no website to log into, no separate app to install. If you're in the Discord server, you have access to your commands.

---

## Where Does It Live?

SterlingStan runs on **Amazon Web Services (AWS)**, which is the same cloud platform used by companies like Netflix, NASA, and Airbnb. Rather than running on a computer that someone in the guild has to keep on and connected to the internet 24/7, it runs "in the cloud" — on Amazon's infrastructure, which is always on and always available.

The bot only actually does any work when someone uses a command. To stay responsive at all times, it also wakes itself up with a silent ping every 10 minutes. Think of it less like a computer that's always on, and more like a vending machine: it does nothing until someone pushes a button, then it does exactly what it's supposed to, then it goes back to waiting.

Everything about how the bot is set up — every setting, every piece of infrastructure — is written down in a set of configuration files stored alongside the bot's code. This means if guild management ever changes hands, the new tech lead can get the whole thing running again from scratch without needing to know what the previous person did or click through any menus. It's all written down.

---

## What Can It Do?

Commands are split into two groups: ones that any guild member can use on themselves, and ones reserved for officers.

### Member Commands

These are available to everyone in the server.

**`/register`**
The first command a new member should use. You provide your AQW character name (your in-game name, or IGN) and the bot links it to your Discord account. After this, you exist in the guild roster.

**`/setclasses`**
After registering, use this to list up to 5 of your favorite or most-used AQW classes, separated by commas — for example: `Void Highlord, Stonecrusher, Archpaladin`. This information is saved to your profile and visible to officers.

**`/update`**
Changed your main character or switched up your class lineup? Use `/update` to change your registered in-game name, your class list, or both.

**`/profile`**
Shows your own profile card — your Discord username, AQW character name, the classes you've listed, and the date you registered. Only you can see it; it appears as a private message from the bot.

**`/unregister`**
Removes your profile from the roster entirely. The bot will ask you to confirm before anything is deleted — you can't accidentally remove yourself.

---

### Officer Commands

These are only available to members with the designated officer role in Discord.

**`/lookup @member`**
Pulls up the profile card of any registered guild member by mentioning them. Useful for quickly checking a member's IGN or classes without having to ask them directly.

**`/roster`**
Shows the full list of registered guild members, 10 at a time, with each person's Discord username and AQW character name side by side. Good for a quick headcount or for finding someone before an event.

**`/adminset @member`**
Lets an officer create or update a profile on behalf of another member. Useful for onboarding members who aren't comfortable using the bot themselves, or for correcting a typo in someone's IGN.

**`/adminremove @member`**
Removes another member's profile from the roster. Like `/unregister`, this requires a confirmation click before anything is deleted.

---

## What Does a Profile Look Like?

When you use `/profile` or when an officer uses `/lookup`, the bot replies with a card that looks like this:

```
╔═══════════════════════════╗
║  🗡️  HeroOfLore           ║
║  Discord: @HeroPlayer     ║
║  Member since: 2025-04-01 ║
║                           ║
║  Favorite Classes:        ║
║  1. Void Highlord         ║
║  2. Stonecrusher          ║
║  3. Archpaladin           ║
╚═══════════════════════════╝
```

All bot responses are **private by default** — only the person who ran the command can see them. The bot won't clutter up any channels.

---

## Privacy and Security

A few things worth knowing about how data is handled:

- **The bot only stores what you give it.** It records your Discord user ID (a permanent internal number Discord assigns to every account — not your display name), your AQW character name, and your class list. Nothing else.
- **Your Discord user ID, not your username, is what the bot tracks.** This means if you change your Discord display name, your profile still works correctly.
- **Responses are private.** Every command response is only visible to you. Officers using `/lookup` or `/roster` also see those responses privately.
- **Credentials are locked away.** The bot's passwords and security keys are stored in a dedicated secure vault (Amazon's Secrets Manager) that is separate from the rest of the bot. They are never stored in the code itself.
- **Only officers can touch other people's data.** The permission system is tied directly to the officer role in your Discord server. If someone's officer role is removed in Discord, they immediately lose access to officer commands — no separate configuration needed.

---

## How Much Does It Cost?

Roughly **$0.40–$0.50 per month**, which is almost entirely the cost of the secure credentials vault (~$0.40/month). Every other piece of the system — the compute, the database, the web endpoint — falls within Amazon's permanent free tier at guild scale.

For comparison, a traditional always-on server to host a bot typically runs $5–10/month at minimum. The cloud approach costs about 10 times less because the bot only runs when it's actually being used.

At this time, Zarkion is willing to bear the monthly expenses out of his own pocket. He and the guild leadership team can revisit this plan in the future if the cost balloons. In the worst case scenario, Zarkion may ask for assistance from the guild members in the form of donations. He highly doubts that this will happen any time soon.

---

## What Happens If Something Goes Wrong?

The bot logs every command it handles, including any errors, to a monitoring system that can be searched and filtered. If something breaks, the developer can pull up exactly what happened and when without guessing.

---

## What's Planned for the Future?

The bot is built to grow. The following features are planned for future releases, in rough order of priority:

- **Class autocomplete** — when typing your classes with `/setclasses`, Discord will suggest known AQW class names as you type, reducing typos.
- **Auto role assignment** — when a member successfully registers, the bot automatically gives them a "Registered" role in Discord, making it easy to see at a glance who has and hasn't registered.
- **Officer notes** — officers will be able to attach private notes to a member's profile, visible only to other officers.
- **Event attendance tracking** — officers will be able to create events and members can check in, building an attendance history per member.
- **Class-based roster filtering** — officers will be able to run `/roster class:Stonecrusher` to find everyone who mains a specific class, useful for planning group content.
- **Web dashboard** — a browser-based interface for officers to manage the roster without needing to use Discord commands.

None of these require changes to the core architecture. They are additions, not rewrites.

---

## Frequently Asked Questions

**Do I have to register?**
It's not technically enforced, but registering is how you appear on the guild roster. Unregistered members are invisible to the bot and to officers using `/roster`.

**What if I have multiple AQW characters?**
You can only link one character name per Discord account. Use your main, or whichever character you play in guild content. You can always change it later with `/update`.

**Can the bot read my messages?**
No. SterlingStan only receives information when you explicitly use one of its slash commands. It does not monitor the chat.

**What if I leave the guild?**
An officer can remove your profile with `/adminremove`, or you can remove it yourself with `/unregister` before you leave.

**Who maintains this?**
Currently, Zarkion is the developer and sole maintainer. The entire setup is documented and version-controlled so that if guild leadership or technical ownership changes, the new responsible person can take over without starting from scratch.

**What if we want to shut it down?**
The developer can tear down the entire bot and all its cloud resources with a single command. Nothing will be left running and no further charges will accrue.

**Will the bot ever time out or fail to respond?**
No. The bot sends itself a silent "stay awake" ping every 10 minutes so it's always ready to respond instantly, even during quiet periods. You should never see "The application did not respond" under normal conditions.
