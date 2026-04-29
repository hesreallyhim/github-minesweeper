<picture>
  <source prefers-color-scheme="dark" srcset="assets/minesweeper-banner-dark.svg" />
  <source prefers-color-scheme="light" srcset="assets/minesweeper-banner-light.svg" />
  <img src="assets/minesweeper-banner.svg" alt="Minesweeper banner" />
</picture>

# Welcome to **GitHub Minesweeper!**<sup>*</sup><br>
<sub>*This repo is not associated with Microsoft, who owns the famous implementation we're most familiar with - and who also happens to own GitHub, who is also not affiliated with this repository. Really, it seems like no one is affiliated with this repository - even the maintainer is only somewhat aware of it I think.</sub>

<h1 align="center"><a href="https://github.com/hesreallyhim/github-minesweeper/issues/new?template=minesweeper-room.yml">START A NEW GAME</a></h1>

## Start A Game

<details>
<summary>How to start a game</summary>

1. Gameplay take place inside GitHub Issues. Start a new issue by clicking [HERE](https://github.com/hesreallyhim/github-minesweeper/issues/new?template=minesweeper-room.yml)<br>(or, go to **Issues** -> **New issue** -> **Minesweeper Room**)

2. After having read the [CODE OF CONDUCT](.github/CODE_OF_CONDUCT.md) at least once, tick the box, then click <kbd>SUBMIT</kbd>.

3. **That's it!** That issue is now your personal Minesweeper game. Wait for the Minesweeper-Bot to set up your game, then submit moves by commenting in the thread. The Bot is usually pretty responsive - but it is very busy, so don't spam your own game (or anyone else's).
</details>

## What's "Minesweeper"?

<details>
<summary>If you grew up with Windows XP, you can probably skip this part</summary>

<br>

It's this thing:

<picture><img src="assets/minesweeper-board-classic.jpg" alt="Minesweeper screenshot" width="200" /></picture>

Minesweeper is a classic computer game. Like all great games, it's about a situation that we can all relate to: going through a grid of tiles and trying to identify the location of hidden explosive devices on the basis of numerical hints, while trying to avoid getting blown up. You could call it a "slice of life" game I suppose.

### Gameplay

You start with a 9x9 grid of empty cells. One by one, you select a cell in order to reveal what's underneath. There's three outcomes:

(i) The cell reveals a number - that number indicates *how many cells that touch that cell have a mine in them*. This is the information you use to figure out which cells in the grid have mines, and to clear the board.

(ii) The cell has no mines around it. It reveals the whole group of adjacent empty cells.

(iii) The cell has a mine in it. The mine explodes. That means you lost the game.

So the idea is to find some cells with *numbers*, and then use that information to deduce whether other cells do or do not have mines in them. (It hardly seems worth explaining because surely everyone has done this in real life, but anyway that's how it works.)

In order to keep track of things, once you figure out that a certain cell must contain a mine, you do what anyone would do in that situation, and stick a flag right on top of the place where the underground explosive that is set to trigger on pressure is lying. Simple, right?

</details>

## Command Format

Use plain commands (slash prefix is also accepted):

- `A1 B2` or `guess A1 A2` - reveal cell(s)
- `flag H7 H8` - flag suspected mine(s)
- `unflag H7` - remove flag(s)
- `giveup` - end the game

Rules:

- Commands are case-insensitive.
- Use one action per line.
- Any unrecognized token invalidates the whole turn.

## Hall Of Fame

<!-- MS_LEADERBOARD_START -->
### Leaderboards
_As of (UTC): 2026-04-21T05:07:54+00:00 from 2 completed games_
(Leaderboards update every 15 minutes)

<table align="center">
  <tr>
    <td><picture><img src="assets/readme-leaderboard-card-champions.svg" alt="Champions Card" width="460" /></picture></td>
    <td><picture><img src="assets/readme-leaderboard-card-commitment.svg" alt="Commitment Card" width="460" /></picture></td>
  </tr>
  <tr>
    <td><picture><img src="assets/readme-leaderboard-card-quick-clear.svg" alt="Quick Clear Card" width="460" /></picture></td>
    <td><picture><img src="assets/readme-leaderboard-card-consistency.svg" alt="Consistency Card" width="460" /></picture></td>
  </tr>
</table>
<!-- MS_LEADERBOARD_END -->

## Repository Surface

- `.github/ISSUE_TEMPLATE/` - room creation UX
- `.github/workflows/minesweeper-leaderboards.yml` - scheduled leaderboard publishing
- `scripts/build_leaderboards.py` - leaderboard build entrypoint
- `src/minesweeper/leaderboards.py` - leaderboard logic and README block rendering
- `data/games/` - terminal game records
- `data/leaderboards.json` - machine-readable leaderboard summary
- `assets/readme-leaderboard-card-*.svg` - generated leaderboard cards
